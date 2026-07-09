from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pipeline.cli import _parse_args, main


def _write_config(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data))
    return path


def test_help_links_to_github_repo(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["svc-pipeline", "--help"])

    with pytest.raises(SystemExit):
        _parse_args()

    assert "github.com/regs08/SVCProcessingPipeline" in capsys.readouterr().out


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


def test_parse_args_accepts_step_three_and_group_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["svc-pipeline", "--step", "3", "--groups-csv", "naming_ids/groups.csv", "--group-method", "median"],
    )

    args = _parse_args()

    assert args.step == "3"
    assert args.groups_csv == "naming_ids/groups.csv"
    assert args.group_method == "median"


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


def test_main_step_three_groups_existing_merged_csv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    groups_csv = tmp_path / "groups.csv"
    groups_csv.write_text("scan_id,name\n1,leaf_a\n2,leaf_a\n")

    config_path = _write_config(
        tmp_path / "config.json",
        {
            "sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>",
            "processed_dir": "sig_processed",
            "resampled_dir": "sig_resampled",
            "output_dir": str(tmp_path / "out"),
            "summary_csv_name": "summary.csv",
            "merged_csv_name": "merged.csv",
            "groups_csv": str(groups_csv),
        },
    )
    input_dir = tmp_path / "myinput"
    input_dir.mkdir()

    resampled_dir = tmp_path / "out" / "sig_resampled" / "myinput"
    resampled_dir.mkdir(parents=True)
    merged_csv = resampled_dir / "myinput_merged.csv"
    merged_csv.write_text("sample_name,400\nleaf.0001,1.0\nleaf.0002,3.0\n")

    monkeypatch.setattr(
        sys,
        "argv",
        ["svc-pipeline", str(config_path), "--input-dir", str(input_dir), "--step", "3"],
    )

    main()

    grouped_csv = resampled_dir / "myinput_grouped_spectra.csv"
    assert grouped_csv.exists()
    captured = capsys.readouterr()
    assert "grouped_csv" in captured.out
    assert str(grouped_csv.resolve()) in captured.out


def test_main_init_config_writes_starter_and_exits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["svc-pipeline", "--init-config"])

    main()

    written = tmp_path / "config" / "config.json"
    assert written.is_file()
    assert json.loads(written.read_text())["sig_input_dir"] == "<PATH_TO_SIG_INPUT_ROOT>"
    assert str(written.resolve()) in capsys.readouterr().out


def test_main_init_config_refuses_to_overwrite_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "config" / "config.json"
    existing.parent.mkdir()
    existing.write_text('{"already": "here"}')
    monkeypatch.setattr(sys, "argv", ["svc-pipeline", "--init-config"])

    with pytest.raises(SystemExit, match="already exists"):
        main()


def test_main_exits_on_placeholder_without_input_dir_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _write_config(tmp_path / "config.json", {"sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>"})

    monkeypatch.setattr(sys, "argv", ["svc-pipeline", str(config_path)])

    with pytest.raises(SystemExit, match="placeholder"):
        main()
