from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SVC_PATH = ROOT / "notebooks" / "pipeline_demo" / "svc.py"
SPEC = importlib.util.spec_from_file_location("pipeline_demo_svc", SVC_PATH)
assert SPEC is not None and SPEC.loader is not None
svc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(svc)


class DummySpectrum:
    def __init__(self, name: str, value: float, *, processed: bool = True) -> None:
        self.name = name
        self.is_processed = processed
        self.wavelengths = svc.STANDARD_WAVELENGTHS.copy()
        self.reflectance = np.full(len(svc.STANDARD_WAVELENGTHS), value, dtype=float)


class DummyCollection:
    def __init__(self, spectra: list[DummySpectrum]) -> None:
        self.spectra = spectra


def _write_manifest(tmp_path: Path, payload: bytes) -> tuple[Path, Path]:
    spectra_dir = tmp_path / "spectra"
    spectra_dir.mkdir()
    sig_path = spectra_dir / "demo.sig"
    sig_path.write_bytes(payload)
    manifest = {
        "files": [
            {
                "name": "demo.sig",
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return spectra_dir, manifest_path


def test_verify_demo_data_accepts_matching_manifest(tmp_path: Path) -> None:
    spectra_dir, manifest_path = _write_manifest(tmp_path, b"synthetic")

    assert svc.verify_demo_data(spectra_dir, manifest_path) == spectra_dir


def test_verify_demo_data_reports_missing_files(tmp_path: Path) -> None:
    spectra_dir, manifest_path = _write_manifest(tmp_path, b"synthetic")
    (spectra_dir / "demo.sig").unlink()

    with pytest.raises(FileNotFoundError, match="Demo .sig data are missing"):
        svc.verify_demo_data(spectra_dir, manifest_path)


def test_verify_demo_data_reports_checksum_mismatch(tmp_path: Path) -> None:
    spectra_dir, manifest_path = _write_manifest(tmp_path, b"synthetic")
    (spectra_dir / "demo.sig").write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="failed manifest verification"):
        svc.verify_demo_data(spectra_dir, manifest_path)


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


def test_demo_helper_imports_public_resampler_api() -> None:
    source = SVC_PATH.read_text()

    assert "_read_sig" not in source
    assert "_gaussian_resample" not in source
    assert "process_sig_file" in source
