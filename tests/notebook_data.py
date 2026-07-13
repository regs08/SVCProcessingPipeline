"""Deterministic test-only SVC data for notebook and integration smoke tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np


FILE_COUNT = 15
REFERENCE_INDICES = frozenset({0, 7, 14})


def _sensor_wavelengths() -> tuple[np.ndarray, np.ndarray]:
    segments = (
        np.round(np.linspace(339.1, 1012.0, 512), 1),
        np.round(np.linspace(972.0, 1910.0, 256), 1),
        np.round(np.linspace(1894.0, 2520.4, 256), 1),
    )
    wavelengths = np.concatenate(segments)
    sensor_ids = np.concatenate(
        [
            np.full(len(segment), sensor_id, dtype=int)
            for sensor_id, segment in enumerate(segments)
        ]
    )
    return wavelengths, sensor_ids


def _leaf_reflectance(wavelengths: np.ndarray, scan_index: int) -> np.ndarray:
    red_edge = 0.38 / (1.0 + np.exp(-(wavelengths - 720.0) / 18.0))
    green_peak = 0.055 * np.exp(-0.5 * ((wavelengths - 550.0) / 38.0) ** 2)
    red_absorption = 0.025 * np.exp(-0.5 * ((wavelengths - 675.0) / 24.0) ** 2)
    water_1400 = 0.16 * np.exp(-0.5 * ((wavelengths - 1400.0) / 55.0) ** 2)
    water_1900 = 0.22 * np.exp(-0.5 * ((wavelengths - 1900.0) / 75.0) ** 2)
    water_2450 = 0.08 * np.exp(-0.5 * ((wavelengths - 2450.0) / 95.0) ** 2)
    scan_offset = 0.004 * ((scan_index % 6) - 2.5)
    texture = 0.002 * np.sin(wavelengths / 31.0 + scan_index)
    reflectance = (
        0.045
        + red_edge
        + green_peak
        - red_absorption
        - water_1400
        - water_1900
        - water_2450
        + scan_offset
        + texture
    )
    return np.clip(reflectance, 0.015, 0.75)


def _scan_text(scan_index: int) -> str:
    wavelengths, sensor_ids = _sensor_wavelengths()
    if scan_index in REFERENCE_INDICES:
        reflectance = 0.98 + 0.003 * np.sin(wavelengths / 43.0 + scan_index)
    else:
        reflectance = _leaf_reflectance(wavelengths, scan_index)

    reflectance = reflectance * np.array([0.985, 1.0, 1.018])[sensor_ids]
    reference_radiance = 1000.0 + 120.0 * np.sin(wavelengths / 180.0)
    target_radiance = reference_radiance * reflectance
    name = f"synthetic.HR.{scan_index:04d}.sig"
    lines = [
        "/*** Synthetic SVC Test Data ***/",
        f"name= {name}",
        "instrument= HI: 2212118 (HR-1024i)",
        "integration= synthetic",
        "data=",
    ]
    lines.extend(
        f"{wavelength:.1f}  {reference:.2f}  {target:.2f}  {100.0 * fraction:.2f}"
        for wavelength, reference, target, fraction in zip(
            wavelengths, reference_radiance, target_radiance, reflectance
        )
    )
    return "\n".join(lines) + "\n"


def create_notebook_test_data(target_dir: str | Path) -> Path:
    """Write a full-range test dataset; never called by the user tutorial."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    for scan_index in range(FILE_COUNT):
        path = target / f"synthetic.HR.{scan_index:04d}.sig"
        path.write_text(_scan_text(scan_index))
    return target
