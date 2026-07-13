# Tutorial — Using the SIG Processing Pipeline

A hands-on guide for turning raw SVC HR-1024i `.sig` files into clean,
analysis-ready reflectance spectra. No prior experience with this codebase is
assumed.

There are **two ways to use this pipeline**, and this tutorial is built around
the first:

- **🌱 The notebook (gentle — start here).** The tutorial notebook
  [`notebooks/pipeline_demo.ipynb`](notebooks/pipeline_demo.ipynb) walks through
  the *entire* pipeline interactively and draws a plot at every step. You load
  your scans, clean them, and average them — all in one place, seeing exactly
  what happens. This is the recommended entry point for almost everyone.
- **⚙️ The command line (advanced).** A single terminal command, `svc-pipeline`,
  runs the cleanup across many folders at once and writes output CSVs — no plots,
  no clicking. Best once you have lots of data to process the same way every
  time. Covered in **Part B**.

> Most readers only need **Part A**. Come back for **Part B** when you're
> batch-processing data or want to script the pipeline.

---

## The big picture — what the pipeline does

The SVC HR-1024i is a field instrument that measures **reflectance** (how much
light a surface bounces back) across 400–2500 nm. It uses **three separate
detector arrays** that each cover part of the range and slightly overlap. Because
of that, a raw `.sig` file is not a clean curve — it has small seams ("splices")
where the detectors hand off to each other, and the wavelength axis even folds
backwards twice.

The pipeline fixes this in three stages:

```
   raw *.sig files
        │
        ▼
   ┌─────────────────────────────────────────────┐
   │ Stage 1 — Process / truncate                │  pipeline/sig_processor.py
   │   Check every file came from the same        │
   │   instrument, then trim each file at the     │
   │   calibrated end wavelength.                 │
   └─────────────────────────────────────────────┘
        │  truncated *.sig
        ▼
   ┌─────────────────────────────────────────────┐
   │ Stage 2 — Resample                          │  pipeline/resampler.py
   │   Trim the sensor overlaps, line the three   │
   │   detectors up, smooth out noise, and        │
   │   resample onto a clean 400–2500 nm grid     │
   │   at 1 nm spacing.                           │
   └─────────────────────────────────────────────┘
        │  clean spectra (rows = scans, 2101 columns = 400…2500 nm)
        ▼
   ┌─────────────────────────────────────────────┐
   │ Stage 3 — Group & average (optional)        │  pipeline/processor.py
   │   Combine repeat scans of the same sample    │
   │   into one averaged spectrum.                │
   └─────────────────────────────────────────────┘
```

### Two entry points — same stages

Here's the key thing to understand: **the notebook and the command line are two
different doors into the same three stages.** You don't need both.

| Path | What it runs | What you get | Best for |
|---|---|---|---|
| **🌱 Notebook** | Stages **1 → 2 → 3**, interactively, with a plot at each step | Figures **and** CSVs | Learning, checking a new dataset, exploring, making figures, small jobs |
| **⚙️ `svc-pipeline` (CLI)** | Stages **1 + 2**, and **3** too if you've set `groups_csv` in the config (or pass `--groups-csv`) | The merged CSV, plus a grouped/averaged CSV if Stage 3 ran; no plots | Processing many folders the same way, reproducibly |

The notebook does it all from inside Jupyter: its setup cell performs **Stage 1**,
the `.process()` calls perform **Stage 2**, and the averaging cell performs
**Stage 3**. So when you work in the notebook, you are running the complete
pipeline yourself — you never have to touch `svc-pipeline`. The CLI can now run
all three stages too, batch-style — see [B2](#b2-define-a-config) for
`groups_csv`.

**Input** (either path): a folder of `.sig` files.
**Output:** a CSV where each row is one scan and each column is one wavelength
(400, 401, … 2500 nm — 2101 columns).

### How to determine the Stage 1 end line

Determine the end line **after calibrating an instrument, and again whenever a
new SVC instrument is introduced**. The value is instrument-specific: it is the
**maximum wavelength in the data section of a raw `.sig` file**.

To find it manually:

1. Open a raw `.sig` file in a text editor and find the line `data=`. Everything
   below it is the scan data.
2. Read the **first column** below `data=`. This is the wavelength column; the
   other columns contain radiance and reflectance values.
3. Find the largest number in that first column. Keep the value exactly as it
   appears in the file, including its decimal place. That maximum is the
   `end_line` for the instrument.
4. Check several `.sig` files from the same instrument and calibration. They
   should have the same maximum wavelength. If they do not, stop and investigate
   the calibration or files instead of choosing one arbitrarily.

You can also calculate it with Python from the project folder. Replace the path
with one of your raw files:

```python
from pathlib import Path

sig_file = Path("path/to/one_scan.sig")
lines = sig_file.read_text(errors="replace").splitlines()
data_start = next(i for i, line in enumerate(lines) if line.strip() == "data=") + 1

wavelengths = []
for line in lines[data_start:]:
    columns = line.split()
    if columns:
        try:
            wavelengths.append((float(columns[0]), columns[0]))
        except ValueError:
            pass

_, end_line = max(wavelengths)
print(f"end_line = {end_line}")
```

For example, if the maximum first-column value is `2520.4`, configure the end
line as the string `"2520.4"`. Stage 1 keeps the data through that wavelength
and removes anything after it. This is a calibration/setup task—not a value you
need to rediscover for every routine processing run with the same calibrated
instrument.

---

# Part A — The gentle path: the tutorial notebook

This is the main event. By the end you'll have loaded scans, watched the cleanup
happen step by step, and saved averaged spectra — all without leaving Jupyter.

## A1. Get and open the notebook

You need a Python 3.11 notebook environment and a folder containing your raw
`.sig` scans. You can download
[`notebooks/pipeline_demo.ipynb`](notebooks/pipeline_demo.ipynb) by itself, or
clone the repository to keep the notebook, tutorial, configs, and tests together:

```bash
git clone https://github.com/regs08/SVCProcessingPipeline.git
cd SVCProcessingPipeline
```

The public repository intentionally excludes field `.sig` files because their
headers can contain GPS and time metadata. Copy your authorized scans into a
folder you control. If you place them beneath the clone's ignored `data/`
directory, this terminal command helps locate them:

```bash
find data -type f -name '*.sig' | head
```

Open the notebook and run its first code cell. It checks whether the notebook
helpers are already available; if not, it installs `svc-processing[demo]>=0.1.5`
into the current kernel. While that release is not yet available from PyPI, the
same setup cell falls back to installing from the public GitHub source archive.
No editable install, repository clone, or Python-path modification is needed.

> **Working from a repository clone?** `./setup.sh` is still available for
> contributors. It creates `.venv`, installs the project in editable mode,
> and installs JupyterLab. You still point `DATA_FOLDER` at your own scans.

## A2. Launch Jupyter locally (if needed)

If you do not already have an application that opens notebooks, install and
launch JupyterLab from the folder containing your downloaded notebook:

```bash
python3.11 -m pip install jupyterlab
jupyter lab
```

A browser tab opens; click `pipeline_demo.ipynb`. VS Code users can instead open
the file directly with the Python and Jupyter extensions.

## A3. How to run cells

A notebook is a stack of **cells** (boxes of code or text). Click a code cell and
press **Shift + Enter** to run it and move to the next. Run them **top to
bottom** — each builds on the one before. Output and plots appear right under the
cell that produced them.

Run the install, imports, and settings cells first. Set `DATA_FOLDER` to the
folder containing the scans—not to an individual `.sig` file. The preflight cell
prints the count and first filename. `config.prepare()` then performs **Stage 1**
by truncating those raw files into a working folder. The remaining parts mirror
the notebook.

## A4. Part 1 — a single spectrum, step by step

Loading one scan makes each stage easy to see.

```python
# Load one Stage 1 output into a Spectrum object and print a summary
single_spectrum = Spectrum.from_config(config)
print(single_spectrum)
```

The printout doubles as an **instrument check** — confirm `sensor count = 3` and
that the splice wavelengths sit near ~984 nm and ~1896 nm. If they don't, you're
probably pointing at the wrong data.

```python
single_spectrum.plot()                  # the RAW spectrum
```

You'll see a jagged line that **folds back on itself twice** — that's the three
detectors stored end-to-end, exactly the artifact the pipeline fixes.

```python
single_spectrum.process()               # run the cleanup (Stage 2)
single_spectrum.plot_processing_steps() # show the before/after
```

`plot_processing_steps()` draws **three panels** side by side:

1. **Raw** — the folded-back data, with the splice wavelengths marked as red
   dashed lines.
2. **After splice correction** — the three detectors lined up into one
   continuous curve.
3. **After smooth + resample** — the final, clean spectrum on the 400–2500 nm
   grid.

## A5. Part 2 — a whole folder

Now the same process runs on every scan at once, with two clean-up filters.

```python
collection = SpectraCollection.from_config(config)
print(collection)
collection.plot_raw()                    # all raw spectra overlaid
```

In that raw plot, the near-flat lines up near reflectance ≈ 1.0 are **white
reference panels** (measured before each set of leaves). You don't want those in
your analysis, so filter them out — and drop any obvious outliers too:

```python
collection.filter_reference_scans()      # remove the white panels
collection.filter_outliers()             # remove scans far from the group
```

Then process and look at the results:

```python
collection.process()                     # clean every remaining scan (Stage 2)
collection.plot_processing_steps(spectrum_index=0)   # 3-panel check on one scan
collection.plot()                        # all cleaned spectra overlaid
```

Finally, save them to a CSV (one row per scan, wavelength columns):

```python
spectra_path = save_spectra_csv(collection, OUTPUT_FOLDER / "spectra.csv")
print("Saved:", spectra_path)
```

## A6. Part 3 — group & average

Field measurements usually take **several scans of the same sample** (e.g. two
scans per leaf). This part averages those repeats into one spectrum per sample —
that's **Stage 3**.

```python
# 1. See which list position (index) each scan is at
for i, s in enumerate(collection.spectra):
    print(f"[{i}] {s.name}")

# 2. Define groups by 0-based index. This example pairs them up: (0,1), (2,3), …
groups = [
    tuple(range(i, min(i + 2, len(collection.spectra))))
    for i in range(0, len(collection.spectra), 2)
]

# 3. Average each group and plot individuals (faded) under their mean (bold)
pairs = average_pairs(collection, groups=groups)
plot_paired_averages(collection, pairs, groups=groups)

# 4. Save — one row per sample, wavelength columns
pairs.to_csv(OUTPUT_FOLDER / "spectra_paired.csv")
```

Edit the `groups` tuples to match how *your* measurements are organized — groups
can be any size, not just pairs.

## A7. Visualization cheat-sheet

| Call | What you see |
|---|---|
| `spectrum.plot()` | One spectrum (raw until you call `.process()`, then the cleaned version). |
| `spectrum.plot_processing_steps()` | Three panels: raw → splice-corrected → final. |
| `collection.plot_raw()` | Every raw scan overlaid; fold-backs and reference panels visible. |
| `collection.plot_processing_steps(spectrum_index=n)` | The 3-panel before/after for scan number `n`. |
| `collection.plot()` | Every cleaned scan overlaid on one chart. |
| `plot_paired_averages(collection, pairs, groups=groups)` | Individual scans faded under their bold group mean, one colour per group. |

> These friendly `Spectrum` / `SpectraCollection` helpers are installed from
> [`pipeline/notebook.py`](pipeline/notebook.py). Under the
> hood they call the same functions the command-line pipeline uses
> (`process_sig_file`, `resample_spectra` in
> [`pipeline/resampler.py`](pipeline/resampler.py)) — so the numbers you see in
> the notebook are identical to what the CLI would produce.

## A8. Using your own data in the notebook

The tutorial assumes you have raw scans. Configure them in the settings cells:

- Set `DATA_FOLDER` to your folder of raw `.sig` files.
- Leave `INSTRUMENT = "auto"` to detect the instrument from the file headers, or
  set it explicitly to `"bronze"` or `"silver"`.
- Set `END_LINE` to the exact string found with the
  [maximum-wavelength procedure](#how-to-determine-the-stage-1-end-line), such
  as `END_LINE = "2520.4"`. You may leave it as `None` only when the calibrated
  default already matches your instrument.

Everything downstream (load, filter, process, average, plot) works the same.

## A9. Where your results were saved

The notebook writes its CSVs under `pipeline_outputs/notebook_run/`:

- `spectra.csv` — every cleaned scan (Part 2).
- `spectra_paired.csv` — one averaged row per sample group (Part 3).
- `spectra_grouped.csv` — groups selected by scan number (Part 4).

Each file has one row per scan/group and wavelength columns 400 – 2500 nm. Open
them in Excel, pandas, or R for downstream analysis.

🎉 That's the whole pipeline. For most work, you can stop here.

---

# Part B — The advanced path: the command line

When you have many folders to process — or want a repeatable, scriptable run with
no notebook — use the `svc-pipeline` command. It runs **Stages 1 + 2** and writes
the merged CSV; add a `groups_csv` to the config (or pass `--groups-csv`) and it
runs **Stage 3** too, writing an averaged spectrum per group alongside it. No
config? Grouping/averaging is also available directly in the notebook or with
the [`pipeline/processor.py`](pipeline/processor.py) tools.

## B1. Install as a command-line tool

**If you're working from a clone of this repo** (development work), run the setup
script with `--dev` to add the test/lint tools on top of the demo ones:

```bash
./setup.sh --dev
```

That's the scripted equivalent of installing the full extras by hand:

```bash
python -m pip install -e ".[dev,demo]"
```

**If you just want the tool, with no repo clone**, install it from PyPI:

```bash
python -m pip install svc-processing
```

> **The PyPI package name and the terminal command are different words** — this
> trips people up. You `pip install svc-processing`, but the command you actually
> type is **`svc-pipeline`** (that's what `[project.scripts]` in `pyproject.toml`
> maps it to). There is no `svc-processing` command.

Either way, check it's available:

```bash
svc-pipeline --help
```

If you installed from PyPI with no repo clone, there's no `config/` folder to
copy a starter config from — see [B2](#b2-define-a-config) for
`svc-pipeline --init-config`, which generates one.

To build a distributable wheel or publish the package, see
[`docs/pip_packaging_guide.md`](docs/pip_packaging_guide.md).

## B2. Define a config

A **config** is a small JSON file telling the pipeline *where your data is* and
*where to put the results*. The shipped template is
[`config/config.json`](config/config.json):

> **Starting from a fresh `pip install svc-processing` with no repo clone?**
> There's no `config/config.json` to copy — run `svc-pipeline --init-config`
> in your project folder to generate the same starter template shown below,
> then edit it as described here.

```json
{
  "sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>",
  "process_all_subdirs": true,
  "processed_dir": "sig_processed",
  "resampled_dir": "sig_resampled",
  "output_dir": "pipeline_outputs",
  "summary_csv_name": "processed_sig_summary.csv",
  "merged_csv_name": "merged_spectra.csv",
  "end_line_overrides": {},

  "instrument": {
    "bronze": { "end_line": "2520.4", "serial": "2212118" },
    "silver": { "end_line": "2517.9", "serial": "1202103" }
  },

  "processing": {
    "band_min": 400,
    "band_max": 2500,
    "resample_fwhm_nm": 10.0,
    "splice_interp_wvl": [5.0, 2.0],
    "fixed_sensor": 2
  }
}
```

**The only line you must change** is `sig_input_dir` — point it at your folder of
`.sig` files. (Forget, and the pipeline stops with a clear message rather than
doing the wrong thing.)

**Where things go** (usually leave as-is):

| Key | What it does |
|---|---|
| `sig_input_dir` | Folder holding your raw `.sig` files (**change this**). |
| `process_all_subdirs` | If `true`, each sub-folder with `.sig` files is processed as its own dataset. `false` treats `sig_input_dir` itself as one dataset. |
| `output_dir` | Top folder for all results (default `pipeline_outputs/`). |
| `processed_dir` / `resampled_dir` | Sub-folders for Stage 1 and Stage 2 output. |
| `summary_csv_name` / `merged_csv_name` | Endings for the two output CSVs; the real filename is prefixed with your input folder's name. |

The **`instrument`** block maps each instrument to its truncation wavelength
(`end_line`) and `serial` number (used to confirm a folder isn't mixing
instruments). Set `end_line` using the
[maximum-wavelength procedure above](#how-to-determine-the-stage-1-end-line),
especially after calibration or when adding a new SVC instrument. The
**`processing`** block holds Stage 2's scientific parameters.

> ⚠️ **Leave the `processing` values at their defaults** unless you know exactly
> why you're changing them — they're numerically verified against the original R
> reference, and any change prints a warning that the guarantee no longer holds.
> Full key-by-key detail is in [`config/README.md`](config/README.md) and
> [`docs/in_depth_methods_and_config_guide.md`](docs/in_depth_methods_and_config_guide.md).

> **Don't commit private paths.** Keep the placeholder in the shared
> `config/config.json`; save your personal edited version under a different name.

**Optional — group repeat scans into one averaged spectrum per sample (Stage 3).**
Add two keys pointing at a grouping CSV (same schema used by
[`naming_ids/`](naming_ids/README.md)):

```json
"groups_csv": "naming_ids/my_groups.csv",
"group_agg_method": "mean"
```

With `groups_csv` set, running `svc-pipeline` also writes a grouped/averaged CSV
next to the merged one — no notebook needed. Omit both keys and Stage 3 simply
doesn't run (everything else works exactly as before).

**The groups CSV** has a `scans` (or `scan_id`) column and a `name` column:

```csv
scans,name
1;2,plotA_leaf1
3;4;5,plotA_leaf2
6,plotA_leaf3
```

> **The one thing that trips people up:** grouping happens *within a row*.
> Putting `1;2` in one cell averages scans 1 and 2 together into a single
> output row. Two *separate* rows that happen to share the same `name` do
> **not** get merged — you'd just get two un-averaged output rows with a
> duplicate name. Numbers in one cell can be separated by `;` or `,` (use `;`
> if your CSV itself is comma-delimited, to avoid needing to quote the cell).
> A row named `reference` (or marked in an optional `reference` column) is
> skipped entirely — handy for excluding a calibration panel scan.

## B3. Run it

To process the same folder from the command line, use `--input-dir` to skip
config editing:

```bash
svc-pipeline --input-dir /path/to/your/sig/folder
```

It prints the input directory and the files it produced. Look under
`pipeline_outputs/`:

```
pipeline_outputs/
├── sig_processed/<folder_name>/
│   ├── <truncated *.sig files>
│   └── <folder_name>_processed_sig_summary.csv
└── sig_resampled/<folder_name>/
    └── <folder_name>_merged_spectra.csv   ← your result
```

Once you've edited the config to point at your own data, just run:

```bash
svc-pipeline config.json
```

(A bare name resolves under `config/`, so `config.json` and `config/config.json`
both work.)

### The options you'll use

| Option | What it does |
|---|---|
| `config` | Which config file to use (positional, optional; default `config.json`). |
| `--input-dir <path>` | Process only this folder, ignoring the config's `sig_input_dir`. |
| `--step {1,2,3,all}` | `1` = Stage 1 only; `2` = Stage 2 only (Stage 1 must have run already); `3` = Stage 3 only (Stage 2 must have run already; requires `groups_csv`); `all` = every stage that's configured (default). |
| `--groups-csv <path>` | Group repeat scans and average them, using this CSV — overrides the config's `groups_csv` (or sets it if the config doesn't have one). |
| `--group-method {mean,median,sum,min,max}` | Aggregation method for Stage 3 (default `mean`) — overrides the config's `group_agg_method`. |
| `--verbose` | Print detailed progress messages — useful if something looks wrong. |

```bash
# Full run with detailed logging
svc-pipeline config.json --verbose

# Re-do only the resampling (Stage 2) without re-truncating every file
svc-pipeline config.json --step 2 --input-dir /path/to/your/sig/folder

# Group and average an already-resampled folder, without editing the config
svc-pipeline config.json --step 3 --groups-csv naming_ids/my_groups.csv
```

> **Heads-up:** each run **deletes** the previously processed `.sig` files in the
> target output folder before writing fresh ones, so results never get mixed.

---

## Troubleshooting

| Message / symptom | What it means & the fix |
|---|---|
| Notebook says no `.sig` files were found | Set `DATA_FOLDER` to the containing folder, confirm the files end in `.sig`, and re-run from the settings cell. |
| Notebook: `ModuleNotFoundError: pipeline.notebook` / `matplotlib` | Re-run the first setup/install cell in the current kernel. If PyPI reports that `svc-processing>=0.1.5` is unavailable, publish the release or make sure the public GitHub source archive contains these notebook-helper changes. |
| `jupyter: command not found` | Install the app: `python -m pip install jupyterlab`. |
| `svc-pipeline: command not found` | Your environment isn't active. Run `source .venv/bin/activate`. |
| `svc-processing: command not found` | That's the PyPI package name, not the command. The command is `svc-pipeline`. |
| `... still contains the placeholder "<PATH_TO_SIG_INPUT_ROOT>"` | You didn't set `sig_input_dir`. Edit the config, or pass `--input-dir <path>`. |
| `No SIG files found in ...` | The input folder has no `.sig` files. Check the path and that files end in `.sig`. |
| `Instrument mismatch detected; aborting processing.` | A folder mixes scans from different instruments. Split them into separate folders. |
| `Summary CSV not found ... (run --step 1 first)` | You ran `--step 2` before Stage 1. Run `--step all` (or `--step 1` then `--step 2`). |
| `Merged CSV not found ... (run --step 2 first)` | You ran `--step 3` before Stage 2. Run `--step all` (or `--step 1`, `--step 2`, then `--step 3`). |
| `Groups CSV not found: ...` | The `groups_csv` path (config or `--groups-csv`) doesn't exist. Check the path. |
| A warning that a `processing.*` value "differs from parity-verified default" | You changed a value in the `processing` block. Restore the defaults unless intentional. |

Add `--verbose` to any terminal run to see exactly what each stage is doing.

---

## Where to go next

| You want to… | Read |
|---|---|
| Look up every config key precisely | [`config/README.md`](config/README.md) |
| Understand the algorithm / cite the method | [`docs/supplementary_methods.md`](docs/supplementary_methods.md) |
| Know why each parameter is set the way it is | [`docs/in_depth_methods_and_config_guide.md`](docs/in_depth_methods_and_config_guide.md) |
| Call the pipeline from your own Python code | [`pipeline/README.md`](pipeline/README.md) |
| Build or publish the package | [`docs/pip_packaging_guide.md`](docs/pip_packaging_guide.md) |
| See the whole repo layout | [`FOLDER_STRUCTURE.md`](FOLDER_STRUCTURE.md) |
| Confirm the Python output matches the R reference | [`tests/README.md`](tests/README.md) |

Happy processing! 🌱
