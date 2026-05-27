import os
from pathlib import Path
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--r-reference-csv",
        action="store",
        default=None,
        help=(
            "Path to the reference CSV produced by the R/spectrolab pipeline. "
            "Required to run the parity test. Can also be set via the R_REFERENCE_CSV env var."
        ),
    )
    parser.addoption(
        "--r-input-dir",
        action="store",
        default=None,
        help=(
            "Path to the processed .sig input directory that was used to generate the R "
            "reference CSV. Required to run the parity test. Can also be set via R_INPUT_DIR."
        ),
    )


@pytest.fixture
def r_reference_csv(request):
    """Path to the R pipeline output CSV. Test is skipped when not provided."""
    raw = request.config.getoption("--r-reference-csv") or os.environ.get("R_REFERENCE_CSV")
    if not raw:
        pytest.skip(
            "No R reference CSV supplied. "
            "Pass --r-reference-csv=<path> or export R_REFERENCE_CSV=<path>."
        )
    path = Path(raw)
    if not path.exists():
        pytest.fail(f"R reference CSV not found: {path.resolve()}")
    return path


@pytest.fixture
def r_input_dir(request):
    """Processed .sig input dir used to generate the R reference CSV. Test is skipped when not provided."""
    raw = request.config.getoption("--r-input-dir") or os.environ.get("R_INPUT_DIR")
    if not raw:
        pytest.skip(
            "No R input directory supplied. "
            "Pass --r-input-dir=<path> or export R_INPUT_DIR=<path>."
        )
    path = Path(raw)
    if not path.is_dir():
        pytest.fail(f"R input directory not found: {path.resolve()}")
    return path
