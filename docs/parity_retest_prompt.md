# Parity Re-Test Prompt (copy into any capable coding LLM)

```
You are an expert in field spectroscopy data processing and scientific
computing. Your task is to execute a numerical parity verification between two
independent implementations of an SVC HR-1024i spectral processing pipeline,
using a new dataset that I will supply, and produce a formal parity report
suitable as a supplementary table in a peer-reviewed manuscript.

---

## CONTEXT

Two implementations of the same algorithm exist in this repository:

  Pipeline A — R/spectrolab (Meireles et al., 2020, JOSS, 5(53), 2526)
               https://doi.org/10.21105/joss.02526
  Pipeline B — pure Python, located at `pipeline/resampler.py`,
               orchestrated by the `svc-pipeline` console script

Both produce a CSV in which rows are samples and columns are integer
wavelengths 400–2500 nm (2101 columns). Algorithmic steps in both pipelines:

  1. Parse `.sig` file (column 4 / 100 → fractional reflectance).
  2. Perturb exact-duplicate wavelengths at sensor boundaries by
     1.2357e-5 × min_band_spacing.
  3. Detect sensor segment splice wavelengths via the formula
        splice[i] = (2·i·wl_next_start + wl_curr_end) / (2·i + 1).
  4. Trim overlap bands and apply spectrolab's match_sensors with iter=1
     (multiplicative ramp on Sensor 1 only; Sensors 2/3 unmodified).
  5. Apply resolution-matched Gaussian smoothing (smooth_fwhm, k=3 k-means
     quantization of per-band FWHM, then doubled).
  6. Gaussian-weighted resample to 1 nm grid 400–2500 with FWHM = 10 nm
     (σ = 10 / (2·sqrt(2·ln 2)) ≈ 4.25 nm).

A prior parity run on 66 samples (instrument "Silver", Serial 1202103)
produced:
  max abs diff  = 1.10e-6
  mean abs diff = 4.0e-8
  cells > 1e-3  = 0
The accepted physical-significance threshold is 1e-3 absolute reflectance
(0.1 %).

---

## INPUT YOU WILL RECEIVE

I will supply the absolute path to a folder containing new `.sig` files from
the same instrument family (HR-1024i). Place the path here:

    NEW_SIG_DIR = <PASTE ABSOLUTE PATH HERE>

If a previously-generated R/spectrolab reference CSV exists for this dataset,
also place it here; otherwise leave blank and the R pipeline will be re-run
when possible:

    R_REFERENCE_CSV = <PASTE ABSOLUTE PATH OR LEAVE BLANK>

Instrument correction type (silver, white, blue, etc.) if known:

    CORRECTION_TYPE = <silver | other | unknown>

---

## STEPS TO PERFORM

1. Sanity-check the input folder:
     - Count `.sig` files.
     - Verify all files share the same instrument serial number using
       `pipeline.sig_processor.SigFileProcessor.check_instrument_consistency`.
     - Report any warnings.

2. Run Pipeline B (Python) end-to-end on NEW_SIG_DIR:
     - Either invoke `svc-pipeline config.json --input-dir <NEW_SIG_DIR> --step all`
       (the shipped `config.json` template is used; `--input-dir` overrides its
       `sig_input_dir` directly), OR
     - Call `pipeline.resampler.resample_spectra(processed_dir, out_dir,
       "python_merged.csv")` directly on already-processed `.sig` files.
     - Capture the resulting CSV path.

3. Obtain the Pipeline A (R) reference:
     - If R_REFERENCE_CSV was supplied, use it.
     - Otherwise, if R + spectrolab is available, run the R pipeline on the
       SAME processed `.sig` directory (the project has scripts archived
       alongside it; ask me for the R script path if not found). The R output
       must be a CSV with sample-name index and integer wavelength columns
       400–2500.
     - If R is unavailable on this machine, STOP and report this clearly —
       parity cannot be claimed without the R reference.

4. Run the existing pytest parity harness:

       pytest tests/test_resampler_parity.py \
           --r-reference-csv=<R_REFERENCE_CSV> \
           --r-input-dir=<PROCESSED_SIG_DIR>

   Capture pass/fail and the printed max/mean diff diagnostics.

5. Independently compute and report the following statistics on the aligned
   N_samples × 2101 matrix:

       max  |R - Py|
       mean |R - Py|
       count of cells with |R - Py| > 1e-3
       count of cells with |R - Py| > 1e-4
       count of cells with |R - Py| > 1e-5
       worst-offending sample name
       worst-offending wavelength (nm)

   Also compute a per-wavelength RMSE curve and identify any wavelength bins
   where systematic divergence appears (max diff > 10× the global mean diff).

6. Produce a Markdown report titled
   "Parity Verification — Dataset <folder name>, <YYYY-MM-DD>"
   containing:
     - Dataset description (file count, instrument serial, date range if
       parseable from file headers).
     - Table of the equivalence statistics in step 5 (same column layout as
       Table 1 in `docs/supplementary_methods.md`).
     - Pass/fail verdict against the 1e-3 threshold.
     - A short prose paragraph (3–6 sentences) interpreting the result and
       comparing it to the prior 66-sample reference run.
     - Any anomalies (samples that fall outside tolerance, suspected
       upstream data issues, instrument mismatches).
     - Exact software versions used (Python, NumPy, SciPy, pandas, R,
       spectrolab).

Save the report to `docs/parity_<folder-name>_<YYYY-MM-DD>.md`.

---

## TONE AND STYLE

- Formal scientific English; passive voice where appropriate.
- Numbers in scientific notation with two significant figures (e.g. 1.1e-6).
- No conjecture beyond what the data support.
- Do NOT modify `pipeline/resampler.py` or any pipeline source; this is a
  verification task, not a refactor. If a discrepancy > 1e-3 is found, report
  it and STOP — do not attempt to fix the code.
```
