# `pipeline/` — Core Python Package

Pure-Python building blocks for the SVC HR-1024i SIG processing pipeline. Every
stage lives in this package; the `svc-pipeline` console script calls
[`cli.main()`](cli.py). The CLI layer (`cli` -> `run_config` -> `runner`) wires
the run config to the two science modules (`sig_processor`, `resampler`).

## Modules

### [`cli.py`](cli.py) — command-line interface (`main`)
Thin glue, no config or processing logic of its own: parses arguments, configures logging, and for each input directory wires a `RunConfig` to a `Pipeline`. Installed as `svc-pipeline`.

### [`run_config.py`](run_config.py) — `RunConfig`, `PipelineSettings`
Encapsulates *what to run*. `RunConfig.load(repo_root, name, logger)` resolves the config path (bare names fall back under [`config/`](../config/) and gain a `.json` suffix), parses + validates the JSON, and exposes:

- `RunConfig.write_starter_config(base_dir)` (classmethod) — write a starter `config/config.json` (same template as the one shipped in this repo) under `base_dir`; refuses to overwrite an existing file. Backs `svc-pipeline --init-config`, which is how an installed-from-PyPI user (no repo clone, so no `config/` directory to copy) gets a starting template.
- `.ensure_no_placeholder(input_dir_override)` — abort with guidance if the template's `<PATH_TO_SIG_INPUT_ROOT>` was never edited.
- `.input_directories()` — expand `sig_input_dir` / `sig_input_dirs` / `process_all_subdirs` into the directories to process.
- `.processing_params()` — the `processing` block merged over the parity-verified defaults (cached; warns once on any non-parity value).
- `.settings_for(input_dir, *, verbose, groups_csv_override=None, group_method_override=None)` — build the per-directory `PipelineSettings` (a frozen dataclass of resolved input/output paths + `processing_params` + resolved `correction_types`/`instrument_numbers` + resolved `groups_csv`/`group_agg_method`/`grouped_csv_name`). Internally resolves `SigFileProcessor`'s end-line/serial tables for this directory (priority: inline `instrument` block > `sensor_calibration_file` > `config/calibrations/<dir>.json` > built-in defaults) as plain dicts — it does not mutate `SigFileProcessor.DEFAULT_CORRECTION_TYPES`/`DEFAULT_INSTRUMENT_NUMBERS`, so calibration is resolved fresh per directory with no shared global state between runs. `groups_csv` is `None` (Stage 3 skipped) unless the config's `groups_csv` key or a `--groups-csv` override is set.

### [`runner.py`](runner.py) — `Pipeline`
Encapsulates *doing the work*. `Pipeline(settings, logger).run(step)` runs the requested stage(s) and returns `{"summary_csv": …, "merged_csv": …, "grouped_csv": …}`:

- `.process_sig_files()` — Stage 1: instrument-consistency check, truncate each `.sig` at the calibration end-line, write the summary CSV.
- `.resample(summary_csv)` — Stage 2: call `resample_spectra` with the config's `processing_params`.
- `.group_and_average(merged_csv)` — Stage 3, optional (only runs when `settings.groups_csv` is set): reads groups via `GroupSpec.from_csv()` and averages repeat scans with `SigSpectraAverager`, writing `grouped_csv_name`. `step="3"` re-runs this alone against an already-existing merged CSV; `step="all"` runs it automatically whenever `groups_csv` is configured.

### [`sig_processor.py`](sig_processor.py) — `SigFileProcessor`
Truncates and inspects raw `.sig` ASCII files emitted by the SVC HR-1024i instrument.

- `DEFAULT_CORRECTION_TYPES` — built-in sensor calibration end-line values: `{"bronze": "2520.4", "silver": "2517.9"}` (units: nm, used as the trailing-line wavelength at which truncation stops). Class-wide fallback only — `RunConfig` never mutates this at runtime; see `correction_types`/`instrument_numbers` below.
- `DEFAULT_INSTRUMENT_NUMBERS` — known serial numbers: `{"bronze": "2212118", "silver": "1202103"}`. Same fallback-only status as `DEFAULT_CORRECTION_TYPES`.
- `parse_correction_types_file(config_path)` — static method that parses a sensor-calibration JSON file (same shape as files in [`config/calibrations/`](../config/calibrations/)) into a plain `correction_type -> end_line` dict, without touching any class state. This is what `RunConfig.settings_for()` uses to resolve per-directory calibration.
- `load_default_correction_types(config_path)` — classmethod that overwrites `DEFAULT_CORRECTION_TYPES` from a sensor calibration JSON file (delegates to `parse_correction_types_file`). Mutates class-wide state on purpose — intended for direct, explicit use (e.g. in a notebook), not for per-run resolution.
- `__init__(correction_value=…, correction_type=…, correction_config=…, correction_types=…, instrument_numbers=…, logger=…)` — three mutually exclusive ways to specify the correction itself. `correction_value` is the explicit end-line wavelength string; `correction_type` is one of the registered names (`bronze` / `silver`), looked up in `correction_types`/`instrument_numbers` if supplied, else the class-wide `DEFAULT_CORRECTION_TYPES`/`DEFAULT_INSTRUMENT_NUMBERS`; `correction_config` is a dict with keys `end_line`, `instrument_number`, `name`. `correction_types`/`instrument_numbers` let a caller (e.g. `RunConfig`) inject a per-instance calibration table instead of relying on shared class state. `logger`, if supplied, routes verbose/error messages through it instead of `print()`.
- `process_sig_files(input_folder, output_folder, verbose=False)` — iterate every `.sig` in `input_folder`, write a truncated copy to `output_folder`. Truncation keeps lines up to and including the first line that starts with `end_line_value`.
- `check_instrument_consistency(folder_path)` — returns a dict with keys `consistent`, `instrument`, `instrument_name`, `files_by_instrument`, `total_files`, `warnings`. Used by the orchestrator to abort early when a folder mixes instruments.
- `extract_instrument_from_file(file_path)` / `get_file_metadata(file_path)` — header parsers (read the `instrument=…` line or the full `key=value` header block respectively).
- `get_supported_correction_types()` — the correction-type names this instance knows about (e.g. `['bronze', 'silver']`, or whatever was injected via `correction_types=`/loaded via `load_default_correction_types`). The end-line value, correction type, and instrument number themselves are plain public attributes (`.end_line_value`, `.correction_type`, `.instrument_number`) — read them directly rather than through a getter.

The class instance never holds spectral data; it streams files line-by-line and writes to disk. Safe to instantiate per directory.

### [`resampler.py`](resampler.py) — `process_sig_file(...)`, `resample_spectra(...)`
Pure-Python replacement for the archived R/`spectrolab` resampling script. Replicates the exact algorithm of `read_spectra → guess_splice_at → match_sensors → smooth → resample(fwhm=10)`:

1. **`_read_sig(path)`** — parses the `data=` section of a `.sig` file. Column 4 (target reflectance %) is divided by 100 to give fractional reflectance. Exact-duplicate wavelengths at sensor boundaries are perturbed by `1.2357e-5 × min(|diff(non-duplicate bands)|)` (mirrors `spectrolab::i_bands`).
2. **`_sensor_segment_indices(wls)`** — detects sensor segments via backward jumps in the wavelength sequence.
3. **`_guess_splice_at(segments, wls)`** — computes splice wavelengths as `(2i·λ_next_start + λ_curr_end) / (2i + 1)` for each adjacent sensor pair (1-based `i`).
4. **`_trim_and_assign(...)`** — trims each sensor at its splice so adjacent sensors do not overlap (matches `spectrolab::i_trim_sensor_overlap`).
5. **`_apply_match_sensors(...)`** — applies a linearly-varying multiplicative ramp to Sensor 1 only (the `iter = 1` branch of `match_sensors`). Sensor 2 is the radiometric reference; Sensor 3 is left unchanged.
6. **`_smooth_fwhm(wls, rfs)`** — resolution-matched Gaussian smoothing with per-band FWHM derived from local band spacing, k-means quantized into 3 clusters (one per sensor), then doubled. Matches `spectrolab::smooth_fwhm`.
7. **`_gaussian_resample(wls, rfs, target, sigma)`** — Gaussian-weighted resampling onto `400:2500` at 1 nm spacing with FWHM = 10 nm (`σ ≈ 4.25 nm`).

Public entry points:

- `process_sig_file(path, ...)` returns a frozen `ProcessedSpectrum` dataclass
  containing the raw arrays, sensor/splice diagnostics, corrected arrays, output
  wavelengths, and output reflectance for one file. This is the supported API for
  notebooks or demos that need intermediate arrays.
- `resample_spectra(input_dir, output_dir, output_filename, ...)` processes every
  `.sig` file in a directory and writes a CSV at `output_dir / output_filename`
  with rows = sample names (`.sig` stem), columns = integer wavelengths 400–2500.
  It delegates to `process_sig_file()` and returns the `Path` to the written file.

Constants (top of module): `_FWHM_NM = 10.0`, `_INTERP_WVL = (5.0, 2.0)`, `_FIXED_SENSOR = 2`, `_BAND_MIN = 400`, `_BAND_MAX = 2500`. Do not edit these without re-running the parity test in [`tests/`](../tests/). (Gaussian sigma is derived from `_FWHM_NM` via `_sigma_from_fwhm()`, not stored as a separate constant.)

### [`processor.py`](processor.py) — `SVCDataProcessor`, `SigSpectraAverager`, `GroupSpec`, `find_spectra_by_name`
Post-resampling utilities for grouping and averaging spectra. Not invoked by the
production CLI; intended for use in notebooks and ad-hoc analysis.

- **`GroupSpec(members, name=None)`** — frozen dataclass describing one group of scans. `GroupSpec.from_csv(path, …)` loads a list of group specs from a [`naming_ids/`](../naming_ids/) CSV (`scan_id` / `scans` and `name` columns); rows named `reference` are skipped automatically.
- **`SVCDataProcessor`** — chainable processor:
  - `.load_csv(path, **kwargs)` → load wavelength matrix.
  - `.split_columns(name_col=None)` → identify wavelength vs metadata columns.
  - `.extract_sig_entries()` → parse `base_name` and trailing numeric index from each sample-name cell. Sample-name normalization pads the numeric suffix to 4 digits (e.g. `leaf.3` → `leaf.0003`).
  - `.group_by(groups, by='number'|'index')` → bucket entries into the supplied groups, warning on ungrouped entries.
  - `.average_groups(cols=None, agg_method='mean'|'median'|'sum'|'min'|'max', name_strategy='base_first'|'first_cell'|'concat_base', override_names=…)` → aggregate each group; result lives in `self.grouped_df`.
  - `.concat_grouped_and_ungrouped(ungrouped_mode='raw'|'empty')` → stitch grouped + ungrouped into `self.final_df`.
  - `.save_csv(path)` → write `grouped_df`.
- **`SigSpectraAverager(df, sample_col='sample_name')`** — facade that normalizes sample names and runs the load/split/extract chain in one step. `.aggregate(groups, method='mean'|None, …)` returns a DataFrame; `method=None` returns the raw rows (no aggregation).
- **`find_spectra_by_name(dataframes, search_key, *, name_column='name', case_sensitive=False, exact_match=False)`** — search across multiple frames; results are annotated with a `_source_index` column.

### [`__init__.py`](__init__.py)
Empty marker. Import classes from their concrete modules (e.g. `from pipeline.sig_processor import SigFileProcessor`).

## Adding a new stage
Subclass `SigFileProcessor` (truncation/inspection) or wrap `resample_spectra` to insert pre-/post-processing. Keep numerical constants in `resampler.py` aligned with the algorithm documented in [`docs/supplementary_methods.md`](../docs/supplementary_methods.md); changing them invalidates the parity claim and the parity test in [`tests/test_resampler_parity.py`](../tests/test_resampler_parity.py) must be re-run.
