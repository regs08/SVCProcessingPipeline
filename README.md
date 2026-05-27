# SIG Processing Pipeline

Pure-Python utilities for processing SIG spectra, resampling spectra, and aggregating summaries. `run_pipeline.py` is the single entry point, while `pipeline/resampler.py` performs the Python-based resampling (replacing the former R dependency).

## Quick Start
- Create and activate a virtual environment before installing requirements:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate  # (zsh/bash) or: . .venv/bin/activate
  python -m pip install -r requirements.txt
  ```
- Copy `config/config.json` (or create a similar run config) and update it with your own paths (see [Configuration](#configuration)).
- Execute the pipeline: `python run_pipeline.py --config config/config.json --verbose`.

## Pipeline Overview
- **Inputs**: Raw `.sig` files placed wherever `sig_input_dir` points (commonly under a private `data/` tree kept outside of version control).
- **Stage 1 — Python (SigFileProcessor)**: Cleans the files and writes processed spectra to `processed_dir` (usually `pipeline_outputs/sig_processed/<run>/`).
- **Stage 2 — Python (Resampler)**: Resamples the spectra using `pipeline/resampler.py`, producing per-run CSVs `merged_csv_name` inside `resampled_dir`.
- **Stage 3 — Python (Summary Writer)**: Generates a `*_processed_sig_summary.csv` that ties input ↔ processed files and captures the instrument/end-line metadata.
- **Orchestration**: `run_pipeline.py` glues the three stages together, logs progress, and exits early if validation fails (empty input dir, inconsistent instrument, etc.).

## Repository Layout
- `config/config.json` — Main run configuration consumed by `run_pipeline.py`.
- `config/calibrations/` — Optional per-project correction-type calibration files loaded by naming convention or explicit path.
- `pipeline/` — Python package containing all pipeline building blocks:
  - `sig_processor.py` — `SigFileProcessor`: truncates raw `.sig` files at the instrument end-line.
  - `processor.py` — `SVCDataProcessor` / `SigSpectraAverager`: grouping and averaging utilities.
  - `resampler.py` — `resample_spectra()`: pure-Python replacement for the former R resampling script.
- `pipeline_outputs/` — Default destination for `sig_processed/` and `sig_resampled/` artifacts (ignored by git).
- `notebooks/` — Visualization and exploratory analysis notebooks. They assume relative paths or placeholder strings that you should update locally.
- `naming_ids/` — Private lookup tables for weekly runs (ignored by git; keep your copies outside of commits).
- `tests/` — Pytest suite including the R-vs-Python parity check.

## Configuration
This repo ships with two different config file types:

- `config/config.json` (run config): controls input discovery, output folders, and filenames for each pipeline run.
- `config/calibrations/72424_Crittenden_SVC_Bronze.json` (calibration config): maps correction type to end-line values used by `SigFileProcessor`:
  ```json
  {
    "bronze": "2520.5",
    "silver": "2517.9"
  }
  ```

Run-config example (`config/config.json` style):

```json
{
  "sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>",
  "process_all_subdirs": true,
  "processed_dir": "sig_processed",
  "resampled_dir": "sig_resampled",
  "output_dir": "pipeline_outputs",
  "summary_csv_name": "processed_sig_summary.csv",
  "merged_csv_name": "merged_spectra.csv",
  "end_line_overrides": {
    "silver": "2517.9"
  }
}
```

- `sig_input_dir` points to your private raw-data folder. With `process_all_subdirs: true`, the pipeline processes each child directory that contains `.sig` files.
- `output_dir` is the top-level output root; `processed_dir` and `resampled_dir` are created under it, and each run gets a subfolder named after the input directory.
- `summary_csv_name` and `merged_csv_name` are suffix names; `run_pipeline.py` prefixes them with the input directory name.
- Optional `end_line_overrides` lets you supply custom correction values per instrument.
- Optional `correction_types_file` can point to a calibration JSON (same shape as files in `config/calibrations/`).

Calibration loading order in `run_pipeline.py`:
1. If `correction_types_file` is set in the run config, load that file.
2. Otherwise, try `config/calibrations/<input_dir_name>.json`.
3. If neither exists, use built-in defaults (`bronze: 2520.4`, `silver: 2517.9`).

## Running the Pipeline
1. Populate the directory referenced by `sig_input_dir` with one or more `.sig` files.
2. Run `python run_pipeline.py --config config/config.json --verbose`.
3. Inspect the logs — validation warnings (instrument mismatches, empty directories, etc.) are surfaced at the start.
4. Review outputs:
   - Processed `.sig` files under `processed_dir`.
   - `*_processed_sig_summary.csv` summarizing each processed file and instrument metadata.
   - Resampled CSV(s) inside `resampled_dir` created by `pipeline/resampler.py`.

## Parity Test (Python vs. former R pipeline)
A parity test confirms that the Python resampler produces values matching a reference CSV generated by the original R/spectrolab pipeline. It is skipped automatically in CI unless the reference data is provided.

```bash
pytest tests/test_resampler_parity.py \
    --r-reference-csv=/path/to/r_output/merged_spectra.csv \
    --r-input-dir=/path/to/processed_sig_files/
```

Or via environment variables:

```bash
R_REFERENCE_CSV=/path/to/r_output/merged_spectra.csv \
R_INPUT_DIR=/path/to/processed_sig_files/ \
pytest tests/test_resampler_parity.py
```

The default tolerance is 1e-3 (0.1% reflectance absolute difference). Override with `MAX_RESAMPLER_DIFF=<value>` if needed.

## Notebooks
`notebooks/sig_spectra_visualization.ipynb` offers quick plots over processed / resampled outputs. Update its placeholder strings (e.g., `<REPO_ROOT>/pipeline_outputs/...`) with your actual run folders before executing cells. Keep notebooks committed without personal paths; the placeholders ensure the public repo does not reveal your machine details.

## Testing
Run the full test suite with:
```bash
pytest
```
Add validation or alternative stages by subclassing components in `pipeline/`.
When automating deployments (Makefile, GitHub Actions, etc.), remember to set environment variables or copy config templates before execution.
