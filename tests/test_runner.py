from __future__ import annotations

import logging
from pathlib import Path

from pipeline.run_config import PipelineSettings
from pipeline.runner import Pipeline


def _settings(tmp_path: Path, input_dir: Path) -> PipelineSettings:
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

    assert result == {"summary_csv": None, "merged_csv": None}
