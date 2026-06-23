from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pipeline.run_config import RunConfig
from pipeline.sig_processor import SigFileProcessor


def _logger() -> logging.Logger:
    return logging.getLogger("tests.run_config")


def test_resolve_path_finds_bare_config_name(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "demo.json"
    config_path.write_text("{}")

    assert RunConfig._resolve_path(tmp_path, "demo") == config_path


def test_placeholder_guard_exits_with_guidance(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config = RunConfig(
        {"sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>"},
        path=config_path,
        base_dir=tmp_path,
        logger=_logger(),
    )

    with pytest.raises(SystemExit, match="placeholder"):
        config.ensure_no_placeholder(None)


def test_input_directories_accepts_semicolon_string(tmp_path: Path) -> None:
    config = RunConfig(
        {"sig_input_dirs": "a;b ; c"},
        path=tmp_path / "config.json",
        base_dir=tmp_path,
        logger=_logger(),
    )

    assert config.input_directories() == [Path("a"), Path("b"), Path("c")]


def test_processing_defaults_are_complete(tmp_path: Path) -> None:
    config = RunConfig({}, path=tmp_path / "config.json", base_dir=tmp_path, logger=_logger())

    assert config.processing_params() == {
        "band_min": 400,
        "band_max": 2500,
        "resample_fwhm_nm": 10.0,
        "splice_interp_wvl": (5.0, 2.0),
        "fixed_sensor": 2,
    }


def test_apply_sensor_calibrations_prefers_inline_instrument_block(tmp_path: Path) -> None:
    original_types = dict(SigFileProcessor.DEFAULT_CORRECTION_TYPES)
    original_serials = dict(SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS)
    config = RunConfig(
        {"instrument": {"bronze": {"end_line": "2520.4", "serial": "2212118"}}},
        path=tmp_path / "config.json",
        base_dir=tmp_path,
        logger=_logger(),
    )

    try:
        config.apply_sensor_calibrations(tmp_path)
        assert SigFileProcessor.DEFAULT_CORRECTION_TYPES["bronze"] == "2520.4"
        assert SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS["bronze"] == "2212118"
    finally:
        SigFileProcessor.DEFAULT_CORRECTION_TYPES = original_types
        SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS = original_serials


def test_load_reports_invalid_json(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "broken.json"
    config_path.write_text("{")

    with pytest.raises(SystemExit, match="not valid JSON"):
        RunConfig.load(tmp_path, "broken", _logger())


def test_settings_for_resolves_output_paths(tmp_path: Path) -> None:
    data = {
        "processed_dir": "sig_processed",
        "resampled_dir": "sig_resampled",
        "output_dir": "pipeline_outputs",
        "summary_csv_name": "processed_sig_summary.csv",
        "merged_csv_name": "merged_spectra.csv",
    }
    config = RunConfig(data, path=tmp_path / "config.json", base_dir=tmp_path, logger=_logger())

    settings = config.settings_for(Path("example_input"), verbose=True)

    assert settings.source_name == "example_input"
    assert settings.processed_dir == tmp_path / "pipeline_outputs/sig_processed/example_input"
    assert settings.resampled_dir == tmp_path / "pipeline_outputs/sig_resampled/example_input"
    assert settings.summary_csv.name == "example_input_processed_sig_summary.csv"
    assert settings.merged_csv_name == "example_input_merged_spectra.csv"
