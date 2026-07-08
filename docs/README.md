# `docs/` — Supplementary Documentation

Long-form documentation supporting the manuscript and the parity verification of the R → Python migration. Files here are intended for human readers (and for LLMs orienting themselves on the project); they are not consumed by the pipeline at runtime.

## Files

### [`supplementary_methods.md`](supplementary_methods.md)
The canonical, manuscript-grade description of the algorithm implemented by [`pipeline/resampler.py`](../pipeline/resampler.py). Covers:

1. Instrument and `.sig` data format (SVC HR-1024i, three-detector layout).
2. Pipeline overview (two implementations: R/`spectrolab` "Pipeline A" and pure-Python "Pipeline B").
3. Sensor stitching and radiometric correction — duplicate-wavelength perturbation, splice formula, `match_sensors(iter = 1)`.
4. Resolution-matched Gaussian smoothing — `smooth_fwhm` with k-means quantization (`k = 3`).
5. Gaussian-weighted resampling onto a 1 nm grid 400–2500 nm (FWHM = 10 nm, σ ≈ 4.25 nm).
6. Rationale for selecting the Python implementation.
7. Parity verification statistics (66 samples, Silver instrument, max abs diff 1.10 × 10⁻⁶).
8. Software versions and reproducibility notes.

**Anyone modifying [`pipeline/resampler.py`](../pipeline/resampler.py) should keep this document in sync.**

### [`in_depth_methods_and_config_guide.md`](in_depth_methods_and_config_guide.md)
Practical, accessible companion to `supplementary_methods.md`. Answers three
questions: what each pipeline stage does and why (keyed to
[`config/config.json`](../config/config.json), with a stage→config-key map
and an "is it safe to change?" guide), and why the pipeline is built this way
at all (Python over R, this algorithm over off-the-shelf libraries like
`specdal`). Read this when editing the config, explaining a setting, or
onboarding someone new; read `supplementary_methods.md` for the citable,
equation-bearing version.

### [`parity_retest_prompt.md`](parity_retest_prompt.md)
A self-contained LLM prompt that drives a parity re-test for a new dataset. Includes the algorithmic spec (steps 1–6 of the pipeline), the expected statistics, the steps the LLM must perform (run Pipeline B, obtain Pipeline A reference, run [`tests/test_resampler_parity.py`](../tests/test_resampler_parity.py), compute statistics, produce a Markdown report), and tone/style rules ("formal scientific English; do not modify pipeline source"). Copy this verbatim into any capable coding LLM to regenerate a `parity_<dataset>_<date>.md`.

### [`pip_packaging_guide.md`](pip_packaging_guide.md)
Packaging and release notes for the current `pyproject.toml` layout and
`svc-pipeline` console script.

## Conventions
- Parity reports are named `parity_<dataset_folder_name>_<YYYY-MM-DD>.md`.
- Statistics are reported in scientific notation with two significant figures (e.g. `1.1e-6`).
- The threshold for "physically equivalent" is **1 × 10⁻³ absolute reflectance** (0.1 %) — well below the HR-1024i radiometric noise floor.
- Do not delete prior parity reports; they form the audit trail referenced by the manuscript.
