# Refactor Plan — Simplify the Pipeline Entry Point

**Status:** superseded by the 2026-06-03 CLI/run-config refactor and packaging work.
Kept as historical context only; do not treat the line references below as
current evidence without re-running them.
**Author of plan:** audit pass, 2026-06-02
**For:** the next instance / contributor who implements these changes
**Scope:** how a user *enters* the pipeline (the CLI), plus the documentation and
folder-structure drift that the entry-point audit uncovered. The numerical core
(`pipeline/resampler.py`, `pipeline/sig_processor.py`) is **out of scope** — do
not touch the parity-verified algorithm.

---

## 1. Objective

Make the canonical invocation this simple:

```bash
python3 run_pipeline.py config.json
```

and make the zero-argument form work too:

```bash
python3 run_pipeline.py            # uses config/config.json by default
```

Today neither works cleanly. The current documented command is
`python run_pipeline.py --config config/config.json --verbose`, and the bare
form crashes (see §2).

> Note on the literal target `python3 run_pipeline config.json` (no `.py`):
> dropping the extension requires either packaging (a `svc-pipeline` console
> script) or a wrapper shim. That is treated as an **optional follow-on** in
> §6. The 99% win — positional config, working default, no required flags — is
> delivered entirely by §4 with `run_pipeline.py` kept as-is.

---

## 2. Audit findings (current state, with evidence)

### Entry-point friction

| # | Finding | Evidence |
|---|---|---|
| A | **The CLI default config points at a file that does not exist.** `--config` defaults to `config/weekly_data.json`, but there is no such file in the repo. So a bare `python3 run_pipeline.py` throws an uncaught `FileNotFoundError` traceback. | `run_pipeline.py:394`; confirmed `config/weekly_data.json` absent |
| B | **Config is a verbose `--config` flag, not a positional argument.** User must type `--config config/config.json`. | `run_pipeline.py:392-396` |
| C | **The user must include the `config/` directory prefix.** A bare `config.json` resolves to `<repo>/config.json` (missing), because `_resolve_under` anchors at repo root with no `config/` fallback. | `run_pipeline.py:79-83`, `:420` |
| D | **No friendly errors.** `_load_json` lets `FileNotFoundError` / `json.JSONDecodeError` bubble up as a stack trace. A first-time user who runs the broken default or typos a path gets a traceback, not guidance. | `run_pipeline.py:71-76` |
| E | **The placeholder config silently "succeeds with nothing."** The shipped `config.json` has `"sig_input_dir": "<PATH_TO_SIG_INPUT_ROOT>"`. If a user runs it unedited, the run logs "Input directory missing …" and prints "not produced" rather than a clear "you need to edit your config" message. | `config/config.json:2`; `run_pipeline.py:266-268`, `:458-464` |
| F | **The docs apologize for the broken default instead of fixing it.** Both READMEs tell the user to "always pass `--config` explicitly" — a design smell that this refactor removes. | `README.md:95`, `config/README.md:10` |

### Documentation / structure drift (uncovered while auditing the entry path)

| # | Finding | Evidence |
|---|---|---|
| G | **README install/run commands use the old verbose form** and must be rewritten to the new simple form. | `README.md:35`, `:85`, `:90`, `:95` |
| H | **Broken doc links to deleted files.** `notebooks/README.md` is deleted (staged `D`), yet `README.md` and `FOLDER_STRUCTURE.md` still link to it. | `README.md:19`; `FOLDER_STRUCTURE.md:43,45,67` |
| I | **`FOLDER_STRUCTURE.md` tree is stale.** It lists `sig_spectra_visualization.ipynb` / `notebooks/README.md` (both deleted) and omits what actually exists now: `notebooks/pipeline_demo.ipynb` and the `notebooks/pipeline_demo/` package (`__init__.py`, `svc.py`). It also omits `docs/pip_packaging_guide.md`. | `git status`; `git ls-files notebooks/`; `FOLDER_STRUCTURE.md:43-47` |
| J | **`config/calibrations/` is now empty.** The only calibration JSON was deleted (staged `D`). Git does not track empty dirs, so on a fresh clone the directory disappears even though the auto-inference feature (`config/calibrations/<input_dir_name>.json`) still references it. | `git status`; `run_pipeline.py:155-161`; `ls config/calibrations/` |
| K | **`parity_retest_prompt.md` references `config/weekly_data.json`** as the config to use — same dead file as (A). | `docs/parity_retest_prompt.md:75` |

### Minor (note, not blocking)

| # | Finding | Evidence |
|---|---|---|
| L | **Confusing operator precedence in the parity-warning condition.** The expression `value != default and value != tuple(default) if isinstance(default, list) else value != default` relies on `and` binding tighter than the ternary. It happens to produce correct results today, but it is fragile and hard to read. Optional cleanup only. | `run_pipeline.py:179` |

---

## 3. Summary of proposed changes

1. **CLI:** make `config` a positional arg (default `config.json`); resolve bare
   names against `config/`; keep `--config` as a deprecated hidden alias for one
   release. (§4)
2. **Guards:** friendly errors for missing/invalid config and for the unedited
   `<PATH_TO_SIG_INPUT_ROOT>` placeholder. (§4)
3. **Docs:** rewrite the run commands in `README.md`, `config/README.md`,
   `docs/parity_retest_prompt.md` to the new form; fix broken links. (§5)
4. **Structure:** sync `FOLDER_STRUCTURE.md` to reality; add `config/calibrations/.gitkeep`. (§5)
5. **Optional:** reconcile and correct `docs/pip_packaging_guide.md`; if packaging
   is pursued, expose a real `svc-pipeline` console command. (§6)

---

## 4. Part 1 — CLI entry point (the core change)

**File:** `run_pipeline.py`

### 4a. Positional config with a working default + `config/` fallback

Replace the `--config` argument in `_parse_args` (`run_pipeline.py:392-396`) with a
positional, and add a dedicated resolver. Target resolution behaviour:

| User types | Resolves to |
|---|---|
| *(nothing)* | `<repo>/config/config.json` |
| `config.json` | `<repo>/config/config.json` (via `config/` fallback) |
| `config` | `<repo>/config/config.json` (auto-append `.json`) |
| `config/config.json` | `<repo>/config/config.json` (explicit relative) |
| `/abs/path.json` | `/abs/path.json` |

Resolution is anchored at `repo_root = Path(__file__).resolve().parent`, so it is
independent of the current working directory (preserves today's behaviour).

Reference implementation to paste in:

```python
def _resolve_config(repo_root: Path, value: str) -> Path:
    """Resolve a run-config argument with friendly fallbacks.

    Tries, in order: the path as given (relative to repo root), the same name
    under config/, and the same again with a .json suffix appended.
    """
    raw = Path(value).expanduser()
    if raw.is_absolute():
        candidates = [raw]
    else:
        names = [raw]
        if raw.suffix == "":
            names.append(raw.with_suffix(".json"))
        candidates = []
        for n in names:
            candidates.append(repo_root / n)        # e.g. <repo>/config.json
            candidates.append(repo_root / "config" / n)  # e.g. <repo>/config/config.json
    for c in candidates:
        if c.is_file():
            return c
    available = sorted(p.name for p in (repo_root / "config").glob("*.json"))
    raise SystemExit(
        f"Config not found: '{value}'.\n"
        f"  Tried: {', '.join(str(c) for c in candidates)}\n"
        f"  Available in config/: {', '.join(available) or '(none)'}\n"
        f"  Usage: python3 run_pipeline.py [CONFIG] [--step ...] [--verbose]"
    )
```

And in `_parse_args`:

```python
parser.add_argument(
    "config",
    nargs="?",
    default="config.json",
    help="Run-config JSON. Bare names resolve under config/ (default: config.json).",
)
# Deprecated alias — keep for one release so existing scripts/cron don't break.
parser.add_argument("--config", dest="config_flag", help=argparse.SUPPRESS)
```

In `main` (`run_pipeline.py:415-421`), pick the flag if present (with a warning),
else the positional, then resolve:

```python
args = _parse_args()
repo_root = Path(__file__).resolve().parent
logger = _configure_logging(args.verbose)

config_arg = args.config
if getattr(args, "config_flag", None):
    logger.warning("--config is deprecated; pass the config as a positional argument: "
                   "python3 run_pipeline.py %s", args.config_flag)
    config_arg = args.config_flag

config_path = _resolve_config(repo_root, str(config_arg))
config = _load_json(config_path)
logger.info("Using config: %s", config_path)
```

> This delivers findings A, B, C, and F at once.

### 4b. Friendly errors for a broken/invalid config (finding D)

Wrap the load so the user gets a message, not a traceback. Update `_load_json`
(`run_pipeline.py:71-76`):

```python
def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.expanduser().open() as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise SystemExit(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a JSON object: {path}")
    return data
```

(`_resolve_config` already prevents the missing-file case, but keep this for
explicit/absolute paths and malformed JSON.)

### 4c. Guard the unedited placeholder (finding E)

After loading the config in `main`, before the per-directory loop
(`run_pipeline.py:432`), fail fast with guidance if the template was never edited:

```python
PLACEHOLDER = "<PATH_TO_SIG_INPUT_ROOT>"
raw_inputs = [config.get("sig_input_dir"), *(config.get("sig_input_dirs") or [])]
if not args.input_dir and any(v == PLACEHOLDER for v in raw_inputs if v):
    raise SystemExit(
        f"{config_path} still contains the placeholder \"{PLACEHOLDER}\".\n"
        f"  Edit \"sig_input_dir\" to point at your .sig data directory, "
        f"or pass --input-dir <path>."
    )
```

### 4d. (Optional) clarify the parity-warning condition (finding L)

If touching `_load_processing_params` anyway, replace `run_pipeline.py:179` with a
readable form that does not depend on ternary/`and` precedence:

```python
default_cmp = tuple(default) if isinstance(default, list) else default
if value != default_cmp:
    logger.warning(...)
```

Behaviour-preserving; do **not** change `_PARITY_DEFAULTS` values.

### Acceptance checks for Part 1

```bash
# 1. zero-arg uses config/config.json (will then hit the placeholder guard 4c)
python3 run_pipeline.py
# 2. bare name resolves under config/
python3 run_pipeline.py config.json
# 3. extensionless name
python3 run_pipeline.py config
# 4. explicit relative path still works
python3 run_pipeline.py config/config.json
# 5. typo gives a friendly message + lists available configs (no traceback)
python3 run_pipeline.py nope.json
# 6. deprecated flag still works, with a warning
python3 run_pipeline.py --config config/config.json
# 7. a real run end-to-end against a tmp .sig dir
python3 run_pipeline.py config.json --input-dir /path/to/sig --verbose
```

---

## 5. Part 2 — Documentation & structure sync

These are mechanical edits that must land **with** the CLI change so the docs
match the binary.

### 5a. `README.md`
- `:30-36` Quick start → replace run line with `python3 run_pipeline.py config.json`
  (after editing `sig_input_dir`).
- `:84-95` "Running the pipeline" → `python3 run_pipeline.py [config] [options]`;
  change the options table row from `--config <path>` to a `config` positional;
  delete the `:95` paragraph about the `weekly_data.json` default entirely.
- `:19` Repository-map row for `notebooks/` → drop the dead `notebooks/README.md`
  link; point at `notebooks/pipeline_demo.ipynb` (the current demo).

### 5b. `config/README.md`
- `:10` → rewrite: "`run_pipeline.py` takes the run config as a positional
  argument (default `config/config.json`); bare names resolve under `config/`."
  Remove the `weekly_data.json` mention.

### 5c. `docs/parity_retest_prompt.md`
- `:74-75` → replace `config/weekly_data.json` and the `--config`/`--input-dir`
  example with the new positional form.

### 5d. `FOLDER_STRUCTURE.md` (finding I, H)
- `:43-47` notebooks block → reflect reality:
  - `pipeline_demo.ipynb` (tracked)
  - `pipeline_demo/` package: `__init__.py`, `svc.py`
  - remove `sig_spectra_visualization.ipynb` and the `notebooks/README.md` line
- `:67` reading-order step 8 → drop the `notebooks/README.md` link.
- `:33-37` docs block → add `pip_packaging_guide.md`.
- `:11` line is fine (`run_pipeline.py` still the only top-level script).
- Confirm the deletions are intentional and committed (see §7).

### 5e. `config/calibrations/.gitkeep` (finding J)
- Add an empty `config/calibrations/.gitkeep` so the auto-inference directory
  survives a fresh clone. Optionally add a one-line `config/calibrations/README.md`
  pointing back to `config/README.md §"Sensor calibration config schema"`.

---

## 6. Part 3 — Packaging (optional follow-on; only if `python3 run_pipeline` w/o `.py` is wanted)

There is an in-flight `docs/pip_packaging_guide.md`. If packaging is pursued, it
both (a) yields a true bare command `svc-pipeline config.json` and (b) needs
three corrections before it will work:

1. **Wrong build backend.** The guide's
   `build-backend = "setuptools.backends.legacy:build"` is invalid and will make
   `python -m build` fail. Correct value: `build-backend = "setuptools.build_meta"`.
2. **The console script won't be importable as written.** `[project.scripts]
   svc-pipeline = "run_pipeline:main"` requires the top-level `run_pipeline.py`
   module to be packaged, but the guide only includes `pipeline*`. Add:
   ```toml
   [tool.setuptools]
   py-modules = ["run_pipeline"]
   ```
3. **`pipeline/__init__.py` import names are wrong.** The guide suggests
   `from .processor import SvcProcessor` / `Resampler` / `SigProcessor`. The real
   public names are `SVCDataProcessor`, `resample_spectra`, `SigFileProcessor`
   (see `README.md:135-146`). `pipeline/__init__.py` is currently *intentionally
   empty*; if it is populated, use the correct names or imports will crash.

If packaging lands, update the README "Quick start" to show `pip install -e .`
then `svc-pipeline config.json`. **Recommendation:** do Parts 1–2 first (they are
small and high-value); treat packaging as a separate later PR.

---

## 7. Pre-existing uncommitted changes (resolve before/with this work)

`git status` at audit time shows a half-finished cleanup already in the tree.
Decide and commit these so the refactor starts from a clean base:

```
 M FOLDER_STRUCTURE.md            # will be edited again here (§5d)
 M config/README.md               # will be edited again here (§5b)
 D config/calibrations/72424_Crittenden_SVC_Bronze.json   # confirm intentional; see §5e
 M config/config.json             # end_line bronze 2520.5 -> 2520.4; confirm correct value
 M pipeline/resampler.py          # OUT OF SCOPE — review separately; do not bundle w/ CLI change
 M run_pipeline.py                # confirm what changed vs. this plan's edits
 D notebooks/README.md            # breaks links in README/FOLDER_STRUCTURE (fixed in §5)
 D notebooks/sig_spectra_tutorial.ipynb
 D notebooks/sig_spectra_visualization.ipynb
?? docs/pip_packaging_guide.md    # untracked; see §6
```

⚠️ `pipeline/resampler.py` is modified and is the **parity-critical** file. Keep it
out of the entry-point commit; if its change is intentional, it needs its own
review + a parity re-run (`tests/test_resampler_parity.py`) per `README.md:155`.

---

## 8. Suggested commit sequence

1. **Land the in-flight cleanup** (or revert it) so the base is clean — esp.
   decide on the notebook/calibration deletions. Add `config/calibrations/.gitkeep`.
2. **CLI commit:** `run_pipeline.py` §4a–4c (+ optional 4d). Title:
   "Make config a positional arg with a working default and friendly errors."
3. **Docs commit:** §5a–5d. Title: "Sync docs/structure to the simplified CLI."
4. *(later, separate PR)* packaging §6.
5. *(separate, with parity re-run)* whatever `pipeline/resampler.py` change is.

Run `pytest` after step 2 (`README.md:158`). The parity test skips without
reference data; the rest of the suite must stay green.

---

## 9. Out of scope (do not change here)
- The resampling algorithm / constants in `pipeline/resampler.py`,
  `pipeline/sig_processor.py` (`_FWHM_NM`, `_SIGMA_NM`, `_INTERP_WVL`,
  `_FIXED_SENSOR`, `_BAND_MIN`, `_BAND_MAX`) — load-bearing for the parity claim.
- `_PARITY_DEFAULTS` values in `run_pipeline.py:24-30`.
- The R reference in `archived_r_scripts/` (frozen).
