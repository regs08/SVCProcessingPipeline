# `config/` — Pipeline Configuration

Two distinct file types live here, both consumed by [`run_pipeline.py`](../run_pipeline.py):

1. **Run configs** (top-level files like [`config.json`](config.json)) — declare input/output paths and filenames for a pipeline run.
2. **Sensor calibration configs** ([`calibrations/`](calibrations/)) — map sensor/instrument types (e.g. `bronze`, `silver`) to the `.sig` end-line wavelength used by `SigFileProcessor` for truncation.

## Run config schema

`run_pipeline.py` loads the run config via `--config <path>` (default at the CLI level is `config/weekly_data.json`, but the shipped template is [`config.json`](config.json) — pass it explicitly).

```json
{
  "sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>",
  "process_all_subdirs": true,
  "processed_dir": "sig_processed",
  "resampled_dir": "sig_resampled",
  "output_dir": "pipeline_outputs",
  "summary_csv_name": "processed_sig_summary.csv",
  "merged_csv_name": "merged_spectra.csv",
  "end_line_overrides": {}
}
```

| Key | Type | Meaning |
|---|---|---|
| `sig_input_dir` | string | Root directory containing raw `.sig` files (or subdirectories of them). |
| `sig_input_dirs` | string \| list | **Optional.** Explicit list of input directories; supersedes `sig_input_dir` and `process_all_subdirs`. Strings may be `;`-delimited. |
| `process_all_subdirs` | bool | When `true`, every child directory of `sig_input_dir` that contains at least one `.sig` file is processed as its own run. |
| `processed_dir` | string | Subdirectory of `output_dir` where truncated `.sig` files are written. A subfolder named after the input dir is created underneath. |
| `resampled_dir` | string | Subdirectory of `output_dir` where the merged resampled CSV is written. Same per-input-dir layout. |
| `output_dir` | string | Top-level output root; resolved relative to the repo root when not absolute. |
| `summary_csv_name` | string | Suffix for the per-run summary CSV. The actual filename is `<input_dir_name>_<summary_csv_name>`. |
| `merged_csv_name` | string | Suffix for the resampler output CSV. Filename is `<input_dir_name>_<merged_csv_name>`. |
| `end_line_overrides` | object | **Optional.** `{sensor_type: end_line_value}` pairs that override the sensor calibration file / built-in defaults. Keys are lower-cased. |
| `sensor_calibration_file` | string | **Optional.** Path (absolute or repo-relative) to a sensor calibration JSON. Takes precedence over the auto-inferred file. |
| `correction_types_file` | string | **Optional legacy alias.** Older name for `sensor_calibration_file`; still supported for compatibility. |

### Sensor calibration loading order (in `run_pipeline.py`)
1. `sensor_calibration_file` in the run config, if present. The legacy `correction_types_file` key is also accepted.
2. Otherwise: `config/calibrations/<input_dir_name>.json`, if it exists.
3. Otherwise: built-in defaults `{"bronze": "2520.4", "silver": "2517.9"}` from [`SigFileProcessor.DEFAULT_CORRECTION_TYPES`](../pipeline/sig_processor.py).

`end_line_overrides` (run config) is then applied on top.

## Sensor calibration config schema (`calibrations/*.json`)

Plain `{sensor_type: end_line_wavelength_string}` map:

```json
{
  "bronze": "2520.5",
  "silver": "2517.9"
}
```

Keys are normalized to lower case. Values are strings representing the wavelength at which a `.sig` file's data section ends (`SigFileProcessor` writes lines up to and including the line that begins with this value).

### Shipped sensor calibration file

- [`calibrations/72424_Crittenden_SVC_Bronze.json`](calibrations/72424_Crittenden_SVC_Bronze.json) — site/instrument-specific overrides for the 7/24/24 Crittenden Bronze run.

To create a new sensor calibration:
1. Drop a JSON file named `<input_dir_name>.json` into `calibrations/` to be picked up automatically, **or**
2. Reference an arbitrary file from your run config via `"sensor_calibration_file": "config/calibrations/<file>.json"`.

## Notes
- The shipped [`config.json`](config.json) uses placeholder `"<PATH_TO_SIG_INPUT_ROOT>"` — replace it locally; never commit machine paths.
- Output directories are created on demand; existing processed `.sig` files in the target directory are deleted at the start of each run.
- Built-in instrument numbers (`bronze: 2212118`, `silver: 1202103`) come from [`SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS`](../pipeline/sig_processor.py) and are not configurable via these files.
