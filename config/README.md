# `config/` — Pipeline Configuration

Two distinct file types live here, both consumed by the installed
`svc-pipeline` console script:

1. **Run configs** (top-level files like [`config.json`](config.json)) — declare input/output paths and filenames for a pipeline run.
2. **Sensor calibration configs** ([`calibrations/`](calibrations/)) — map sensor/instrument types (e.g. `bronze`, `silver`) to the `.sig` end-line wavelength used by `SigFileProcessor` for truncation.

## Run config schema

`svc-pipeline` takes the run config as a positional argument (default
`config/config.json`); bare names resolve under `config/`, so `config.json`,
`config`, and `config/config.json` all work. The shipped template is
[`config.json`](config.json).

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
| `groups_csv` | string | **Optional.** Path (absolute or repo-relative) to a grouping CSV (`scans`/`scan_id` + `name` columns — see [`naming_ids/README.md`](../naming_ids/README.md)). When set, Stage 3 groups repeat scans of the same sample and averages them; overridable per-run with `--groups-csv`. |
| `group_agg_method` | string | **Optional**, default `"mean"`. One of `mean`/`median`/`sum`/`min`/`max`; overridable per-run with `--group-method`. |
| `grouped_csv_name` | string | **Optional**, default `"grouped_spectra.csv"`. Suffix for Stage 3's output CSV. Filename is `<input_dir_name>_<grouped_csv_name>`. Only produced when `groups_csv` is set. |

### `instrument` block (optional)

Inline instrument configuration — supersedes all other calibration sources when present.

```json
"instrument": {
  "bronze": { "end_line": "2520.4", "serial": "2212118" },
  "silver": { "end_line": "2517.9", "serial": "1202103" }
}
```

| Sub-key | Meaning |
|---|---|
| `end_line` | Wavelength string at which `SigFileProcessor` truncates the `.sig` data section. |
| `serial` | Instrument serial number used for consistency checking. |

Both sub-keys are optional. A flat shorthand `{"bronze": "2520.4"}` (end-line value only) is also accepted.  
Add or rename keys to register additional sensor types beyond `bronze` / `silver`.

### `processing` block (optional)

Algorithm parameters for Stage 2 (`resample_spectra`). All keys are optional; omitting a key uses the parity-verified default. **Changing any value from its default invalidates the R/`spectrolab` parity claim** — a warning is logged at runtime.

```json
"processing": {
  "band_min": 400,
  "band_max": 2500,
  "resample_fwhm_nm": 10.0,
  "splice_interp_wvl": [5.0, 2.0],
  "fixed_sensor": 2
}
```

| Key | Default | Meaning |
|---|---|---|
| `band_min` | `400` | First wavelength (nm) of the output 1 nm grid. |
| `band_max` | `2500` | Last wavelength (nm) of the output 1 nm grid. |
| `resample_fwhm_nm` | `10.0` | FWHM (nm) of the final Gaussian resample kernel (spectrolab `resample(fwhm=10)`). |
| `splice_interp_wvl` | `[5.0, 2.0]` | Half-window (nm) around each splice boundary used by `match_sensors` (spectrolab `interpolate_wvl`). |
| `fixed_sensor` | `2` | 1-based index of the sensor held fixed during `match_sensors` (spectrolab `fixed_sensor`). |

### Grouping / Stage 3 (optional)

```json
"groups_csv": "naming_ids/my_groups.csv",
"group_agg_method": "mean"
```

When `groups_csv` is set, `svc-pipeline --step all` (or a standalone
`--step 3`, once Stage 2 has already produced a merged CSV) reads that CSV
with `GroupSpec.from_csv()` and averages the named groups of repeat scans
with `SigSpectraAverager`, writing `<input_dir_name>_<grouped_csv_name>`
alongside the merged CSV. Both keys can be overridden per-run without
editing the config: `svc-pipeline --groups-csv path/to/groups.csv
--group-method median`. If `groups_csv` is absent, Stage 3 never runs — it's
fully opt-in and every existing config keeps working unchanged.

### Sensor calibration loading order
1. `instrument` block in the run config, if present — **highest priority**.
2. `sensor_calibration_file` in the run config, if present.
3. Otherwise: `config/calibrations/<input_dir_name>.json`, if it exists.
4. Otherwise: built-in defaults `{"bronze": "2520.4", "silver": "2517.9"}` from [`SigFileProcessor.DEFAULT_CORRECTION_TYPES`](../pipeline/sig_processor.py).

`end_line_overrides` (run config) is then applied on top.

## Sensor calibration config schema (`calibrations/*.json`)

Plain `{sensor_type: end_line_wavelength_string}` map:

```json
{
  "bronze": "2520.4",
  "silver": "2517.9"
}
```

Keys are normalized to lower case. Values are strings representing the wavelength at which a `.sig` file's data section ends (`SigFileProcessor` writes lines up to and including the line that begins with this value).

To create a new sensor calibration:
1. Drop a JSON file named `<input_dir_name>.json` into `calibrations/` to be picked up automatically, **or**
2. Reference an arbitrary file from your run config via `"sensor_calibration_file": "config/calibrations/<file>.json"`.

## Notes
- The shipped [`config.json`](config.json) uses placeholder `"<PATH_TO_SIG_INPUT_ROOT>"` — replace it locally; never commit machine paths.
- Output directories are created on demand; existing processed `.sig` files in the target directory are deleted at the start of each run.
- Built-in instrument numbers (`bronze: 2212118`, `silver: 1202103`) come from [`SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS`](../pipeline/sig_processor.py). They can be overridden for a run with the optional `instrument` block; calibration JSON files only map sensor type to truncation end-line.
