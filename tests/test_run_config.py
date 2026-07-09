from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from pipeline.run_config import RunConfig


def _logger() -> logging.Logger:
    return logging.getLogger("tests.run_config")


def test_resolve_path_finds_bare_config_name(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "demo.json"
    config_path.write_text("{}")

    assert RunConfig._resolve_path(tmp_path, "demo") == config_path


def test_write_starter_config_creates_config_json_with_placeholder(tmp_path: Path) -> None:
    target = RunConfig.write_starter_config(tmp_path)

    assert target == tmp_path / "config" / "config.json"
    data = json.loads(target.read_text())
    assert data["sig_input_dir"] == "<PATH_TO_SIG_INPUT_ROOT>"
    assert data["processing"]["band_min"] == 400


def test_write_starter_config_refuses_to_overwrite_existing(tmp_path: Path) -> None:
    existing = tmp_path / "config" / "config.json"
    existing.parent.mkdir()
    existing.write_text('{"already": "here"}')

    with pytest.raises(SystemExit, match="already exists"):
        RunConfig.write_starter_config(tmp_path)

    assert json.loads(existing.read_text()) == {"already": "here"}


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


def test_resolve_calibrations_prefers_inline_instrument_block(tmp_path: Path) -> None:
    config = RunConfig(
        {"instrument": {"bronze": {"end_line": "2520.4", "serial": "2212118"}}},
        path=tmp_path / "config.json",
        base_dir=tmp_path,
        logger=_logger(),
    )

    correction_types, instrument_numbers = config._resolve_calibrations(tmp_path)

    assert correction_types["bronze"] == "2520.4"
    assert instrument_numbers["bronze"] == "2212118"
    # Sensor types absent from the inline block still fall back to the
    # built-in defaults rather than disappearing.
    assert correction_types["silver"] == "2517.9"


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
    assert settings.correction_types["silver"] == "2517.9"
    assert settings.instrument_numbers["silver"] == "1202103"


def test_settings_for_grouping_defaults_when_unconfigured(tmp_path: Path) -> None:
    data = {
        "processed_dir": "sig_processed",
        "resampled_dir": "sig_resampled",
        "summary_csv_name": "summary.csv",
        "merged_csv_name": "merged.csv",
    }
    config = RunConfig(data, path=tmp_path / "config.json", base_dir=tmp_path, logger=_logger())

    settings = config.settings_for(Path("example_input"), verbose=False)

    assert settings.groups_csv is None
    assert settings.group_agg_method == "mean"
    assert settings.grouped_csv_name == "example_input_grouped_spectra.csv"


def test_settings_for_resolves_groups_csv_from_config(tmp_path: Path) -> None:
    data = {
        "processed_dir": "sig_processed",
        "resampled_dir": "sig_resampled",
        "summary_csv_name": "summary.csv",
        "merged_csv_name": "merged.csv",
        "groups_csv": "naming_ids/groups.csv",
        "group_agg_method": "median",
    }
    config = RunConfig(data, path=tmp_path / "config.json", base_dir=tmp_path, logger=_logger())

    settings = config.settings_for(Path("example_input"), verbose=False)

    assert settings.groups_csv == tmp_path / "naming_ids/groups.csv"
    assert settings.group_agg_method == "median"


def test_settings_for_cli_overrides_take_priority_over_config(tmp_path: Path) -> None:
    data = {
        "processed_dir": "sig_processed",
        "resampled_dir": "sig_resampled",
        "summary_csv_name": "summary.csv",
        "merged_csv_name": "merged.csv",
        "groups_csv": "naming_ids/groups.csv",
        "group_agg_method": "mean",
    }
    config = RunConfig(data, path=tmp_path / "config.json", base_dir=tmp_path, logger=_logger())

    settings = config.settings_for(
        Path("example_input"),
        verbose=False,
        groups_csv_override=tmp_path / "override_groups.csv",
        group_method_override="max",
    )

    assert settings.groups_csv == tmp_path / "override_groups.csv"
    assert settings.group_agg_method == "max"
