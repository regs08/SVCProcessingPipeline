from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline.resampler import ProcessedSpectrum, process_sig_file, resample_spectra


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sig_inputs"


def test_process_sig_file_returns_public_intermediates() -> None:
    result = process_sig_file(
        FIXTURE_DIR / "bronze_a.sig",
        band_min=400,
        band_max=410,
    )

    assert isinstance(result, ProcessedSpectrum)
    assert result.sample_name == "bronze_a"
    assert len(result.raw_wavelengths) == len(result.raw_reflectance)
    assert len(result.segments) == 3
    assert len(result.splice_wavelengths) == 2
    assert result.corrected_wavelengths.shape == result.corrected_reflectance.shape
    assert result.output_wavelengths.tolist() == list(range(400, 411))
    assert result.output_reflectance.shape == (11,)
    assert np.isfinite(result.output_reflectance).all()


def test_process_sig_file_reports_missing_data_marker(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.sig"
    invalid.write_text("instrument= HI: 2212118 (HR-1024i)\n")

    with pytest.raises(ValueError, match="missing the required 'data=' marker"):
        process_sig_file(invalid)


def test_resample_spectra_delegates_to_single_file_path(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy2(FIXTURE_DIR / "bronze_a.sig", input_dir / "bronze_a.sig")

    single = process_sig_file(input_dir / "bronze_a.sig", band_min=400, band_max=410)
    output = resample_spectra(
        input_dir,
        tmp_path / "out",
        "merged.csv",
        band_min=400,
        band_max=410,
    )
    merged = pd.read_csv(output, index_col=0)

    assert merged.shape == (1, 11)
    np.testing.assert_allclose(
        merged.loc["bronze_a"].to_numpy(dtype=float),
        single.output_reflectance,
    )
