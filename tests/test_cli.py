from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pipeline.cli import _parse_args, main


def _write_config(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data))
    return path


def test_parse_args_step_and_input_dir_default_to_all_and_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["svc-pipeline", "config.json"])

    args = _parse_args()

    assert args.config == "config.json"
    assert args.step == "all"
    assert args.input_dir is None
    assert args.verbose is False


def test_parse_args_accepts_step_input_dir_and_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["svc-pipeline", "myconfig", "--step", "2", "--input-dir", "/some/dir", "--verbose"],
    )

    args = _parse_args()

    assert args.step == "2"
    assert args.input_dir == "/some/dir"
    assert args.verbose is True


def test_main_input_dir_override_bypasses_config_input_and_placeholder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # sig_input_dir is left as the unedited placeholder; --input-dir must
    # still work without tripping the placeholder guard.
    config_path = _write_config(
        tmp_path / "config.json",
        {
            "sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>",
            "processed_dir": "sig_processed",
            "resampled_dir": "sig_resampled",
            "output_dir": str(tmp_path / "out"),
            "summary_csv_name": "summary.csv",
            "merged_csv_name": "merged.csv",
        },
    )
    empty_input = tmp_path / "empty_input"
    empty_input.mkdir()

    monkeypatch.setattr(
        sys,
        "argv",
        ["svc-pipeline", str(config_path), "--input-dir", str(empty_input), "--step", "1"],
    )

    main()

    captured = capsys.readouterr()
    assert str(empty_input.resolve()) in captured.out
    assert "not produced" in captured.out


def test_main_exits_on_placeholder_without_input_dir_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.json", {"sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>"})

    monkeypatch.setattr(sys, "argv", ["svc-pipeline", str(config_path)])

    with pytest.raises(SystemExit, match="placeholder"):
        main()
