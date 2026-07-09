# Tutorial — Using the SIG Processing Pipeline

A hands-on guide for turning raw SVC HR-1024i `.sig` files into clean,
analysis-ready reflectance spectra. No prior experience with this codebase is
assumed.

There are **two ways to use this pipeline**, and this tutorial is built around
the first:

- **🌱 The notebook (gentle — start here).** The demo notebook
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

---

# Part A — The gentle path: the demo notebook

This is the main event. By the end you'll have loaded scans, watched the cleanup
happen step by step, and saved averaged spectra — all without leaving Jupyter.

## A1. One-time setup

You need **Python 3.11**. Open a terminal in the project's top folder (the one
with `pyproject.toml`) and run these once:

```bash
# 1. Create an isolated environment so this project's packages
#    don't interfere with anything else on your machine.
python3.11 -m venv .venv

# 2. Activate it — your shell now uses this environment.
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

# 3. Install the pipeline, its science libraries, and Jupyter.
python -m pip install -e ".[demo]"
python -m pip install jupyterlab

# 4. Copy the bundled 15-scan example dataset into place.
python3 scripts/prepare_demo_data.py \
  --source-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom
```

That's all the terminal work for the gentle path — from here you live in the
notebook.

> **Tip — next time.** Each new terminal session, re-run
> `source .venv/bin/activate` first. You'll know it's active when your prompt
> shows `(.venv)`.

## A2. Open the notebook

Launch Jupyter from the project's top folder:

```bash
jupyter lab
```

A browser tab opens. Navigate to `notebooks/pipeline_demo.ipynb` and click it.

> Prefer VS Code? Its Python + Jupyter extensions open `.ipynb` files directly —
> just pick the `.venv` environment as the kernel.

## A3. How to run cells

A notebook is a stack of **cells** (boxes of code or text). Click a code cell and
press **Shift + Enter** to run it and move to the next. Run them **top to
bottom** — each builds on the one before. Output and plots appear right under the
cell that produced them.

Run the first few cells (imports and paths). The **paths** cell is where
**Stage 1** happens: it truncates the raw demo files into a working folder.
You'll see it print where the raw and processed spectra live. Then follow the
three parts below — they mirror the notebook exactly.

## A4. Part 1 — a single spectrum, step by step

Loading one scan makes each stage easy to see.

```python
# Load one scan into a Spectrum object and print a summary
single_spectrum = Spectrum(next(SPECTRA_FOLDER.glob("*.sig")))
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
collection = SpectraCollection(SPECTRA_FOLDER)
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

> These friendly `Spectrum` / `SpectraCollection` helpers live in
> [`notebooks/pipeline_demo/svc.py`](notebooks/pipeline_demo/svc.py). Under the
> hood they call the same functions the command-line pipeline uses
> (`process_sig_file`, `resample_spectra` in
> [`pipeline/resampler.py`](pipeline/resampler.py)) — so the numbers you see in
> the notebook are identical to what the CLI would produce.

## A8. Using your own data in the notebook

The notebook is wired to the demo dataset, but pointing it at your own scans is a
two-line change in the setup cells:

- Set `RAW_SPECTRA_FOLDER` to your folder of `.sig` files (instead of the
  verified demo folder).
- In the **paths** cell, change `correction_type="bronze"` to your instrument
  (`"bronze"` or `"silver"`) so Stage 1 trims at the right wavelength.

Everything downstream (load, filter, process, average, plot) works the same.

## A9. Where your results were saved

The notebook writes its CSVs under `pipeline_outputs/csv_exports/`:

- `spectra.csv` — every cleaned scan (Part 2).
- `spectra_paired.csv` — one averaged row per sample group (Part 3).

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

**If you're working from a clone of this repo** (development work), install the
full extras (adds the test/lint tools on top of the demo ones):

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
instruments). The **`processing`** block holds Stage 2's scientific parameters.

> ⚠️ **Leave the `processing` values at their defaults** unless you know exactly
> why you're changing them — they're numerically verified against the original R
> reference, and any change prints a warning that the guarantee no longer holds.
> Full key-by-key detail is in [`config/README.md`](config/README.md) and
> [`docs/in_depth_methods_and_config_guide.md`](docs/in_depth_methods_and_config_guide.md).

> **Don't commit private paths.** Keep the placeholder in the shared
> `config/config.json`; save your personal edited version under a different name.

**Optional — group repeat scans into one averaged spectrum per sample (Stage 3).**
Add two keys pointing at a grouping CSV (same `scan_id`/`scans` + `name` schema
described in [`naming_ids/README.md`](naming_ids/README.md)):

```json
"groups_csv": "naming_ids/my_groups.csv",
"group_agg_method": "mean"
```

With `groups_csv` set, running `svc-pipeline` also writes a grouped/averaged CSV
next to the merged one — no notebook needed. Omit both keys and Stage 3 simply
doesn't run (everything else works exactly as before).

## B3. Run it

Try it immediately on the bundled example — `--input-dir` points at a folder
directly and skips the placeholder check, so no config editing is needed:

```bash
svc-pipeline --input-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom
```

It prints the input directory and the files it produced. Look under
`pipeline_outputs/`:

```
pipeline_outputs/
├── sig_processed/a4any_sb_2025-cn_ch-svc-aviris_bottom/
│   ├── <15 truncated *.sig files>
│   └── a4any_sb_2025-cn_ch-svc-aviris_bottom_processed_sig_summary.csv
└── sig_resampled/a4any_sb_2025-cn_ch-svc-aviris_bottom/
    └── a4any_sb_2025-cn_ch-svc-aviris_bottom_merged_spectra.csv   ← your result
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
svc-pipeline config.json --step 2 --input-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom

# Group and average an already-resampled folder, without editing the config
svc-pipeline config.json --step 3 --groups-csv naming_ids/my_groups.csv
```

> **Heads-up:** each run **deletes** the previously processed `.sig` files in the
> target output folder before writing fresh ones, so results never get mixed.

---

## Troubleshooting

| Message / symptom | What it means & the fix |
|---|---|
| Demo data "missing" or "failed manifest verification" | Run `python3 scripts/prepare_demo_data.py --source-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom`. |
| Notebook: `ModuleNotFoundError: pipeline` / `matplotlib` | Your environment isn't installed/active. Re-run the **A1** setup, and select the `.venv` kernel in Jupyter. |
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
