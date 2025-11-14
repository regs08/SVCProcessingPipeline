import re
import warnings
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Literal, Optional, Sequence, Union

import pandas as pd


GroupTuple = namedtuple("GroupTuple", ["members", "name"])


@dataclass(frozen=True)
class GroupSpec:
    """Tuple-like specification for grouping spectra, with optional display name."""
    members: Sequence[int]
    name: Optional[str] = None

    def __post_init__(self):
        normalized_members = tuple(int(m) for m in self.members)
        object.__setattr__(self, "members", normalized_members)

    def to_namedtuple(self) -> GroupTuple:
        return GroupTuple(self.members, self.name)

    @classmethod
    def from_csv(
        cls,
        csv_path: Union[str, Path],
        *,
        members_column: str = "scans",
        id_column: str = "scan_id",
        name_column: str = "name",
        exclude_columns: Sequence[str] = ("reference",),
        delimiter: str = ",",
        return_namedtuple: bool = True,
    ) -> List[Union["GroupSpec", GroupTuple]]:
        """
        Build grouping specifications from a CSV containing `members` and `name` columns.

        Args:
            csv_path: Path to the CSV file.
            members_column: Column containing member identifiers (comma-separated or iterable-like).
            id_column: Optional single-value identifier column used when `members_column` is missing.
            name_column: Column containing human-readable group names.
            exclude_columns: Columns dropped from the data before processing (defaults to removing `reference`).
            delimiter: Delimiter used when splitting string-based member lists.
            return_namedtuple: Whether to return namedtuples (`True`) or GroupSpec instances (`False`).

        Returns:
            List of GroupTuple or GroupSpec objects, respecting `return_namedtuple`.
        """
        df = pd.read_csv(csv_path)

        # Build case-insensitive lookup (preserve first occurrence)
        column_lookup = {col.lower(): col for col in df.columns}

        drop_columns = [
            column_lookup[col.lower()]
            for col in exclude_columns
            if col.lower() in column_lookup
        ]
        if drop_columns:
            df = df.drop(columns=drop_columns)
            column_lookup = {col.lower(): col for col in df.columns}

        resolved_members_col = column_lookup.get(members_column.lower())
        resolved_id_col = column_lookup.get(id_column.lower())
        resolved_name_col = column_lookup.get(name_column.lower())

        if resolved_members_col is None and resolved_id_col is None:
            raise KeyError(
                f"Expected '{members_column}' or '{id_column}' in {csv_path}; none found."
            )
        if resolved_name_col is None:
            raise KeyError(f"Column '{name_column}' not found in {csv_path}.")

        specs: List[Union["GroupSpec", GroupTuple]] = []
        for _, row in df.iterrows():
            if resolved_members_col is not None:
                members_value = row[resolved_members_col]
            else:
                members_value = row.get(resolved_id_col)
            if pd.isna(members_value):
                continue

            if isinstance(members_value, str):
                tokens = [token.strip() for token in members_value.replace(";", delimiter).split(delimiter)]
                members = tuple(int(token) for token in tokens if token)
            elif isinstance(members_value, Iterable):
                members = tuple(int(v) for v in members_value)
            else:
                members = (int(members_value),)

            if not members:
                continue

            name_value = row.get(resolved_name_col)
            group_name = None if pd.isna(name_value) else str(name_value).strip() or None

            if group_name and group_name.lower() == "reference":
                continue

            spec = cls(members=members, name=group_name)
            specs.append(spec.to_namedtuple() if return_namedtuple else spec)

        return specs


class SVCDataProcessor:
    """Compact OO processor for SVC spectra workflows (logic preserved)."""
    SigEntry = namedtuple("SigEntry", ["index", "base_name", "number"])
    SAMPLE_NAME_PATTERN = re.compile(r"^(?P<base>.+?)\.(?P<num>\d+)(?:\.sig)?$", re.IGNORECASE)
    TRAILING_DIGITS_PATTERN = re.compile(r"^(?P<base>.*?)(?P<num>\d+)(?:\.sig)?$", re.IGNORECASE)

    # ---------- IO ----------
    def load_csv(self, file_path: str, **kwargs):
        """Load CSV file. Pass any additional pandas.read_csv() arguments via kwargs."""
        self.df: pd.DataFrame = pd.read_csv(file_path, **kwargs)
        return self
    
    def load_excel(self, file_path: str, sheet: Union[int, str] = 0):
        """Load Excel file (legacy method for backward compatibility)."""
        self.df: pd.DataFrame = pd.read_excel(file_path, sheet_name=sheet)
        return self

    # ---------- Structure ----------
    def split_columns(self, name_col: Optional[str] = None):
        assert hasattr(self, "df"), "Call load_csv or load_excel first."
        self.name_col: str = name_col or self.df.columns[0]
        num_cols = self.df.select_dtypes(include='number').columns.tolist()
        xlike_cols = [c for c in self.df.columns if isinstance(c, str) and c.startswith("X")]
        # Preserve order, unique
        self.wavelength_cols: List[str] = list(dict.fromkeys(num_cols + xlike_cols))
        return self

    # ---------- Parsing ----------
    @classmethod
    def normalize_sample_name(cls, value: Union[str, int, float]) -> str:
        """
        Normalize a raw sample name into the canonical `{name}.####` format (no `.sig` suffix).

        Args:
            value: Original sample name value.

        Returns:
            str: Normalized sample name.

        Raises:
            ValueError: If the value cannot be coerced into the expected format.
        """
        raw = "" if value is None else str(value).strip()
        if not raw:
            raise ValueError("Sample name is empty or None.")

        name = raw[:-4] if raw.lower().endswith(".sig") else raw

        match = cls.SAMPLE_NAME_PATTERN.match(name)
        if not match:
            match = cls.TRAILING_DIGITS_PATTERN.match(name)

        if not match:
            raise ValueError(f"Sample name '{raw}' does not match expected pattern.")

        base = match.group("base").rstrip(".")
        num = match.group("num")

        try:
            padded_num = str(int(num)).zfill(4)
        except ValueError as exc:
            raise ValueError(f"Sample number '{num}' in '{raw}' is not numeric.") from exc

        return f"{base}.{padded_num}"

    @classmethod
    def normalize_sample_column(
        cls,
        df: pd.DataFrame,
        column: str = "name",
        *,
        inplace: bool = False,
    ) -> pd.DataFrame:
        """
        Normalize a sample-name column to `{name}.####` format without modifying other columns.

        Args:
            df: DataFrame containing the column.
            column: Column name to normalize.
            inplace: If True, mutate df in place; otherwise return a copy.

        Returns:
            pd.DataFrame: DataFrame with normalized sample names.
        """
        target = df if inplace else df.copy()
        target[column] = target[column].astype(str).apply(cls.normalize_sample_name)
        return target

    def extract_sig_entries(self):
        assert hasattr(self, "df") and hasattr(self, "name_col"), "Call split_columns first."
        names = self.df[self.name_col].astype(str).tolist()
        out = []
        for i, n in enumerate(names):
            try:
                normalized = self.normalize_sample_name(n)
                base_part, number_part = normalized.rsplit(".", 1)
                number_value = int(number_part)
                self.df.at[i, self.name_col] = normalized
                out.append(
                    self.SigEntry(index=i, base_name=base_part, number=number_value)
                )
            except ValueError:
                warnings.warn(f"Unable to normalize sample name '{n}' at index {i}.", UserWarning)
                out.append(
                    self.SigEntry(index=i, base_name=n, number=None)
                )
        self.entries: List[self.SigEntry] = out
        return self

    # ---------- Grouping ----------
    @staticmethod
    def _ensure_iterable_group(g: Union[int, Iterable[int]]) -> Iterable[int]:
        return (g,) if isinstance(g, int) else g

    def group_by(self, groups: Sequence[Union[int, Iterable[int]]], *, by: Literal["number", "index"] = "number"):
        assert hasattr(self, "entries"), "Call extract_sig_entries first."

        # Clean warning format
        def _simple_warn_format(message, category, filename, lineno, line=None):
            return f"{category.__name__}: {message}\n"
        warnings.formatwarning = _simple_warn_format

        available_values = {getattr(e, by) for e in self.entries}
        lookup = {}
        for e in self.entries:
            key = getattr(e, by)
            lookup.setdefault(key, []).append(e)

        grouped: List[List[self.SigEntry]] = []
        used_values = set()

        for g in groups:
            vals = self._ensure_iterable_group(g)
            bucket: List[self.SigEntry] = []
            for val in vals:
                if val not in available_values:
                    warnings.warn(f"⚠️ Cannot find {by}={val}", UserWarning)
                else:
                    bucket.extend(lookup[val])
                    used_values.add(val)
            grouped.append(bucket)

        # find entries not grouped
        uncovered_vals = available_values - used_values
        ungrouped_entries = [e for e in self.entries if getattr(e, by) in uncovered_vals]
        if ungrouped_entries:
            warnings.warn(
                f"⚠️ Entries {[getattr(e, by) for e in ungrouped_entries]} do not belong to any group",
                UserWarning
            )

        self.grouped_entries: List[List[self.SigEntry]] = grouped
        self.ungrouped_entries: List[self.SigEntry] = ungrouped_entries
        return self

    # ---------- Averaging ----------
    @staticmethod
    def _select_numeric_cols(df: pd.DataFrame, cols: Optional[Iterable[str]]) -> List[str]:
        return list(cols) if cols is not None else list(df.select_dtypes(include="number").columns)

    @staticmethod
    def _validate_group_indices(df: pd.DataFrame, group: Sequence["SVCDataProcessor.SigEntry"], group_id: int) -> None:
        n = len(df)
        bad = [e.index for e in group if e.index < 0 or e.index >= n]
        if bad:
            raise IndexError(f"Group {group_id} has out-of-bounds indices {bad} for DataFrame with {n} rows.")

    @staticmethod
    def _row_indices(group: Sequence["SVCDataProcessor.SigEntry"]) -> List[int]:
        return [e.index for e in group]

    @staticmethod
    def _format_indices_display(row_idxs: Sequence[int], index_base: int) -> str:
        if index_base not in (0, 1):
            raise ValueError("index_base must be 0 or 1.")
        indices = ",".join(str(i + index_base) for i in row_idxs)
        return f"rows[{indices}]"

    @staticmethod
    def _pick_sample_name(df: pd.DataFrame, name_col: str, group: Sequence["SVCDataProcessor.SigEntry"], row_idxs: Sequence[int], strategy: str = "base_first") -> str:
        base_names = [e.base_name for e in group if e.base_name]
        first_row_name = str(df.iloc[row_idxs[0]][name_col])
        if strategy == "first_cell":
            return first_row_name
        if strategy == "concat_base":
            seen, uniq = set(), []
            for b in base_names:
                if b not in seen:
                    seen.add(b)
                    uniq.append(b)
            return ";".join(uniq) if uniq else first_row_name
        # default: base_first
        if base_names:
            unique_bases = set(base_names)
            if len(unique_bases) > 1:
                warnings.warn(
                    f"Group mixes base names {sorted(unique_bases)}; using '{base_names[0]}' (strategy='base_first').",
                    UserWarning
                )
            first_number = next((e.number for e in group if e.number is not None), None)
            if first_number is not None:
                return f"{base_names[0]}.{str(first_number).zfill(4)}"
            return base_names[0]
        return first_row_name
    
    @staticmethod
    def _generate_sample_name_with_min(base_name: str, group: Sequence["SVCDataProcessor.SigEntry"]) -> str:
        """
        Generate sample name by combining base name with minimum number of group.
        
        Args:
            base_name (str): The base name to use (e.g., 'AVIRIS1')
            group (Sequence[SigEntry]): The group of SigEntry objects
            
        Returns:
            str: Generated sample name (e.g., 'AVIRIS1_1' for group numbers [1,2,3])
        """
        # Extract numbers from the group, filtering out None values
        numbers = [e.number for e in group if e.number is not None]
        
        if not numbers:
            # If no numbers found, return just the base name
            return base_name
        
        # Find minimum number in the group
        min_number = min(numbers)
        return f"{base_name}_{min_number}"

    @staticmethod
    def _aggregate_rows(
        df: pd.DataFrame,
        row_idxs: Sequence[int],
        cols: Sequence[str],
        method: Literal["mean", "median", "sum", "min", "max"],
    ) -> pd.DataFrame:
        subset = df.iloc[row_idxs][list(cols)]
        if method == "mean":
            aggregated = subset.mean(numeric_only=True, skipna=True)
        elif method == "median":
            aggregated = subset.median(numeric_only=True, skipna=True)
        elif method == "sum":
            aggregated = subset.sum(numeric_only=True, skipna=True)
        elif method == "min":
            aggregated = subset.min(numeric_only=True, skipna=True)
        elif method == "max":
            aggregated = subset.max(numeric_only=True, skipna=True)
        else:
            raise ValueError(f"Unsupported aggregation method '{method}'.")
        return aggregated.to_frame().T

    def average_groups(
        self,
        *,
        cols: Optional[Iterable[str]] = None,
        index_base: int = 1,
        name_strategy: str = "base_first",
        base_name: Optional[str] = None,
        agg_method: Literal["mean", "median", "sum", "min", "max"] = "mean",
        override_names: Optional[Sequence[Optional[str]]] = None,
    ):
        assert hasattr(self, "df") and hasattr(self, "grouped_entries") and hasattr(self, "wavelength_cols") and hasattr(self, "name_col"), "Run previous steps first."

        use_cols = self._select_numeric_cols(self.df, cols or self.wavelength_cols)
        name_col = self.name_col

        if override_names is not None and len(override_names) != len(self.grouped_entries):
            raise ValueError("override_names length must match number of groups.")

        out_rows = []
        for g_id, group in enumerate(self.grouped_entries, start=1):
            if not group:
                warnings.warn(f"Empty group at position {g_id}; skipping.", UserWarning)
                continue
            self._validate_group_indices(self.df, group, g_id)
            row_idxs = self._row_indices(group)
            
            # Choose naming strategy
            override_name = None
            if override_names:
                override_name = override_names[g_id - 1]

            if override_name:
                sample_name = override_name
            elif base_name is not None:
                sample_name = self._generate_sample_name_with_min(base_name, group)
            else:
                sample_name = self._pick_sample_name(self.df, name_col, group, row_idxs, name_strategy)
            
            averaged = self._aggregate_rows(self.df, row_idxs, use_cols, agg_method)
            
            # Create grouping numbers string from the group's numbers
            group_numbers = [str(e.number) for e in group if e.number is not None]
            grouping_str = ",".join(group_numbers) if group_numbers else ""
            
            averaged.insert(0, "row_indices", self._format_indices_display(row_idxs, index_base))
            averaged.insert(0, "grouping", grouping_str)
            averaged.insert(0, "name", sample_name)
            
            out_rows.append(averaged)

        self.grouped_df: pd.DataFrame = pd.concat(out_rows, ignore_index=True) if out_rows else pd.DataFrame()
        return self

    # ---------- Ungrouped summary ----------
    @staticmethod
    def ungrouped_entries_to_df(ungrouped: List["SVCDataProcessor.SigEntry"]) -> pd.DataFrame:
        if not ungrouped:
            return pd.DataFrame(columns=["index", "number", "base_name"])
        return pd.DataFrame([{"index": e.index, "number": e.number, "base_name": e.base_name} for e in ungrouped])

    def ungrouped_as_df(self):
        self.ungrouped_df = self.ungrouped_entries_to_df(getattr(self, "ungrouped_entries", []) or [])
        return self

    # ---------- Combine grouped + ungrouped ----------
    def concat_grouped_and_ungrouped(
        self,
        *,
        ungrouped_mode: Literal["raw", "empty"] = "raw",
        index_base: int = 1
    ):
        """
        Stack self.grouped_df with ungrouped entries (raw spectra or empty spectral cells).
        """
        assert hasattr(self, "grouped_df"), "Call average_groups first."
        assert hasattr(self, "ungrouped_entries"), "Call group_by first to populate ungrouped_entries."
        assert hasattr(self, "df") and hasattr(self, "wavelength_cols") and hasattr(self, "name_col"),                 "Ensure load_csv/split_columns ran."

        grouped = self.grouped_df.copy()

        rows = []
        for e in (self.ungrouped_entries or []):
            row = {col: None for col in grouped.columns}
            row["name"] = e.base_name or str(self.df.iloc[e.index][self.name_col])
            row["row_indices"] = self._format_indices_display([e.index], index_base)
            row["grouping"] = str(e.number) if e.number is not None else ""

            if ungrouped_mode == "raw":
                for col in grouped.columns:
                    if col in ("name", "row_indices", "grouping"):
                        continue
                    if col in self.df.columns:
                        row[col] = self.df.iloc[e.index][col]
            rows.append(row)

        ungrouped_df_aligned = pd.DataFrame(rows, columns=grouped.columns) if rows else pd.DataFrame(columns=grouped.columns)
        self.final_df = pd.concat([grouped, ungrouped_df_aligned], ignore_index=True)
        return self

    # ---------- Pretty prints (groups + ungrouped) ----------
    def debug_print_groups(self):
        """Print groups and ungrouped entries with clear headers and spacing."""
        assert hasattr(self, "grouped_entries"), "Call group_by first."

        print("#### Group Entries ####\n")
        print("Number of groups:", len(self.grouped_entries), "\n")

        for gi, group in enumerate(self.grouped_entries, start=1):
            print(f"##### Group {gi} #####")
            if not group:
                print(" (empty)\n")
                continue
            for e in group:
                print(f" index={e.index}, number={e.number}, base_name={e.base_name}")
            print()

        print("##### Ungrouped Entries #####")
        if getattr(self, "ungrouped_entries", None):
            for e in self.ungrouped_entries:
                print(f" index={e.index}, number={e.number}, base_name={e.base_name}")
        else:
            print(" None")
        print()

    # ---------- Save ----------
    def save_csv(self, out_path: str):
        assert hasattr(self, "grouped_df"), "Call average_groups first."
        self.grouped_df.to_csv(out_path, index=False)
        return self


class SigSpectraAverager:
    """
    Helper facade around SVCDataProcessor that normalizes sample names and averages spectra.
    """

    def __init__(self, df: pd.DataFrame, sample_col: str = "sample_name"):
        self.sample_col = sample_col

        working_df = df.copy()
        if sample_col != "name":
            if sample_col not in working_df.columns:
                raise KeyError(f"Column '{sample_col}' not found in DataFrame.")
            working_df = working_df.rename(columns={sample_col: "name"})

        self.dataframe = SVCDataProcessor.normalize_sample_column(working_df, column="name", inplace=False)
        self.processor = SVCDataProcessor()
        self.processor.df = self.dataframe
        self.processor.split_columns(name_col="name")
        self.processor.extract_sig_entries()

    @classmethod
    def from_csv(cls, file_path: str, sample_col: str = "sample_name", **kwargs) -> "SigSpectraAverager":
        """
        Instantiate the averager from a CSV file containing spectra.

        Args:
            file_path: Path to the spectra CSV.
            sample_col: Column storing sample names.
            **kwargs: Additional keyword arguments passed to pandas.read_csv.

        Returns:
            SigSpectraAverager: Configured instance ready for grouping/averaging.
        """
        df = pd.read_csv(file_path, **kwargs)
        return cls(df, sample_col=sample_col)

    @staticmethod
    def _normalize_groups(groups: Sequence[Union[int, Iterable[int]]]) -> List[dict]:
        normalized: List[dict] = []
        for g in groups:
            custom_name: Optional[str] = None

            if isinstance(g, GroupSpec):
                members_source = g.members
                custom_name = g.name
            elif hasattr(g, "_fields"):
                custom_name = getattr(g, "name", None)
                if hasattr(g, "members"):
                    members_source = getattr(g, "members")
                else:
                    members_source = [getattr(g, field) for field in g._fields if field != "name"]
            elif hasattr(g, "members") and isinstance(getattr(g, "members"), Iterable):
                members_source = getattr(g, "members")
                custom_name = getattr(g, "name", None)
            elif isinstance(g, Iterable) and not isinstance(g, (str, bytes)):
                members_source = g
                custom_name = getattr(g, "name", None) if hasattr(g, "name") else None
            else:
                members_source = (g,)

            # Normalize members_source into a tuple of ints
            if isinstance(members_source, Iterable) and not isinstance(members_source, (str, bytes)):
                flattened: List[int] = []
                for value in members_source:
                    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                        flattened.extend(int(v) for v in value)
                    else:
                        flattened.append(int(value))
                values = tuple(flattened) if flattened else (int(members_source),)
            else:
                values = (int(members_source),)

            normalized.append({"members": values, "name": custom_name})
        return normalized

    def aggregate(
        self,
        groups: Sequence[Union[int, Iterable[int]]],
        method: Optional[Literal["mean", "median", "sum", "min", "max"]] = "mean",
        *,
        index_base: int = 1,
        name_strategy: str = "base_first",
        base_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Average spectra for the provided groups and return a new DataFrame.

        Args:
            groups: Sequence of tuples/iterables whose values map to the four-digit sample IDs.
            method: Aggregation method to apply (defaults to arithmetic mean). Pass ``None`` to skip
                aggregation and return the original spectra rows untouched.
            index_base: Display base for index reporting (1-based by default).
            name_strategy: Strategy forwarded to SVCDataProcessor.average_groups.
            base_name: Optional base name override for generated sample names.

        Returns:
            pd.DataFrame: Averaged spectra rows (or the original rows when ``method`` is ``None``).
        """
        normalized_groups = self._normalize_groups(groups)
        member_sets = [spec["members"] for spec in normalized_groups]
        custom_names = [spec["name"] for spec in normalized_groups]

        self.processor.group_by(member_sets, by="number")

        if method is None:
            # No aggregation requested: still record grouping but retain original spectra rows.
            grouped_frames = []
            for name_spec, members in zip(normalized_groups, member_sets):
                entries = []
                for member in members:
                    entries.extend(self.processor._ensure_iterable_group(member))
                # Map member numbers back to row indices
                rows = []
                for entry in self.processor.entries:
                    if entry.number in members:
                        rows.append(entry.index)
                if not rows:
                    continue
                subset = self.processor.df.iloc[rows].copy()
                override_name = name_spec.get("name")
                if override_name:
                    subset["name"] = override_name
                grouped_frames.append(subset)
            return pd.concat(grouped_frames, ignore_index=True) if grouped_frames else pd.DataFrame()

        self.processor.average_groups(
            cols=self.processor.wavelength_cols,
            index_base=index_base,
            name_strategy=name_strategy,
            base_name=base_name,
            agg_method=method,
            override_names=custom_names,
        )
        return self.processor.grouped_df.copy()


def find_spectra_by_name(
    dataframes: Sequence[pd.DataFrame],
    search_key: str,
    *,
    name_column: str = "name",
    case_sensitive: bool = False,
    exact_match: bool = False,
) -> pd.DataFrame:
    """
    Search across multiple spectra DataFrames for rows whose name column matches the search key.

    Args:
        dataframes: Iterable of pandas DataFrames containing spectra (each must have `name_column`).
        search_key: String to match against the name column.
        name_column: Column that stores the spectra identifier (defaults to ``"name"``).
        case_sensitive: Whether to treat the match as case-sensitive.
        exact_match: When True, match only names equal to the search key; otherwise substring search.

    Returns:
        pd.DataFrame: Concatenated matches, including a `_source_index` column indicating which
        input DataFrame the row came from. Returns an empty DataFrame if no rows match.
    """
    if not search_key:
        raise ValueError("search_key must be a non-empty string.")

    results: List[pd.DataFrame] = []
    for idx, df in enumerate(dataframes):
        if name_column not in df.columns:
            raise KeyError(f"DataFrame at position {idx} lacks the '{name_column}' column.")

        names = df[name_column].astype(str)
        if exact_match:
            mask = names.eq(search_key) if case_sensitive else names.str.lower().eq(search_key.lower())
        else:
            mask = names.str.contains(
                search_key if case_sensitive else re.escape(search_key),
                case=case_sensitive,
                regex=not exact_match,
                na=False,
            )

        subset = df.loc[mask]
        if not subset.empty:
            annotated = subset.copy()
            annotated.insert(0, "_source_index", idx)
            results.append(annotated)

    if not results:
        if dataframes:
            base_cols = list(dataframes[0].columns)
            return pd.DataFrame(columns=["_source_index"] + base_cols)
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)
