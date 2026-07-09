from __future__ import annotations

import logging
from pathlib import Path

from pipeline.run_config import PipelineSettings
from pipeline.runner import Pipeline


def _settings(
    tmp_path: Path,
    input_dir: Path,
    *,
    groups_csv: Path | None = None,
    group_agg_method: str = "mean",
) -> PipelineSettings:
    return PipelineSettings(
        source_name=input_dir.name or "input",
        input_dir=input_dir,
        processed_dir=tmp_path / "processed",
        resampled_dir=tmp_path / "resampled",
        summary_csv=tmp_path / "processed" / "summary.csv",
        merged_csv_name="merged.csv",
        end_line_overrides={},
        verbose=False,
        processing_params={
            "band_min": 400,
            "band_max": 410,
            "resample_fwhm_nm": 10.0,
            "splice_interp_wvl": (5.0, 2.0),
            "fixed_sensor": 2,
        },
        correction_types={"bronze": "2520.4", "silver": "2517.9"},
        instrument_numbers={"bronze": "2212118", "silver": "1202103"},
        groups_csv=groups_csv,
        group_agg_method=group_agg_method,
        grouped_csv_name="grouped.csv",
    )


def test_process_sig_files_returns_none_for_missing_input(tmp_path: Path) -> None:
    pipeline = Pipeline(_settings(tmp_path, tmp_path / "missing"), logging.getLogger("tests.runner"))

    assert pipeline.process_sig_files() is None


def test_process_sig_files_returns_none_for_empty_input(tmp_path: Path) -> None:
    input_dir = tmp_path / "empty"
    input_dir.mkdir()
    pipeline = Pipeline(_settings(tmp_path, input_dir), logging.getLogger("tests.runner"))

    assert pipeline.process_sig_files() is None


def test_run_step_two_without_summary_does_not_resample(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    pipeline = Pipeline(_settings(tmp_path, input_dir), logging.getLogger("tests.runner"))

    result = pipeline.run("2")

    assert result == {"summary_csv": None, "merged_csv": None, "grouped_csv": None}


def test_run_all_skips_grouping_when_groups_csv_not_configured(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    pipeline = Pipeline(_settings(tmp_path, input_dir), logging.getLogger("tests.runner"))

    result = pipeline.run("all")

    assert result["grouped_csv"] is None


def test_group_and_average_writes_grouped_csv(tmp_path: Path) -> None:
    resampled_dir = tmp_path / "resampled"
    resampled_dir.mkdir(parents=True)
    merged_csv = resampled_dir / "merged.csv"
    merged_csv.write_text("sample_name,400,401\nleaf.0001,1.0,2.0\nleaf.0002,3.0,4.0\n")

    groups_csv = tmp_path / "groups.csv"
    groups_csv.write_text("scan_id,name\n1,leaf_a\n2,leaf_a\n")

    settings = _settings(tmp_path, tmp_path / "input", groups_csv=groups_csv)
    pipeline = Pipeline(settings, logging.getLogger("tests.runner"))

    output = pipeline.group_and_average(merged_csv)

    assert output == resampled_dir / "grouped.csv"
    written = output.read_text()
    assert "leaf_a" in written
    assert "2.0" in written  # mean(1.0, 3.0)
    assert "3.0" in written  # mean(2.0, 4.0)


def test_group_and_average_missing_groups_file_returns_none(tmp_path: Path) -> None:
    resampled_dir = tmp_path / "resampled"
    resampled_dir.mkdir(parents=True)
    merged_csv = resampled_dir / "merged.csv"
    merged_csv.write_text("sample_name,400\nleaf.0001,1.0\n")

    settings = _settings(tmp_path, tmp_path / "input", groups_csv=tmp_path / "missing_groups.csv")
    pipeline = Pipeline(settings, logging.getLogger("tests.runner"))

    assert pipeline.group_and_average(merged_csv) is None


def test_run_step_three_without_merged_csv_logs_error(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    groups_csv = tmp_path / "groups.csv"
    groups_csv.write_text("scan_id,name\n1,leaf_a\n")
    pipeline = Pipeline(_settings(tmp_path, input_dir, groups_csv=groups_csv), logging.getLogger("tests.runner"))

    result = pipeline.run("3")

    assert result == {"summary_csv": None, "merged_csv": None, "grouped_csv": None}


def test_run_step_three_groups_existing_merged_csv(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    resampled_dir = tmp_path / "resampled"
    resampled_dir.mkdir(parents=True)
    merged_csv = resampled_dir / "merged.csv"
    merged_csv.write_text("sample_name,400\nleaf.0001,1.0\nleaf.0002,3.0\n")
    groups_csv = tmp_path / "groups.csv"
    groups_csv.write_text("scan_id,name\n1,leaf_a\n2,leaf_a\n")

    pipeline = Pipeline(_settings(tmp_path, input_dir, groups_csv=groups_csv), logging.getLogger("tests.runner"))

    result = pipeline.run("3")

    assert result["merged_csv"] == merged_csv
    assert result["grouped_csv"] == resampled_dir / "grouped.csv"
    assert result["grouped_csv"].exists()
