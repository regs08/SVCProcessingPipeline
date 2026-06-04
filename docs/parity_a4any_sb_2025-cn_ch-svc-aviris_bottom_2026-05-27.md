# Parity Verification — Dataset a4any_sb_2025-cn_ch-svc-aviris_bottom, 2026-05-27

## Dataset description

| Property                     | Value                                                                        |
|------------------------------|------------------------------------------------------------------------------|
| Source dataset               | `a4any_sb_2025-cn_ch-svc-aviris_bottom` (external `.sig` artifact; raw files not tracked because headers may contain GPS/location metadata) |
| `.sig` file count            | 15                                                                           |
| Instrument header            | `HI: 2212118 (HR-1024i)`                                                     |
| Instrument serial            | 2212118                                                                      |
| Calibration class            | Bronze (end-line = `2520.4`)                                                 |
| Instrument consistency       | Consistent (15 / 15 files share the same instrument; 0 warnings)             |
| Acquisition date range       | 07/07/2022 21:42 to 07/07/2022 21:53 (local time, as parsed from headers)    |
| Aligned matrix dimensions    | 15 samples × 2101 wavelength bands (400–2500 nm, 1 nm grid)                  |

## Pipeline execution

| Stage                       | Output                                                                                                                                                              |
|-----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Pipeline B (Python) CSV     | `pipeline_outputs/sig_resampled/a4any_sb_2025-cn_ch-svc-aviris_bottom/a4any_sb_2025-cn_ch-svc-aviris_bottom_merged_spectra.csv`                                      |
| Pipeline A (R/spectrolab)   | `pipeline_outputs/sig_r_reference/a4any_sb_2025-cn_ch-svc-aviris_bottom/r_merged.csv` (generated locally via `merge_resample_sig.R` on the same processed `.sig` directory) |
| pytest parity harness       | `tests/test_resampler_parity.py::test_python_output_matches_r_reference` — **PASSED** at default tolerance MAX\_ABS\_DIFF = 1e-3                                     |

## Equivalence statistics

| Statistic                                                             | Value                       |
|-----------------------------------------------------------------------|-----------------------------|
| max \|R - Py\|                                                        | 9.4e-7                      |
| mean \|R - Py\|                                                       | 3.4e-8                      |
| cells with \|R - Py\| > 1.0e-3                                        | 0                           |
| cells with \|R - Py\| > 1.0e-4                                        | 0                           |
| cells with \|R - Py\| > 1.0e-5                                        | 0                           |
| Worst-offending sample                                                | `bottom.HR.072825..0003`    |
| Worst-offending wavelength                                            | 692 nm                      |
| Wavelengths with per-band RMSE > 10 × global mean diff                | 22 bands, all in 689–710 nm |

## Per-wavelength systematic divergence

A localised band of 22 wavelengths (approximately 689–710 nm) exhibits per-band
RMSE above 10× the global mean absolute difference, with peak per-band RMSE of
7.3e-7 at 694 nm. The absolute magnitudes remain three orders of magnitude
below the 1e-3 acceptance threshold; this pattern coincides with the Sensor 1
to Sensor 2 splice region and is consistent with minor floating-point ordering
differences in the multiplicative ramp applied by `match_sensors(iter = 1)`.

## Verdict

**PASS.** All 31,515 cells (15 × 2101) lie within the accepted physical
significance threshold of 1e-3 absolute reflectance, with a maximum absolute
deviation of 9.4e-7 — i.e. parity is held to better than one part per million.

## Interpretation

Numerical agreement between the pure-Python re-implementation and the
R/spectrolab reference is comparable in magnitude to the previously reported
66-sample Silver reference run (max 1.1e-6, mean 4.0e-8). The current run on
15 Bronze (Serial 2212118) samples yields max 9.4e-7 and mean 3.4e-8, which is
of the same order as that prior result and is well within the
sub-floating-point-precision regime expected when comparing independent
implementations of Gaussian convolution and splice correction. No cells exceed
the 1e-3 manuscript threshold, no samples behave anomalously, and the
instrument-consistency check returned no warnings. The minor concentration of
divergence in the 689–710 nm splice region is consistent with the behaviour
observed in the prior reference dataset and does not indicate any algorithmic
or upstream data issue.

## Anomalies

None detected. Instrument header consistency was perfect across all 15 files.
No NaN values were produced. The Python output spans the expected reflectance
range (0.028 to 1.002), consistent with valid SVC reflectance products.

## Software versions

| Component   | Version          |
|-------------|------------------|
| Python      | 3.9.6            |
| NumPy       | 2.0.2            |
| SciPy       | 1.13.1           |
| pandas      | 2.3.0+4.g1dfc98e16a |
| specdal     | Not used by Pipeline B runtime |
| R           | 4.5.1            |
| spectrolab  | 0.0.19           |
