# SIG Processing Pipeline

A pure-Python pipeline for processing SVC HR-1024i field hyperspectral `.sig` files. Reads raw multi-detector spectra, performs sensor stitching and radiometric correction, applies resolution-matched Gaussian smoothing, and resamples onto a uniform 1 nm grid from 400–2500 nm. Numerically verified against the legacy R/`spectrolab` reference to better than 1 × 10⁻⁶ absolute reflectance.

> **This README is the canonical entry point for both humans and LLMs.** Every directory in the repo has its own `README.md` describing its contents in detail. Follow the links below — do not assume anything that is not stated here or in the linked docs.

---

## Repository map

| Path | Purpose | Read me first |
|---|---|---|
| [`run_pipeline.py`](run_pipeline.py) | CLI orchestrator (the only top-level script). | This file ↓ |
| [`pipeline/`](pipeline/) | Core Python package: `SigFileProcessor`, `resample_spectra`, `SVCDataProcessor`. | [`pipeline/README.md`](pipeline/README.md) |
| [`tests/`](tests/) | Pytest suite, including the R-vs-Python parity test. | [`tests/README.md`](tests/README.md) |
| [`config/`](config/) | Run configs + instrument calibration JSONs. | [`config/README.md`](config/README.md) |
| [`docs/`](docs/) | Manuscript-grade methods, parity reports, LLM re-test prompt. | [`docs/README.md`](docs/README.md) |
| [`archived_r_scripts/`](archived_r_scripts/) | Frozen R/`spectrolab` reference (Pipeline A) — kept only for parity verification. | [`archived_r_scripts/README.md`](archived_r_scripts/README.md) |
| [`notebooks/`](notebooks/) | Exploratory & visualization notebooks (not on the production path). | [`notebooks/README.md`](notebooks/README.md) |
| [`naming_ids/`](naming_ids/) | Private CSV lookup tables for grouping scans into samples (gitignored). | [`naming_ids/README.md`](naming_ids/README.md) |
| [`FOLDER_STRUCTURE.md`](FOLDER_STRUCTURE.md) | Authoritative tree + reading order. | — |

Generated outputs (gitignored): `pipeline_outputs/sig_processed/<run>/`, `pipeline_outputs/sig_resampled/<run>/`.

---

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Edit config/config.json — replace "<PATH_TO_SIG_INPUT_ROOT>" with your data path.
python run_pipeline.py --config config/config.json --verbose
```

Outputs land under `pipeline_outputs/` by default. See [`config/README.md`](config/README.md) for every supported key.

---

## Pipeline architecture

```
   raw *.sig files (sig_input_dir)
            │
            ▼
   ┌────────────────────────────────────┐
   │ Stage 1: SigFileProcessor          │  pipeline/sig_processor.py
   │   - instrument-consistency check   │
   │   - truncate at calibration        │
   │     end-line wavelength            │
   │   - write summary CSV              │
   └────────────────────────────────────┘
            │
            ▼  processed *.sig + *_processed_sig_summary.csv
   ┌────────────────────────────────────┐
   │ Stage 2: resample_spectra()        │  pipeline/resampler.py
   │   - detect sensor segments         │
   │   - guess_splice_at + trim         │
   │   - match_sensors (iter = 1)       │
   │   - smooth_fwhm (k=3 kmeans)       │
   │   - Gaussian resample fwhm=10      │
   │     onto 400–2500 nm @ 1 nm        │
   └────────────────────────────────────┘
            │
            ▼  <run>_merged_spectra.csv
   ┌────────────────────────────────────┐
   │ Stage 3 (post-hoc, optional):      │  pipeline/processor.py
   │   SVCDataProcessor /               │  + notebooks/
   │   SigSpectraAverager — group &     │
   │   average scans into samples.      │
   └────────────────────────────────────┘
```

[`run_pipeline.py`](run_pipeline.py) glues Stages 1 and 2 together; Stage 3 is invoked from notebooks against the Stage 2 output. The pipeline is **single-pass and idempotent per input directory** — previous processed `.sig` files in the target directory are deleted at the start of each run.

For the formal algorithmic spec (every constant, every formula), read [`docs/supplementary_methods.md`](docs/supplementary_methods.md). That document — not this README — is the source of truth for *what* the code does.

---

## Running the pipeline

```bash
python run_pipeline.py --config config/config.json [options]
```

| Option | Meaning |
|---|---|
| `--config <path>` | Path to a run-config JSON. See [`config/README.md`](config/README.md) for schema. |
| `--input-dir <path>` | Override `sig_input_dir` and process only this directory. |
| `--step {1,2,all}` | `1` = process + summary CSV only; `2` = resample only (requires Stage 1 to have been run); `all` = both (default). |
| `--verbose` | Print INFO/DEBUG logs before and after each stage. |

The CLI default for `--config` is `config/weekly_data.json`; the shipped template is [`config/config.json`](config/config.json), so always pass `--config` explicitly unless you've created the weekly file locally.

### Expected output layout

```
pipeline_outputs/
├── sig_processed/<input_dir_name>/
│   ├── <truncated *.sig files>
│   └── <input_dir_name>_processed_sig_summary.csv
└── sig_resampled/<input_dir_name>/
    └── <input_dir_name>_merged_spectra.csv     # 2101 columns (400–2500 nm)
```

`summary_csv_name` and `merged_csv_name` in the run config are suffixes; the real filenames are prefixed with the input directory name. Verify your config in [`config/README.md`](config/README.md).

---

## Verification (R-vs-Python parity)

The Python resampler is verified against the legacy R/`spectrolab` script ([`archived_r_scripts/merge_resample_sig.R`](archived_r_scripts/merge_resample_sig.R)). Acceptance threshold: **1 × 10⁻³ absolute reflectance** (0.1 %, well below the HR-1024i radiometric noise floor). Historical results:

| Dataset | Samples | Max abs diff | Mean abs diff |
|---|---|---|---|
| Silver instrument (Serial 1202103) | 66 | 1.10 × 10⁻⁶ | 4.0 × 10⁻⁸ |
| Bronze instrument (Serial 2212118), `a4any_sb_2025-cn_ch-svc-aviris_bottom` | 15 | 9.4 × 10⁻⁷ | 3.4 × 10⁻⁸ |

Run the parity test (skipped automatically without reference data):

```bash
pytest tests/test_resampler_parity.py \
    --r-reference-csv=/path/to/r_output/merged_spectra.csv \
    --r-input-dir=/path/to/processed_sig_files/
```

To re-run parity on a new dataset, hand the prompt at [`docs/parity_retest_prompt.md`](docs/parity_retest_prompt.md) to any capable coding LLM. Full details in [`tests/README.md`](tests/README.md) and [`docs/README.md`](docs/README.md).

---

## Public Python API

The most-used entry points (all importable from their concrete modules — `pipeline/__init__.py` is intentionally empty):

```python
from pipeline.sig_processor import SigFileProcessor   # truncation + instrument inspection
from pipeline.resampler      import resample_spectra  # Stage-2 entry point
from pipeline.processor      import (
    SVCDataProcessor,      # chainable load/group/average
    SigSpectraAverager,    # facade — pass a DataFrame, get aggregated DataFrame back
    GroupSpec,             # GroupSpec.from_csv("naming_ids/<file>.csv")
    find_spectra_by_name,  # cross-DataFrame name search
)
```

Detailed signatures and behavioural notes in [`pipeline/README.md`](pipeline/README.md).

---

## For LLMs working in this repo

1. **Read [`FOLDER_STRUCTURE.md`](FOLDER_STRUCTURE.md) first** — it lists every directory and the reading order.
2. **Before modifying [`pipeline/resampler.py`](pipeline/resampler.py), re-read [`docs/supplementary_methods.md`](docs/supplementary_methods.md).** The constants `_FWHM_NM`, `_SIGMA_NM`, `_INTERP_WVL`, `_FIXED_SENSOR`, `_BAND_MIN`, `_BAND_MAX`, and the algorithm steps are load-bearing for the parity claim. Changing any of them requires re-running the parity test and writing a new `docs/parity_<dataset>_<date>.md`.
3. **The R script at [`archived_r_scripts/merge_resample_sig.R`](archived_r_scripts/merge_resample_sig.R) is frozen.** Treat it as a behavioural reference, not as live code to edit.
4. **Never commit machine paths or private data.** Use the placeholders already present in [`config/config.json`](config/config.json) and the notebooks.
5. **Run `pytest` after any change to `pipeline/`.** The parity test will skip if reference data is unavailable; the rest of the suite still runs.

---

## Requirements

Python ≥ 3.9 (used: 3.9 / 3.11). Dependencies pinned at the major-version level in [`requirements.txt`](requirements.txt):

- `numpy`, `scipy`, `pandas` — numerical core.
- `specdal` — kept for historical compatibility; not used by `resample_spectra`.
- `pytest>=8.3.0` — test runner.

R is **not** required for the production pipeline. It is needed only to regenerate Pipeline A parity references; see [`archived_r_scripts/README.md`](archived_r_scripts/README.md).
