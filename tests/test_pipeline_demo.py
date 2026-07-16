from __future__ import annotations

import importlib
from pathlib import Path
import tomllib

import matplotlib.pyplot as plt
import nbformat
import numpy as np
import pandas as pd
import pytest

from pipeline import notebook as svc
from pipeline.processor import GroupSpec
from tests.notebook_data import FILE_COUNT, REFERENCE_INDICES, create_notebook_test_data


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "pipeline_demo.ipynb"


class DummySpectrum:
    def __init__(self, name: str, value: float, *, processed: bool = True) -> None:
        self.name = name
        self.is_processed = processed
        self.wavelengths = svc.STANDARD_WAVELENGTHS.copy()
        self.reflectance = np.full(len(svc.STANDARD_WAVELENGTHS), value, dtype=float)


class DummyCollection:
    def __init__(self, spectra: list[DummySpectrum]) -> None:
        self.spectra = spectra


def test_notebook_test_data_is_private(tmp_path: Path) -> None:
    spectra_dir = create_notebook_test_data(tmp_path / "spectra")
    sig_files = sorted(spectra_dir.glob("*.sig"))

    assert len(sig_files) == FILE_COUNT

    forbidden_headers = ("longitude=", "latitude=", "gpstime=", "time=", "site=")
    for path in sig_files:
        text = path.read_text()
        assert "instrument= HI: 2212118 (HR-1024i)" in text
        assert "integration= synthetic" in text
        assert not any(header in text.lower() for header in forbidden_headers)


def test_notebook_api_runs_end_to_end_with_sig_data(tmp_path: Path) -> None:
    spectra_dir = create_notebook_test_data(tmp_path / "spectra")
    config = svc.build_config(spectra_dir, tmp_path / "output")

    assert config.instrument == "bronze"
    assert config.end_line == "2520.4"
    config.prepare()

    collection = svc.SpectraCollection.from_config(config)
    assert len(collection) == FILE_COUNT
    collection.filter_reference_scans().filter_outliers().process()

    assert len(collection) == FILE_COUNT - len(REFERENCE_INDICES)
    for spectrum in collection.spectra:
        assert np.array_equal(spectrum.wavelengths, svc.STANDARD_WAVELENGTHS)
        assert np.isfinite(spectrum.reflectance).all()

    spectra_csv = svc.save_spectra_csv(collection, tmp_path / "output" / "spectra.csv")
    groups = [
        tuple(range(i, min(i + 2, len(collection.spectra))))
        for i in range(0, len(collection.spectra), 2)
    ]
    pairs = svc.average_pairs(collection, groups=groups)

    assert spectra_csv.exists()
    assert pairs.shape == (6, len(svc.STANDARD_WAVELENGTHS))


def test_average_pairs_checks_bounds() -> None:
    collection = DummyCollection(
        [DummySpectrum("a", 1.0), DummySpectrum("b", 3.0), DummySpectrum("c", 10.0)]
    )

    with pytest.raises(IndexError, match="out-of-range"):
        svc.average_pairs(collection, groups=[(0, 5)])


def test_average_pairs_defaults_to_valid_consecutive_groups() -> None:
    collection = DummyCollection(
        [DummySpectrum("a", 1.0), DummySpectrum("b", 3.0), DummySpectrum("c", 10.0)]
    )

    pairs = svc.average_pairs(collection)

    assert list(pairs.index) == ["pair_1", "pair_2"]
    assert pairs.loc["pair_1", 400] == pytest.approx(2.0)
    assert pairs.loc["pair_2", 400] == pytest.approx(10.0)


def test_average_pairs_requires_processed_spectra() -> None:
    collection = DummyCollection([DummySpectrum("a", 1.0, processed=False)])

    with pytest.raises(RuntimeError, match="not yet processed"):
        svc.average_pairs(collection)


def test_plot_groups_uses_named_group_labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spectra_csv = tmp_path / "spectra.csv"
    pd.DataFrame(
        {
            "sample_name": ["leaf.0000", "leaf.0001", "leaf.0011"],
            "400": [0.10, 0.20, 0.50],
            "401": [0.11, 0.21, 0.51],
        }
    ).to_csv(spectra_csv, index=False)

    groups = [
        GroupSpec(members=(0, 1), name="asymptomatic"),
        GroupSpec(members=(11,), name="symptomatic"),
    ]
    grouped = svc.average_groups(spectra_csv, groups)

    monkeypatch.setattr(plt, "show", lambda: None)
    ax = svc.plot_groups(spectra_csv, groups, grouped)
    labels = [text.get_text() for text in ax.get_legend().get_texts()]
    plt.close(ax.figure)

    assert labels == [
        "asymptomatic  (scans [0, 1])",
        "symptomatic  (scans [11])",
    ]


def test_repo_compatibility_module_reexports_installed_helpers() -> None:
    compatibility_module = importlib.import_module("notebooks.pipeline_demo.svc")

    assert compatibility_module.Spectrum is svc.Spectrum
    assert compatibility_module.SpectraCollection is svc.SpectraCollection
    assert compatibility_module.verify_demo_data is svc.verify_demo_data


def test_notebook_is_pip_first_and_path_independent() -> None:
    notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    all_code = "\n".join(cell.source for cell in code_cells)

    assert 'PYPI_SPEC = "svc-processing[demo]>=0.1.5"' in code_cells[0].source
    assert "SVCProcessingPipeline/archive/refs/heads/main.zip" in code_cells[0].source
    assert "subprocess.check_call" in code_cells[0].source
    assert "pipeline.notebook" in code_cells[0].source
    assert "from pipeline.notebook import" in all_code
    assert "SVC_DATA_FOLDER" in all_code
    assert "create_demo_data" not in all_code
    assert "sys.path" not in all_code
    assert "PROJECT_ROOT" not in all_code
    assert "notebooks/pipeline_demo/demo_data" not in all_code
    assert all(cell.execution_count is None and not cell.outputs for cell in code_cells)
    assert notebook.metadata.kernelspec.display_name == "Python 3"


def test_package_discovery_excludes_generated_outputs() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    discovery = config["tool"]["setuptools"]["packages"]["find"]

    assert discovery["include"] == ["pipeline", "pipeline.*"]
    assert discovery["namespaces"] is False


def test_demo_extra_covers_notebook_runtime_and_execution_dependencies() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)

    runtime = set(config["project"]["dependencies"])
    demo = set(config["project"]["optional-dependencies"]["demo"])
    assert {"numpy", "pandas", "scipy"} <= runtime
    assert {"ipykernel", "matplotlib", "nbclient", "nbconvert", "nbformat"} <= demo


def test_notebook_helper_imports_public_resampler_api() -> None:
    source = (ROOT / "pipeline" / "notebook.py").read_text()

    assert "_read_sig" not in source
    assert "_gaussian_resample" not in source
    assert "process_sig_file" in source
