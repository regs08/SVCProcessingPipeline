# Hybrid SIG Processing Pipeline

Hybrid Python ➜ R ➜ Python utilities for processing SIG spectra, resampling spectra in R, and aggregating summaries. `run_pipeline.py` is the single entry point, while `merge_resample_sig.R` performs the R-based resampling.

## Quick Start
- Create and activate a virtual environment before installing requirements:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate  # (zsh/bash) or: . .venv/bin/activate
  python -m pip install -r requirements.txt
  ```
- If you see `zsh: command not found: activate` or `zsh: command not found: pip`, you didn’t activate the venv in the current shell. Either run `source .venv/bin/activate` first, or skip activation and use `./.venv/bin/python -m pip install -r requirements.txt`.
- Install R locally (e.g., `brew install r` on macOS) so `merge_resample_sig.R` can run through `Rscript`.
- Copy one of the templates under `config/` and update it with your own paths (see [Configuration](#configuration)).
- Execute the pipeline (steps 1+2): `python run_pipeline.py --config config/<your_config>.json --verbose`.
- Execute only step 1 (process + summary CSV): `python run_pipeline.py --config config/<your_config>.json --step 1 --verbose`.
- Execute only step 2 (R resampling): `python run_pipeline.py --config config/<your_config>.json --step 2 --verbose`.
- To run a single dataset without editing your config, add `--input-dir "<PATH_TO_DATASET_DIR>"`.

## Pipeline Overview
- **Inputs**: Raw `.sig` files placed wherever `sig_input_dir` points (commonly under a private `data/` tree kept outside of version control).
- **Stage 1 — Python (SigFileProcessor)**: Cleans the files, writes processed spectra to `processed_dir`, and writes a `*_processed_sig_summary.csv` tying input ↔ processed files plus instrument/end-line metadata.
- **Stage 2 — R (`merge_resample_sig.R`)**: Resamples the spectra, producing per-run CSVs `merged_csv_name` inside `resampled_dir`.
- **Orchestration**: `run_pipeline.py` glues the steps together, logs progress, and exits early if validation fails (empty input dir, inconsistent instrument, missing scripts, etc.).

## Repository Layout
- `config/` — JSON run configurations; copy & edit to register your own datasets.
- `merge_resample_sig.R` — R script that resamples SIG spectra and writes merged CSVs.
- `pipeline/` & `sig_preprocessor/` — Python building blocks that the orchestrator imports.
- `pipeline_outputs/` — Default destination for `sig_processed/` and `sig_resampled/` artifacts (ignored by git).
- `notebooks/` — Visualization and exploratory analysis notebooks. They assume relative paths or placeholder strings that you should update locally.
- `naming_ids/` — Private lookup tables for weekly runs (ignored by git; keep your copies outside of commits).

## Configuration
Each config JSON must provide the directories and filenames the flow needs. We recommend naming the config after the project, e.g. `config/<project_name>.json`.

```json
{
  "sig_input_dir": "<PATH_TO_SIG_INPUT_DIR_OR_ROOT>",
  "process_all_subdirs": false,
  "output_dir": "pipeline_outputs",
  "processed_dir": "sig_processed",
  "resampled_dir": "sig_resampled",
  "summary_csv_name": "processed_sig_summary.csv",
  "merged_csv_name": "merged_spectra.csv",
  "merge_script": "merge_resample_sig.R",
  "end_line_overrides": {},
  "verbose": false
}
```

- Keep secrets and absolute machine paths out of committed configs; use placeholders (as shown) or derive paths from environment variables.
- `sig_input_dir` is the only path that must reference your private data location; the rest can stay relative to the repository (when relative, they are resolved under `output_dir`).
- Set `process_all_subdirs` to `true` if `sig_input_dir` is a root folder containing multiple immediate subfolders (each with `.sig` files) that should be processed in one run.
- The pipeline will automatically load `config/calibrations/<project_name>.json` if it exists (where `<project_name>` is the basename of `sig_input_dir`).
- Optional `correction_types_file` can be set to point to a specific calibration JSON if you don’t want the default auto-discovery behavior.
- Optional `end_line_overrides` (a dict like `{"bronze": "2520.5"}`) overrides the loaded defaults for that run.

### Project calibration (end-line values)
End-line values can change by year/project depending on calibration. For each project, create a calibration file named after the project under `config/calibrations/` (see `config/calibrations/PROJECT_TEMPLATE.json`).

- Name the file: `config/calibrations/<project_name>.json`
- The file should map correction types to end-line values (strings), e.g. `bronze` and `silver`.
- The end-line value should match the **starting wavelength value of the last data row** in a representative `.sig` file for that correction type (i.e., the first column of the last line).
- Within a project, all Bronze measurements should share the same last wavelength, and all Silver measurements should share the same last wavelength.

## Running the Pipeline
1. Populate the directory referenced by `sig_input_dir` with one or more `.sig` files.
2. Ensure the `merge_script` path in your config resolves to the R script (relative or absolute).
3. Run `python run_pipeline.py --config config/<run>.json --verbose`.
4. Inspect the logs—warnings will highlight validation issues (instrument mismatches, empty directories, etc.).
5. Review outputs:
   - Processed `.sig` files under `processed_dir`.
   - `*_processed_sig_summary.csv` summarizing each processed file and instrument metadata.
   - Resampled CSV(s) inside `resampled_dir` created by `merge_resample_sig.R`.

## Notebooks
`notebooks/sig_spectra_visualization.ipynb` and `notebooks/spectral_change_analysis.ipynb` offer quick plots over processed / resampled outputs. Update their placeholder strings (e.g., `<REPO_ROOT>/pipeline_outputs/...`) with your actual run folders before executing cells. Keep notebooks committed without personal paths; the placeholders ensure the public repo does not reveal your machine details.

## Testing & Extensibility
- Lightweight tests can live under `tests/` (invoke with `pytest` once you add tests).
- Add validation or alternative stages by subclassing components in `pipeline/stages.py`.
- When automating deployments (Makefile, GitHub Actions, etc.), remember to set environment variables or copy config templates before execution.
