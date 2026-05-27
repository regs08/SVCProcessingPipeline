"""Pure-Python resampler replacing merge_resample_sig.R.

Faithfully replicates the spectrolab R pipeline:
    read_spectra  →  guess_splice_at  →  match_sensors  →  smooth  →  resample(fwhm=10)

SVC .sig files store multiple sensor segments sequentially in one file, separated
by backward wavelength jumps.  spectrolab detects these segments and applies a
linearly-varying multiplicative correction per segment so that the sensors match
at each splice boundary.  specdal does not understand this structure, so this
module reads .sig files directly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans as _scipy_kmeans, vq as _scipy_vq


# ── spectrolab replication constants ────────────────────────────────────────
_FWHM_NM         = 10.0      # spectrolab resample fwhm=10
_SIGMA_NM        = _FWHM_NM / 2.355          # Gaussian σ ≈ 4.25 nm
_INTERP_WVL      = (5.0, 2.0)                # spectrolab interpolate_wvl default
_FIXED_SENSOR    = 2                          # spectrolab fixed_sensor when 2 splices
_BAND_MIN        = 400
_BAND_MAX        = 2500


# ── .sig file reader ─────────────────────────────────────────────────────────

def _read_sig(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    Read a SVC .sig file and return (wavelengths, reflectances) in file order.

    The .sig data section has four space-separated columns:
        wavelength  ref_radiance  tgt_radiance  pct_reflect

    Sensor segments appear sequentially; segment N+1 starts where the wavelength
    sequence jumps backward relative to segment N.

    Exact-duplicate wavelengths (which occur in the sensor overlap regions) receive
    a tiny perturbation matching spectrolab's i_bands():
        correction = 1.2357e-05 * min(|diff(non_duplicate_bands)|)
    This causes the sensor overlap trimming logic to keep both the last band of
    sensor N and the first band of sensor N+1 when their nominal wavelengths match.
    """
    with open(path) as fh:
        lines = fh.readlines()

    data_start = next(i for i, l in enumerate(lines) if l.strip() == "data=")
    wls, rfs = [], []
    for line in lines[data_start + 1:]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                wls.append(float(parts[0]))
                rfs.append(float(parts[3]) / 100.0)
            except ValueError:
                pass

    wls_arr = np.array(wls, dtype=float)
    rfs_arr = np.array(rfs, dtype=float)

    # Replicate spectrolab i_bands(): add a tiny correction to exact duplicates
    seen: dict[float, bool] = {}
    dup_positions: list[int] = []
    for i, w in enumerate(wls_arr):
        key = float(w)
        if key in seen:
            dup_positions.append(i)
        else:
            seen[key] = True

    if dup_positions:
        non_dup_mask = np.ones(len(wls_arr), dtype=bool)
        non_dup_mask[dup_positions] = False
        min_spacing = float(np.min(np.abs(np.diff(wls_arr[non_dup_mask]))))
        correction = 1.2357e-05 * min_spacing
        for pos in dup_positions:
            wls_arr[pos] += correction

    return wls_arr, rfs_arr


def _sensor_segment_indices(wls: np.ndarray) -> list[tuple[int, int]]:
    """
    Return (start, end) index pairs for each monotonically-increasing sensor segment.

    Matches spectrolab's i_find_sensor_overlap_bounds: a new segment starts
    wherever wavelength[i] < wavelength[i-1].
    """
    decreases = np.where(np.diff(wls) < 0)[0] + 1   # positions of backward jumps
    starts = np.concatenate([[0], decreases])
    ends   = np.concatenate([decreases, [len(wls)]])
    return list(zip(starts.tolist(), ends.tolist()))


def _guess_splice_at(segments: list[tuple[int, int]], wls: np.ndarray) -> list[float]:
    """
    Compute splice wavelengths using spectrolab's formula:
        splice[i] = (sensor[i+1].min_wl * 2*(i+1) + sensor[i].max_wl) / (2*(i+1) + 1)

    where i is 1-based (i=1 for first splice, i=2 for second…).
    """
    splices = []
    for i, ((_, end_i), (start_j, _)) in enumerate(zip(segments[:-1], segments[1:]), start=1):
        scalar   = 2 * i
        min_next = wls[start_j]
        max_curr = wls[end_i - 1]
        splice   = (min_next * scalar + max_curr) / (scalar + 1)
        splices.append(splice)
    return splices


def _trim_and_assign(
    segments: list[tuple[int, int]],
    wls: np.ndarray,
    splices: list[float],
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Replicate spectrolab's i_trim_sensor_overlap: clip each sensor at the splice
    boundaries so there is no wavelength overlap between adjacent sensors.

    Returns a list of (wavelength_indices, sensor_id) per sensor, matching the
    order used by match_sensors.
    """
    n_sensors = len(segments)
    # Build per-sensor index arrays
    sensor_idx = [np.arange(s, e) for s, e in segments]

    for i, splice in enumerate(splices):
        # Clip sensor[i+1] on the left: keep wavelengths >= splice
        right_mask = wls[sensor_idx[i + 1]] >= splice
        sensor_idx[i + 1] = sensor_idx[i + 1][right_mask]

        # Clip sensor[i] on the right: keep wavelengths < first of trimmed sensor[i+1]
        if len(sensor_idx[i + 1]) > 0:
            min_right = wls[sensor_idx[i + 1][0]]
            left_mask = wls[sensor_idx[i]] < min_right
            sensor_idx[i] = sensor_idx[i][left_mask]

    return sensor_idx


def _apply_match_sensors(
    wls: np.ndarray,
    rfs: np.ndarray,
    sensor_idx: list[np.ndarray],
    splices: list[float],
    fixed_sensor: int = _FIXED_SENSOR,
    interp_wvl: tuple = _INTERP_WVL,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Replicate spectrolab's match_sensors.

    When the .sig file contains actual sensor overlap (backward wavelength jumps)
    and there are multiple splices, spectrolab sets iter=1 — meaning only sensor 1
    is corrected.  Sensor 2 (fixed) and sensor 3 stay unchanged.

    The correction for sensor 1 is a linearly-varying multiplicative factor:
        factor = 1.0 at the start of sensor 1's wavelength range
        factor = q   at the end  of sensor 1's wavelength range
    where q = mean(fixed_sensor_at_splice) / mean(sensor1_at_splice).

    fixed_sensor is 1-based (spectrolab default = 2).
    """
    corrected_rfs = rfs.copy()

    # Only the first splice correction is applied when there are multiple splices
    # and the .sig file has overlap data (spectrolab: iter=1 branch).
    # We still compute all splice factors for correctness, but apply only the first.
    n_apply = 1 if len(splices) > 1 else len(splices)

    fixed_0 = fixed_sensor - 1  # 0-based index of fixed sensor

    for z in range(n_apply):
        splice = splices[z]
        hw = interp_wvl[z] if z < len(interp_wvl) else interp_wvl[-1]
        low, high = splice - hw, splice + hw

        left_idx  = sensor_idx[z][
            (wls[sensor_idx[z]] >= low) & (wls[sensor_idx[z]] <= high)
        ]
        right_idx = sensor_idx[z + 1][
            (wls[sensor_idx[z + 1]] >= low) & (wls[sensor_idx[z + 1]] <= high)
        ]

        if len(left_idx) == 0:
            left_idx = sensor_idx[z][[-1]]
        if len(right_idx) == 0:
            right_idx = sensor_idx[z + 1][[0]]

        mean_left  = rfs[left_idx].mean()
        mean_right = rfs[right_idx].mean()

        # Determine which side is fixed and compute the scaling factor q
        if z + 1 == fixed_0:       # fixed sensor is on the right at this splice
            q = mean_right / mean_left if mean_left != 0 else 1.0
            # Scale sensor z (left): factor from 1.0 at start → q at end
            idx = sensor_idx[z]
            w   = wls[idx]
            factors = np.interp(w, [w.min(), w.max()], [1.0, q])
            corrected_rfs[idx] = rfs[idx] * factors
        else:                       # fixed sensor is on the left at this splice
            q = mean_left / mean_right if mean_right != 0 else 1.0
            # Scale sensor z+1 (right): factor from q at start → 1.0 at end
            idx = sensor_idx[z + 1]
            w   = wls[idx]
            factors = np.interp(w, [w.min(), w.max()], [q, 1.0])
            corrected_rfs[idx] = rfs[idx] * factors

    # Merge all sensor bands in wavelength order
    all_idx    = np.concatenate(sensor_idx)
    order      = np.argsort(wls[all_idx])
    merged_wls = wls[all_idx][order]
    merged_rfs = corrected_rfs[all_idx][order]

    return merged_wls, merged_rfs


def _smooth_fwhm(wls: np.ndarray, rfs: np.ndarray) -> np.ndarray:
    """
    Replicate spectrolab smooth(method='gaussian') → smooth_fwhm().

    Mirrors spectrolab internals exactly:
      1. fwhm_from_band_diff — per-band FWHM from local band spacing
      2. i_make_fwhm (return_type='old') — Gaussian-weighted mean of neighbour FWHMs
      3. kmeans(k=3) — quantise into 3 bandwidth clusters (one per sensor)
      4. Double the FWHM  (smooth_fwhm multiplies make_fwhm result by 2)
      5. Gaussian resample to the same wavelength grid with per-band sigma
    """
    diffs = np.diff(wls)
    fwhm_per_band = np.concatenate([[diffs[0]], diffs])   # fwhm_from_band_diff

    sigma0 = fwhm_per_band / (2.0 * np.sqrt(2.0 * np.log(2.0)))

    # Pairwise distance matrix — reused for both the fwhm averaging and the resample
    d = wls[:, None] - wls[None, :]   # shape (n, n): d[i, j] = wls[i] - wls[j]

    # i_make_fwhm with return_type='old': Gaussian-weighted average of fwhm_per_band
    g = np.exp(-0.5 * (d / sigma0[None, :]) ** 2)       # sigma0[j] for target j
    fwhm_old_new = (g * fwhm_per_band[:, None]).sum(axis=0) / g.sum(axis=0)

    # kmeans(k=3): quantise bandwidth into 3 clusters (mirrors spectrolab make_fwhm k=3)
    k = min(3, len(np.unique(np.round(fwhm_old_new, 4))))
    codebook, _ = _scipy_kmeans(fwhm_old_new, k)
    labels, _   = _scipy_vq(fwhm_old_new, codebook)
    smooth_fwhm_vals = 2.0 * codebook[labels]            # step 4: double the FWHM

    # Gaussian resample to the same grid with per-band sigma
    sigma_s = smooth_fwhm_vals / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    g2 = np.exp(-0.5 * (d / sigma_s[None, :]) ** 2)
    return (g2 * rfs[:, None]).sum(axis=0) / g2.sum(axis=0)


def _gaussian_resample(
    wls: np.ndarray,
    rfs: np.ndarray,
    target: np.ndarray,
    sigma: float = _SIGMA_NM,
) -> np.ndarray:
    """
    Gaussian-weighted resampling: replicates spectrolab's resample(fwhm=10).

    For each target wavelength w_t:
        weight_i = exp(-0.5 * ((wl_i - w_t) / sigma)^2)
        output(w_t) = sum(weight_i * rf_i) / sum(weight_i)
    """
    d = wls[:, None] - target[None, :]       # (n_input, n_target)
    w = np.exp(-0.5 * (d / sigma) ** 2)
    return (w * rfs[:, None]).sum(axis=0) / w.sum(axis=0)


# ── public API ───────────────────────────────────────────────────────────────

def resample_spectra(input_dir: Path, output_dir: Path, output_filename: str) -> Path:
    """Load .sig files, replicate spectrolab's pipeline, and write merged CSV.

    Pipeline (mirrors spectrolab exactly):
        read_spectra   – parse .sig data section, detect sensor segments
        guess_splice_at – compute splice wavelengths from segment bounds
        match_sensors  – linearly-varying multiplicative correction per sensor
        smooth()       – Gaussian smooth with per-band sigma from local band spacing
        resample(fwhm=10) – Gaussian-weighted resampling to 400–2500 nm

    Args:
        input_dir:       Directory containing processed .sig files.
        output_dir:      Directory where the output CSV will be written.
        output_filename: File name for the output CSV.

    Returns:
        Path to the written CSV.
    """
    input_dir  = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sig_files = sorted(input_dir.glob("*.sig"))
    if not sig_files:
        raise ValueError(f"No .sig files found in {input_dir}")

    target_wls = np.arange(_BAND_MIN, _BAND_MAX + 1, dtype=float)
    rows: dict[str, np.ndarray] = {}

    for sig_path in sig_files:
        wls, rfs = _read_sig(sig_path)

        # ── detect sensor segments ──────────────────────────────────────────
        segments = _sensor_segment_indices(wls)

        if len(segments) > 1:
            # ── guess_splice_at ─────────────────────────────────────────────
            splices = _guess_splice_at(segments, wls)

            # ── i_trim_sensor_overlap ────────────────────────────────────────
            sensor_idx = _trim_and_assign(segments, wls, splices)

            # ── match_sensors ────────────────────────────────────────────────
            fixed = min(_FIXED_SENSOR, len(segments))
            merged_wls, merged_rfs = _apply_match_sensors(
                wls, rfs, sensor_idx, splices, fixed_sensor=fixed
            )
        else:
            # Single-sensor file: no correction needed
            merged_wls = wls
            merged_rfs = rfs

        # ── smooth() — Gaussian smooth matching spectrolab smooth(method='gaussian')
        smoothed_rfs = _smooth_fwhm(merged_wls, merged_rfs)

        # ── resample(fwhm=10) — Gaussian-weighted to 400:2500 ────────────────
        resampled = _gaussian_resample(merged_wls, smoothed_rfs, target_wls)

        # Sample name: strip .sig extension (matches specdal convention)
        sample_name = sig_path.stem
        rows[sample_name] = resampled

    df = pd.DataFrame(rows, index=target_wls.astype(int)).T
    df.index.name = "sample_name"

    output_path = output_dir / output_filename
    df.to_csv(output_path)
    return output_path
