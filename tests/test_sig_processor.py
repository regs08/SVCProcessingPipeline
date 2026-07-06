from __future__ import annotations

import shutil
from pathlib import Path

from pipeline.sig_processor import SigFileProcessor


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sig_inputs"


def test_process_single_file_truncates_at_end_line(tmp_path: Path) -> None:
    output = tmp_path / "bronze_a.sig"
    processor = SigFileProcessor(correction_type="bronze")

    processor._process_single_file(
        FIXTURE_DIR / "bronze_a.sig",
        output,
        "2520.4",
    )

    text = output.read_text()
    assert "2520.4 0 0 20.0" in text
    assert "2521.0 0 0 21.0" not in text


def test_get_supported_correction_types_reflects_injected_table() -> None:
    default_processor = SigFileProcessor(correction_type="bronze")
    assert set(default_processor.get_supported_correction_types()) == {"bronze", "silver"}

    custom_processor = SigFileProcessor(
        correction_value="9999.0",
        correction_types={"bronze": "2520.4", "custom_sensor": "9999.0"},
        instrument_numbers={"bronze": "2212118", "custom_sensor": "0000000"},
    )
    assert set(custom_processor.get_supported_correction_types()) == {"bronze", "custom_sensor"}


def test_instrument_consistency_reports_consistent_bronze_folder(tmp_path: Path) -> None:
    for name in ("bronze_a.sig", "bronze_b.sig"):
        shutil.copy2(FIXTURE_DIR / name, tmp_path / name)

    result = SigFileProcessor(correction_type="bronze").check_instrument_consistency(str(tmp_path))

    assert result["consistent"] is True
    assert result["total_files"] == 2
    assert result["instrument_name"] == "Bronze"
    assert result["warnings"] == []


def test_instrument_consistency_reports_mixed_instruments(tmp_path: Path) -> None:
    for name in ("bronze_a.sig", "silver.sig"):
        shutil.copy2(FIXTURE_DIR / name, tmp_path / name)

    result = SigFileProcessor(correction_type="bronze").check_instrument_consistency(str(tmp_path))

    assert result["consistent"] is False
    assert result["instrument"] is None
    assert result["instrument_name"] == "Mixed"
    assert len(result["files_by_instrument"]) == 2
    assert result["warnings"]


def test_unknown_instrument_is_reported_without_crashing(tmp_path: Path) -> None:
    shutil.copy2(FIXTURE_DIR / "unknown.sig", tmp_path / "unknown.sig")

    result = SigFileProcessor(correction_type="bronze").check_instrument_consistency(str(tmp_path))

    assert result["consistent"] is True
    assert result["instrument_name"] == "Unknown"
    assert result["warnings"] == []
