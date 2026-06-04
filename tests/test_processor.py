from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pipeline.processor import GroupSpec, SVCDataProcessor, SigSpectraAverager


def test_normalize_sample_name_pads_trailing_number() -> None:
    assert SVCDataProcessor.normalize_sample_name("leaf.3.sig") == "leaf.0003"
    assert SVCDataProcessor.normalize_sample_name("leaf3") == "leaf.0003"


def test_processor_sequence_guards_use_runtime_errors() -> None:
    with pytest.raises(RuntimeError, match="Call load_csv first"):
        SVCDataProcessor().split_columns()


def test_group_spec_from_csv_skips_reference_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "groups.csv"
    csv_path.write_text("scan_id,name,reference\n1,leaf_a,\n2,reference,true\n3,leaf_b,\n")

    groups = GroupSpec.from_csv(csv_path, return_namedtuple=False)

    assert groups == [GroupSpec((1,), "leaf_a"), GroupSpec((3,), "leaf_b")]


def test_sig_spectra_averager_computes_group_mean() -> None:
    df = pd.DataFrame(
        {
            "sample_name": ["leaf.0001", "leaf.0002", "leaf.0003"],
            "400": [1.0, 3.0, 10.0],
            "401": [2.0, 4.0, 20.0],
        }
    )

    with pytest.warns(UserWarning, match="do not belong"):
        averaged = SigSpectraAverager(df).aggregate([(1, 2)], index_base=0)

    assert averaged.loc[0, "name"] == "leaf.0001"
    assert averaged.loc[0, "grouping"] == "1,2"
    assert averaged.loc[0, "row_indices"] == "rows[0,1]"
    assert averaged.loc[0, "400"] == pytest.approx(2.0)
    assert averaged.loc[0, "401"] == pytest.approx(3.0)


def test_concat_grouped_and_ungrouped_can_keep_raw_rows() -> None:
    processor = SVCDataProcessor()
    processor.df = pd.DataFrame(
        {
            "name": ["leaf.0001", "leaf.0002", "leaf.0003"],
            "400": [1.0, 3.0, 10.0],
            "401": [2.0, 4.0, 20.0],
        }
    )

    with pytest.warns(UserWarning, match="do not belong"):
        (
            processor.split_columns(name_col="name")
            .extract_sig_entries()
            .group_by([(1, 2)], by="number")
            .average_groups(index_base=0)
            .concat_grouped_and_ungrouped(ungrouped_mode="raw", index_base=0)
        )

    assert list(processor.final_df["name"]) == ["leaf.0001", "leaf"]
    assert processor.final_df.loc[1, "400"] == 10.0
