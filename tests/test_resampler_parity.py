"""Parity test: Python resampler output MUST match the R/spectrolab pipeline output.

How to run
----------
Supply the two required inputs (CLI flags or env vars):

    pytest tests/test_resampler_parity.py \
        --r-reference-csv=/path/to/r_output/merged_spectra.csv \
        --r-input-dir=/path/to/processed_sig_files/

Or via environment variables:

    R_REFERENCE_CSV=/path/to/r_output/merged_spectra.csv \
    R_INPUT_DIR=/path/to/processed_sig_files/ \
    pytest tests/test_resampler_parity.py

The test is skipped automatically when neither source is provided, so it never
blocks CI environments that do not have reference data available.

Tolerance
---------
spectrolab (R) and specdal (Python) implement smoothing and Gaussian convolution
in different languages / numerical libraries, so floating-point results will
diverge at sub-percent levels. The default tolerance is MAX_ABS_DIFF = 1e-3
(0.1 % reflectance). Tighten or loosen it via the MAX_RESAMPLER_DIFF env var.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from pipeline.resampler import resample_spectra

# Absolute tolerance for per-cell reflectance differences (dimensionless, 0-1 scale).
# Override with MAX_RESAMPLER_DIFF env var for site-specific calibration.
_DEFAULT_TOLERANCE = 1e-3
MAX_ABS_DIFF = float(os.environ.get("MAX_RESAMPLER_DIFF", _DEFAULT_TOLERANCE))


def _load_and_normalise(csv_path: Path) -> pd.DataFrame:
    """Read a spectra CSV and return a float DataFrame with integer wavelength columns.

    Handles both output conventions:
    - spectrolab/write_csv: first column is sample names (named or unnamed)
    - specdal/to_frame: index is sample names, columns are wavelengths
    """
    df = pd.read_csv(csv_path, index_col=0)

    # Drop any non-numeric columns that may represent metadata (e.g. leftover text col)
    numeric_cols = []
    for col in df.columns:
        try:
            float(col)
            numeric_cols.append(col)
        except (ValueError, TypeError):
            pass
    df = df[numeric_cols]

    # Normalise column names to plain integers (400, 401, …) for alignment
    df.columns = [int(float(c)) for c in df.columns]
    df.index = (df.index.astype(str).str.strip()
                    .str.removesuffix(".sig")
                    .str.removesuffix(".SIG"))
    return df.astype(float)


def test_python_output_matches_r_reference(r_reference_csv, r_input_dir, tmp_path):
    """Assert that resample_spectra() produces values equal to the R/spectrolab pipeline.

    Both pipelines must be run on the same processed .sig input directory.
    The test fails with a clear diagnostic when any cell exceeds MAX_ABS_DIFF.
    """
    output_csv = resample_spectra(r_input_dir, tmp_path, "python_merged.csv")

    r_df = _load_and_normalise(r_reference_csv)
    py_df = _load_and_normalise(output_csv)

    # ── sample alignment ──────────────────────────────────────────────────────
    shared_samples = r_df.index.intersection(py_df.index)
    r_only = set(r_df.index) - set(shared_samples)
    py_only = set(py_df.index) - set(shared_samples)

    assert len(shared_samples) > 0, (
        f"No overlapping sample names between R and Python outputs.\n"
        f"  R samples   : {sorted(r_df.index.tolist())[:10]}\n"
        f"  Python samples: {sorted(py_df.index.tolist())[:10]}"
    )

    if r_only:
        pytest.fail(
            f"R reference contains {len(r_only)} sample(s) absent from Python output: "
            f"{sorted(r_only)[:10]}"
        )
    if py_only:
        pytest.fail(
            f"Python output contains {len(py_only)} sample(s) absent from R reference: "
            f"{sorted(py_only)[:10]}"
        )

    # ── wavelength alignment ──────────────────────────────────────────────────
    shared_cols = r_df.columns.intersection(py_df.columns)
    r_missing = set(r_df.columns) - set(shared_cols)
    py_missing = set(py_df.columns) - set(shared_cols)

    assert len(shared_cols) > 0, (
        "No overlapping wavelength columns between R and Python outputs."
    )

    if r_missing:
        pytest.fail(
            f"R reference has {len(r_missing)} wavelength(s) absent from Python output "
            f"(first 10): {sorted(r_missing)[:10]}"
        )
    if py_missing:
        pytest.fail(
            f"Python output has {len(py_missing)} wavelength(s) absent from R reference "
            f"(first 10): {sorted(py_missing)[:10]}"
        )

    # ── numeric parity ────────────────────────────────────────────────────────
    r_aligned = r_df.loc[shared_samples, shared_cols]
    py_aligned = py_df.loc[shared_samples, shared_cols]

    diff = (r_aligned - py_aligned).abs()
    max_diff = float(diff.max().max())
    mean_diff = float(diff.mean().mean())

    assert max_diff <= MAX_ABS_DIFF, (
        f"Python and R pipeline outputs differ beyond tolerance "
        f"(MAX_ABS_DIFF={MAX_ABS_DIFF}).\n"
        f"  max  absolute difference : {max_diff:.6f}\n"
        f"  mean absolute difference : {mean_diff:.6f}\n"
        f"  worst sample  : {diff.max(axis=1).idxmax()}\n"
        f"  worst wavelength: {diff.max(axis=0).idxmax()} nm\n"
        f"\n"
        f"If the algorithms are intentionally different, raise the tolerance via\n"
        f"the MAX_RESAMPLER_DIFF env var or --r-reference-csv with updated data.\n"
        f"If they should be equal, check pipeline/resampler.py Gaussian sigma,\n"
        f"Savitzky-Golay parameters, and stitch method against merge_resample_sig.R."
    )
