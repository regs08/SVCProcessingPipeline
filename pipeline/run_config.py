"""Run-configuration loading for the SIG processing pipeline.

``RunConfig`` encapsulates everything about *what* a run should do: locating and
parsing the run-config JSON, validating it, expanding input directories,
applying sensor calibrations, reading the optional ``processing`` block, and
building the per-directory :class:`PipelineSettings` the orchestration consumes.

The orchestration that *uses* these settings lives in ``pipeline/cli.py``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sig_processor import SigFileProcessor

# Reference snapshots of SigFileProcessor's built-in calibration tables, used as
# the fallback level of `_resolve_calibrations`'s priority order below.
_BUILTIN_SENSOR_CALIBRATIONS = dict(SigFileProcessor.DEFAULT_CORRECTION_TYPES)
_BUILTIN_INSTRUMENT_NUMBERS  = dict(SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS)

# Parity-verified defaults — deviating from these invalidates the R/spectrolab parity claim.
_PARITY_DEFAULTS: dict[str, Any] = {
    "band_min":          400,
    "band_max":          2500,
    "resample_fwhm_nm":  10.0,
    "splice_interp_wvl": [5.0, 2.0],
    "fixed_sensor":      2,
}

_PLACEHOLDER = "<PATH_TO_SIG_INPUT_ROOT>"

# Starter template written by `svc-pipeline --init-config`. Mirrors the
# repo's own config/config.json — keep the two in sync if either changes.
_STARTER_CONFIG_TEMPLATE: dict[str, Any] = {
    "sig_input_dir": _PLACEHOLDER,
    "process_all_subdirs": True,
    "processed_dir": "sig_processed",
    "resampled_dir": "sig_resampled",
    "output_dir": "pipeline_outputs",
    "summary_csv_name": "processed_sig_summary.csv",
    "merged_csv_name": "merged_spectra.csv",
    "end_line_overrides": {},
    "instrument": {
        "bronze": {"end_line": "2520.4", "serial": "2212118"},
        "silver": {"end_line": "2517.9", "serial": "1202103"},
    },
    "processing": dict(_PARITY_DEFAULTS),
}


def _resolve_under(base: Path, value: str) -> Path:
    """Resolve ``value`` against ``base`` unless it is already absolute."""
    path_obj = Path(value).expanduser()
    if path_obj.is_absolute():
        return path_obj
    return base / path_obj


@dataclass(frozen=True)
class PipelineSettings:
    """Fully-resolved inputs/outputs for a single input directory."""

    source_name: str
    input_dir: Path
    processed_dir: Path
    resampled_dir: Path
    summary_csv: Path
    merged_csv_name: str
    end_line_overrides: dict[str, str]
    verbose: bool
    processing_params: dict
    correction_types: dict[str, str]
    instrument_numbers: dict[str, str]
    groups_csv: Path | None
    group_agg_method: str
    grouped_csv_name: str


class RunConfig:
    """A parsed pipeline run configuration and everything derived from it."""

    def __init__(
        self,
        data: dict[str, Any],
        *,
        path: Path,
        base_dir: Path,
        logger: logging.Logger,
    ) -> None:
        self.data = data
        self.path = path
        self.base_dir = base_dir
        self._logger = logger
        self._processing_params: dict[str, Any] | None = None

    # ── construction ─────────────────────────────────────────────────────────

    @classmethod
    def load(cls, base_dir: Path, value: str, logger: logging.Logger) -> "RunConfig":
        """Resolve ``value`` to a config file, parse it, and return a RunConfig."""
        path = cls._resolve_path(base_dir, value)
        data = cls._read_json(path)
        logger.info("Using config: %s", path)
        return cls(data, path=path, base_dir=base_dir, logger=logger)

    @classmethod
    def write_starter_config(cls, base_dir: Path, *, filename: str = "config.json") -> Path:
        """Write a starter ``config/<filename>`` under ``base_dir`` and return its path.

        Refuses to overwrite an existing file, so re-running this never clobbers
        edits you've already made.
        """
        target = base_dir / "config" / filename
        if target.exists():
            raise SystemExit(
                f"{target} already exists — not overwriting.\n"
                f"  Edit it directly, or remove it first to regenerate the starter template."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w") as handle:
            json.dump(_STARTER_CONFIG_TEMPLATE, handle, indent=2)
            handle.write("\n")
        return target

    @staticmethod
    def _resolve_path(base_dir: Path, value: str) -> Path:
        """Resolve a run-config argument with friendly fallbacks.

        Tries, in order: the path as given (relative to ``base_dir``, i.e. the
        current working directory), the same name under ``config/``, and the
        same again with a .json suffix appended. Absolute paths are used as-is.
        """
        raw = Path(value).expanduser()
        if raw.is_absolute():
            candidates = [raw]
        else:
            names = [raw]
            if raw.suffix == "":
                names.append(raw.with_suffix(".json"))
            candidates = []
            for name in names:
                candidates.append(base_dir / name)             # e.g. ./config.json
                candidates.append(base_dir / "config" / name)  # e.g. ./config/config.json
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        available = sorted(p.name for p in (base_dir / "config").glob("*.json"))
        raise SystemExit(
            f"Config not found: '{value}'.\n"
            f"  Tried: {', '.join(str(c) for c in candidates)}\n"
            f"  Available in config/: {', '.join(available) or '(none)'}\n"
            f"  Usage: svc-pipeline [CONFIG] [--step ...] [--verbose]"
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            with path.expanduser().open() as handle:
                data = json.load(handle)
        except FileNotFoundError as exc:
            raise SystemExit(f"Config file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Config is not valid JSON ({path}): {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Config must be a JSON object: {path}")
        return data

    # ── validation ───────────────────────────────────────────────────────────

    def ensure_no_placeholder(self, input_dir_override: str | None) -> None:
        """Fail fast if the template's placeholder input path was never edited."""
        if input_dir_override:
            return
        sig_input_dirs = self.data.get("sig_input_dirs") or []
        if isinstance(sig_input_dirs, str):
            sig_input_dirs = [sig_input_dirs]
        raw_inputs = [self.data.get("sig_input_dir"), *sig_input_dirs]
        if any(value == _PLACEHOLDER for value in raw_inputs if value):
            raise SystemExit(
                f'{self.path} still contains the placeholder "{_PLACEHOLDER}".\n'
                f'  Edit "sig_input_dir" to point at your .sig data directory, '
                f"or pass --input-dir <path>."
            )

    # ── derived values ───────────────────────────────────────────────────────

    def input_directories(self) -> list[Path]:
        """Expand the config into the list of input directories to process."""
        explicit_dirs = self.data.get("sig_input_dirs")
        if explicit_dirs:
            if isinstance(explicit_dirs, str):
                candidates = [item.strip() for item in explicit_dirs.split(";") if item.strip()]
            else:
                candidates = list(explicit_dirs)
            return [Path(entry).expanduser() for entry in candidates]

        base_dir_str = self.data.get("sig_input_dir")
        if not base_dir_str:
            raise ValueError("Configuration must provide 'sig_input_dir' or 'sig_input_dirs'.")
        base_dir = Path(str(base_dir_str)).expanduser()

        if not bool(self.data.get("process_all_subdirs")):
            return [base_dir]
        if not base_dir.is_dir():
            return [base_dir]

        subdirs: list[Path] = []
        for child in sorted(base_dir.iterdir()):
            if child.is_dir() and any(gc.suffix.lower() == ".sig" for gc in child.glob("*.sig")):
                subdirs.append(child)
        return subdirs or [base_dir]

    def processing_params(self) -> dict[str, Any]:
        """Resolve the optional ``processing`` block (cached).

        Every key in ``_PARITY_DEFAULTS`` is always present in the result, so
        callers never need their own fallback defaults. The one-time parity
        warning for any non-default value is emitted on first call only.
        """
        if self._processing_params is None:
            self._processing_params = self._read_processing_params()
        return self._processing_params

    def _read_processing_params(self) -> dict[str, Any]:
        block = self.data.get("processing") or {}
        params: dict[str, Any] = {}
        for key, default in _PARITY_DEFAULTS.items():
            if key in block:
                value = block[key]
                if isinstance(value, list):  # normalise list → tuple for interp_wvl
                    value = tuple(value)
                params[key] = value
                default_cmp = tuple(default) if isinstance(default, list) else default
                if value != default_cmp:
                    self._logger.warning(
                        "processing.%s = %s differs from parity-verified default %s — "
                        "R/spectrolab parity is no longer guaranteed.",
                        key, value, default,
                    )
            else:
                params[key] = tuple(default) if isinstance(default, list) else default
        return params

    def _resolve_calibrations(self, input_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
        """Resolve the correction-type and instrument-number tables for ``input_dir``.

        Priority: inline ``instrument`` block > ``sensor_calibration_file`` >
        auto-inferred ``config/calibrations/<input_dir_name>.json`` > built-in
        defaults. Pure — returns plain dicts and never touches
        ``SigFileProcessor.DEFAULT_CORRECTION_TYPES``/``DEFAULT_INSTRUMENT_NUMBERS``.
        """
        inline = self._instrument_block_calibrations()
        if inline is not None:
            return inline

        instrument_numbers = dict(_BUILTIN_INSTRUMENT_NUMBERS)

        explicit = self.data.get("sensor_calibration_file")
        if explicit:
            path = _resolve_under(self.base_dir, str(explicit))
            correction_types = SigFileProcessor.parse_correction_types_file(path)
            self._logger.info("Loaded sensor calibration from %s", path.resolve())
            return correction_types, instrument_numbers

        inferred = self.base_dir / "config" / "calibrations" / f"{input_dir.name}.json"
        if inferred.exists():
            correction_types = SigFileProcessor.parse_correction_types_file(inferred)
            self._logger.info("Loaded sensor calibration from %s", inferred.resolve())
            return correction_types, instrument_numbers

        self._logger.debug("No sensor calibration file found at %s; using built-in defaults.", inferred)
        return dict(_BUILTIN_SENSOR_CALIBRATIONS), instrument_numbers

    def _instrument_block_calibrations(self) -> tuple[dict[str, str], dict[str, str]] | None:
        """Resolve calibrations from the inline ``instrument`` config block, if present."""
        block = self.data.get("instrument")
        if not block:
            return None

        end_lines: dict[str, str] = {}
        serials: dict[str, str] = {}
        for sensor_type, values in block.items():
            key = str(sensor_type).strip().lower()
            if isinstance(values, dict):
                if "end_line" in values:
                    end_lines[key] = str(values["end_line"]).strip()
                if "serial" in values:
                    serials[key] = str(values["serial"]).strip()
            else:
                end_lines[key] = str(values).strip()  # flat {"bronze": "2520.4"} shorthand

        correction_types = {**dict(_BUILTIN_SENSOR_CALIBRATIONS), **end_lines}
        instrument_numbers = {**dict(_BUILTIN_INSTRUMENT_NUMBERS), **serials}
        if end_lines:
            self._logger.info("Instrument end-lines from config: %s", end_lines)
        if serials:
            self._logger.info("Instrument serials from config: %s", serials)
        return correction_types, instrument_numbers

    def settings_for(
        self,
        input_dir: Path,
        *,
        verbose: bool,
        groups_csv_override: str | Path | None = None,
        group_method_override: str | None = None,
    ) -> PipelineSettings:
        """Build the fully-resolved :class:`PipelineSettings` for one input directory."""
        input_dir = Path(input_dir).expanduser()
        source_name = input_dir.name or "sig_input"
        correction_types, instrument_numbers = self._resolve_calibrations(input_dir)

        output_root: Path | None = None
        if self.data.get("output_dir"):
            output_root = _resolve_under(self.base_dir, str(self.data["output_dir"]))
        base_output = output_root or self.base_dir

        processed_root = _resolve_under(base_output, str(self.data["processed_dir"]))
        resampled_root = _resolve_under(base_output, str(self.data["resampled_dir"]))

        processed_dir = processed_root / source_name
        resampled_dir = resampled_root / source_name
        summary_csv = processed_dir / f"{source_name}_{self.data['summary_csv_name']}"
        merged_csv_name = f"{source_name}_{self.data['merged_csv_name']}"

        overrides_raw = self.data.get("end_line_overrides") or {}
        end_line_overrides = {
            str(key).strip().lower(): str(value).strip()
            for key, value in overrides_raw.items()
            if key is not None
        }

        groups_csv_value = groups_csv_override or self.data.get("groups_csv")
        groups_csv = _resolve_under(self.base_dir, str(groups_csv_value)) if groups_csv_value else None
        group_agg_method = str(group_method_override or self.data.get("group_agg_method", "mean"))
        grouped_csv_name = f"{source_name}_{self.data.get('grouped_csv_name', 'grouped_spectra.csv')}"

        return PipelineSettings(
            source_name=source_name,
            input_dir=input_dir,
            processed_dir=processed_dir,
            resampled_dir=resampled_dir,
            summary_csv=summary_csv,
            merged_csv_name=merged_csv_name,
            end_line_overrides=end_line_overrides,
            verbose=verbose,
            processing_params=self.processing_params(),
            correction_types=correction_types,
            instrument_numbers=instrument_numbers,
            groups_csv=groups_csv,
            group_agg_method=group_agg_method,
            grouped_csv_name=grouped_csv_name,
        )
