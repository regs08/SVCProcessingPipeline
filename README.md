# Hybrid SIG Processing Pipeline

Hybrid Python ➜ R ➜ Python utilities for processing SIG spectra, resampling spectra in R, and aggregating summaries. `run_pipeline.py` is the single entry point (it builds Prefect tasks around the processing/resampling stages), while `merge_resample_sig.R` performs the R-based resampling.

## Quick Start
- Create and activate a virtual environment before installing requirements:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate  # (zsh/bash) or: . .venv/bin/activate
  python -m pip install -r requirements.txt
  ```
- Install R locally (e.g., `brew install r` on macOS) so `merge_resample_sig.R` can run through `Rscript`.
- Copy `config/weekly_data.json` (or create a similar run config) and update it with your own paths (see [Configuration](#configuration)).
- Execute the pipeline: `python run_pipeline.py --config config/<your_config>.json --verbose`.

## Pipeline Overview
- **Inputs**: Raw `.sig` files placed wherever `sig_input_dir` points (commonly under a private `data/` tree kept outside of version control).
- **Stage 1 — Python (SigFileProcessor)**: Cleans the files and writes processed spectra to `processed_dir` (usually `pipeline_outputs/sig_processed/<run>/`).
- **Stage 2 — R (`merge_resample_sig.R`)**: Resamples the spectra, producing per-run CSVs `merged_csv_name` inside `resampled_dir`.
- **Stage 3 — Python (Summary Writer)**: Generates a `*_processed_sig_summary.csv` that ties input ↔ processed files and captures the instrument/end-line metadata.
- **Orchestration**: `run_pipeline.py` glues the three stages together with Prefect tasks, logs progress, and exits early if validation fails (empty input dir, inconsistent instrument, missing scripts, etc.).

## Repository Layout
- `config/weekly_data.json` — Main run configuration consumed by `run_pipeline.py`.
- `config/calibrations/` — Optional per-project correction-type calibration files loaded by naming convention or explicit path.
- `merge_resample_sig.R` — R script that resamples SIG spectra and writes merged CSVs.
- `pipeline/` & `sig_preprocessor/` — Python building blocks that the orchestrator imports.
- `pipeline_outputs/` — Default destination for `sig_processed/` and `sig_resampled/` artifacts (ignored by git).
- `notebooks/` — Visualization and exploratory analysis notebooks. They assume relative paths or placeholder strings that you should update locally.
- `naming_ids/` — Private lookup tables for weekly runs (ignored by git; keep your copies outside of commits).

## Configuration
This repo ships with two different config file types:

- `config/weekly_data.json` (run config): controls input discovery, output folders, and filenames for each pipeline run.
- `config/calibrations/72424_Crittenden_SVC_Bronze.json` (calibration config): maps correction type to end-line values used by `SigFileProcessor`:
  ```json
  {
    "bronze": "2520.5",
    "silver": "2517.9"
  }
  ```

Run-config example (`config/weekly_data.json` style):

```json
{
  "sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>",
  "process_all_subdirs": true,
  "processed_dir": "sig_processed",
  "resampled_dir": "sig_resampled",
  "output_dir": "pipeline_outputs",
  "summary_csv_name": "processed_sig_summary.csv",
  "merge_script": "merge_resample_sig.R",
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
2. Ensure the `merge_script` path in your config resolves to the R script (relative or absolute).
3. Run `python run_pipeline.py --config config/<run>.json --verbose`.
4. Inspect the logs—Prefect will highlight validation warnings (instrument mismatches, empty directories, etc.).
5. Review outputs:
   - Processed `.sig` files under `processed_dir`.
   - `*_processed_sig_summary.csv` summarizing each processed file and instrument metadata.
   - Resampled CSV(s) inside `resampled_dir` created by `merge_resample_sig.R`.

## Notebooks
`notebooks/sig_spectra_visualization.ipynb` and `notebooks/spectral_change_analysis.ipynb` offer quick plots over processed / resampled outputs. Update their placeholder strings (e.g., `<REPO_ROOT>/pipeline_outputs/...`) with your actual run folders before executing cells. Keep notebooks committed without personal paths; the placeholders ensure the public repo does not reveal your machine details.

## Testing & Extensibility
- Lightweight Prefect orchestration tests live under `tests/` (invoke with `pytest` once you add tests).
- Add validation or alternative stages by subclassing components in `pipeline/stages.py`.
- When automating deployments (Makefile, GitHub Actions, etc.), remember to set environment variables or copy config templates before execution.
