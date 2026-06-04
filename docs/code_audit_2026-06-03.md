# Code Audit Report — SVC HR-1024i SIG Processing Pipeline

Audit date: 2026-06-03  
Repository: `svcProcessingPipeline`  
Scope: audit-only review of architecture, code quality, reproducibility, notebook runnability, testing, and research presentability. No source code was modified.

## Executive Summary

The repository contains a small, understandable production pipeline with a clean acyclic dependency graph and a well-isolated numerical core. The strongest engineering asset is `pipeline/resampler.py`, which has a documented R/`spectrolab` parity harness and repeated local execution produced deterministic output on the local six-file demo set. The largest research-readiness gaps are reproducibility and demo runnability: the notebook depends on ignored `.sig` data, fails during headless execution on the local demo set, and a fresh clone does not include the demo data required by the notebook. Documentation overstates reproducibility: `docs/supplementary_methods.md` claims exact pinned manifests, `renv.lock`, seeded k-means determinism, and public `.sig` data availability, but the tracked repository has no exact pins, no `renv.lock`, no tracked `.sig` data, and the Python implementation uses `scipy.cluster.vq.kmeans` without an explicit seed. Static quality is mixed: `ruff` reports 9 findings, tracked-file `pyflakes` reports 6 findings, and convention conformance varies sharply between the newer CLI/config/runner modules and older `sig_processor.py`, `processor.py`, and notebook helper code. Testing is currently narrow: the only tracked test is the parity test, and it skips when reference data are absent. As-is, the repository is not yet presentable as a research-level software-availability artifact without caveats; the shortest path to "yes" is to make the notebook runnable from tracked or externally documented data, make dependency/parity claims reproducible, add focused unit tests around non-numeric orchestration, and add a lint/test CI gate.

## Overall Scorecard

| Dimension | Rating | One-line justification |
|---|---|---|
| A. Separation of Concerns & Architecture | Good | Production imports are acyclic and layered, but the demo helper imports seven private resampler functions. |
| B. Object-Oriented Design | Needs work | Core classes are cohesive enough, but calibration uses mutable class state and `SVCDataProcessor` relies on chain-mutated attributes/assertions. |
| C. Dead / Unused Code & Dependencies | Needs work | `ruff`, `pyflakes`, and `vulture` all report tracked-source issues; `specdal` is declared but not imported, while `matplotlib` is imported but undeclared. |
| D. Coding-Framework Consistency | Needs work | Only 46% of files use future annotations, 54% have module docstrings, and only 44% of applicable files fully type public signatures. |
| E. Folder & Repo Hygiene | Needs work | `.gitignore` protects data, but documented `naming_ids/README.md` is absent, tracked docs contain a machine path, and packaging/CI files are absent. |
| F. Terminal Runnability & Reproducibility | Needs work | CLI guard paths are friendly, but exact dependency and parity-reproducibility claims are not reproducible from tracked files. |
| G. Demo Notebook | Deficient | Headless execution fails; required demo `.sig` files are ignored symlinks, not tracked fresh-clone data. |
| H. Testing & Verification | Deficient | Only `pipeline/resampler.py` is referenced by tracked tests, and the parity test skips without external reference data. |
| I. Research Presentability | Needs work | Strong methods prose exists, but several claims are not backed by the tracked artifact and fresh-clone rerun path is incomplete. |

## Findings Table

| ID | Severity | Dimension | Evidence | Finding | Recommendation |
|---|---|---|---|---|---|
| F-01 | Critical | G, I | `notebooks/pipeline_demo.ipynb:72`, `notebooks/pipeline_demo.ipynb:74`, `.gitignore:24` | **Defect:** the demo notebook points to `pipeline_demo/demo_data/spectra`, but `.sig` files are globally ignored and no demo data are tracked. A fresh clone cannot run the notebook as documented. | **Parity-safe:** either track a minimal non-private demo dataset or document/download it with a checksum and setup cell. |
| F-02 | Critical | G | `notebooks/pipeline_demo.ipynb:388`, `notebooks/pipeline_demo.ipynb:391`, `notebooks/pipeline_demo/svc.py:761` | **Defect:** the notebook hard-codes `(4, 5)` but local demo execution had only indices `0-4`, causing an `IndexError` and two downstream `NameError` cells. | **Parity-safe:** derive default groups from collection length or ship demo data matching the notebook. |
| F-03 | Critical | F, I | `docs/supplementary_methods.md:96`, `requirements.txt:1`, `requirements.txt:5` | **Defect:** the methods claim exact pinned manifests and `renv.lock`, but `requirements.txt` has 0/5 exact pins and no `renv.lock` is tracked. | **Parity-safe:** add exact lock/snapshot files or revise the methods claim to match the repository. |
| F-04 | Major | A, G | `notebooks/pipeline_demo/svc.py:21`, `notebooks/pipeline_demo/svc.py:29` | **Defect:** the demo imports seven private `_...` functions from `pipeline.resampler`, coupling user-facing notebook code to non-public implementation details. | **Parity-safe:** expose a public single-spectrum processing helper or public intermediate API from production code. |
| F-05 | Major | A, G | `pipeline/resampler.py:24`, `pipeline/resampler.py:321`, `pipeline/resampler.py:353`, `notebooks/pipeline_demo/svc.py:116` | **Defect:** production computes exact sigma from FWHM, while the demo calls `_gaussian_resample` without `sigma` and therefore uses `_FWHM_NM / 2.355`; local max demo-vs-production diff was `9.6e-7`. | **Parity-sensitive if changing numeric defaults; parity-safe if demo passes production's computed sigma or reuses a public production helper.** |
| F-06 | Major | B, F | `pipeline/run_config.py:212`, `pipeline/run_config.py:213`, `pipeline/run_config.py:251`, `pipeline/run_config.py:254` | **Defect:** `RunConfig.apply_sensor_calibrations()` mutates `SigFileProcessor` class attributes, so calibration is process-global and affects subsequent instances. | **Parity-safe:** pass calibration maps into `SigFileProcessor` instances or an immutable settings object instead of mutating class defaults. |
| F-07 | Major | H | `tests/test_resampler_parity.py:17`, `tests/README.md:10`, `tests/README.md:37` | **Defect:** the only tracked test skips without external reference data; non-resampler modules have no direct tracked tests. | **Parity-safe:** add unit tests for config resolution, runner dispatch, truncation, grouping, and notebook helper behavior; keep parity data optional but add a small non-private fixture. |
| F-08 | Major | C, F | `requirements.txt:1`, `README.md:165`, `notebooks/pipeline_demo/svc.py:15` | **Defect:** `specdal` is declared but not imported anywhere in tracked Python; `matplotlib` is imported by the demo helper but absent from `requirements.txt`. | **Parity-safe:** move optional/demo dependencies to an extra or add `matplotlib`; remove or justify `specdal` outside runtime requirements. |
| F-09 | Major | E, I | `docs/parity_a4any_sb_2025-cn_ch-svc-aviris_bottom_2026-05-27.md:7` | **Defect:** a tracked parity report contains a machine-specific path under `/Users/nr466/Downloads`. | **Parity-safe:** replace machine paths with project-relative placeholders or external dataset identifiers. |
| F-10 | Major | E | `README.md:5`, `FOLDER_STRUCTURE.md:3`, `README.md:20`, `FOLDER_STRUCTURE.md:72` | **Defect:** docs claim every directory has a README and link to `naming_ids/README.md`, but `naming_ids/` is ignored and absent from tracked files. | **Parity-safe:** track a non-sensitive `naming_ids/README.md` via a `.gitignore` exception or remove those links. |
| F-11 | Major | C, D | `pipeline/sig_processor.py:5`, `pipeline/resampler.py:129`, `notebooks/pipeline_demo/svc.py:692`, `tests/test_resampler_parity.py:33` | **Defect:** tracked-source lint finds unused imports and locals; `ruff` reports 9 issues and tracked-file `pyflakes` reports 6. | **Parity-safe for unused imports/locals; rerun parity only if touching numerical code behavior.** |
| F-12 | Major | F, I | `docs/supplementary_methods.md:48`, `pipeline/resampler.py:19`, `pipeline/resampler.py:248` | **Defect:** methods say smoothing uses `scipy.cluster.vq.kmeans2` and seeded k-means; code imports and calls `kmeans`, with no explicit seed. | **Parity-sensitive:** either correct the prose to `kmeans`/observed determinism or change code only with parity re-run. |
| F-13 | Minor | D | `pipeline/processor.py:109`, `pipeline/processor.py:181`, `pipeline/processor.py:185` | **Defect:** `SVCDataProcessor` uses assertions for runtime sequencing and globally overwrites `warnings.formatwarning`, making behavior less testable and process-local stateful. | **Parity-safe:** replace assertions with explicit exceptions and use local warning formatting only where needed. |
| F-14 | Minor | D | `notebooks/pipeline_demo/svc.py:17`, `notebooks/pipeline_demo/svc.py:19`, `notebooks/pipeline_demo/svc.py:21` | **Defect:** the notebook helper mutates `sys.path` before pipeline imports, producing `ruff` E402 and making imports dependent on execution context. | **Parity-safe:** use package installation/editable install guidance or notebook-relative import setup in one explicit bootstrap cell. |
| F-15 | Minor | E, F | `docs/pip_packaging_guide.md:32`, `docs/pip_packaging_guide.md:45`, `docs/pip_packaging_guide.md:47` | **Defect:** untracked packaging guide recommends a console script target and public exports that do not match current code names. | **Parity-safe:** do not commit as-is; revise if packaging work is accepted. |
| F-16 | Minor | E | `refactor.md:27`, `refactor.md:45`, `refactor.md:49` | **Defect:** untracked refactor notes describe older CLI failures that current Phase 2 runs disproved. | **Parity-safe:** archive as historical notes or update before committing. |
| F-17 | Nit | D | `pipeline/processor.py:389`, `pipeline/sig_processor.py:69`, `pipeline/run_config.py:197` | **Subjective preference:** line length is inconsistent; 9/13 files have lines over 88 characters. | **Parity-safe:** add `ruff format`/Black-compatible formatting policy; avoid numeric edits in parity-sensitive code unless parity is rerun. |

## A. Architecture And Dependency Graph

The production package has a clear layered flow: `run_pipeline.py` is a 14-line shim into `pipeline.cli.main()` (`run_pipeline.py:11`), `pipeline.cli` parses arguments and invokes `RunConfig`/`Pipeline` (`pipeline/cli.py:20`, `pipeline/cli.py:21`, `pipeline/cli.py:87`), and `Pipeline` delegates Stage 1 to `SigFileProcessor` and Stage 2 to `resample_spectra` (`pipeline/runner.py:23`, `pipeline/runner.py:25`, `pipeline/runner.py:117`, `pipeline/runner.py:178`). The AST dependency graph found no import cycles.

| Source | Internal dependency |
|---|---|
| `run_pipeline.py` | `pipeline/cli.py` |
| `pipeline/cli.py` | `pipeline/run_config.py`, `pipeline/runner.py` |
| `pipeline/run_config.py` | `pipeline/sig_processor.py` |
| `pipeline/runner.py` | `pipeline/resampler.py`, `pipeline/run_config.py`, `pipeline/sig_processor.py` |
| `tests/test_resampler_parity.py` | `pipeline/resampler.py` |
| `notebooks/pipeline_demo/svc.py` | `pipeline/resampler.py` private helpers; `pipeline/processor.py` |

The notable architectural issue is the demo/production boundary. `notebooks/pipeline_demo/svc.py` imports `_read_sig`, `_sensor_segment_indices`, `_guess_splice_at`, `_trim_and_assign`, `_apply_match_sensors`, `_smooth_fwhm`, and `_gaussian_resample` directly (`notebooks/pipeline_demo/svc.py:21` through `notebooks/pipeline_demo/svc.py:29`). This is not duplicated algorithm code, which lowers divergence risk, but it is still a leaky abstraction because the notebook relies on private function names and defaults. Local ignored demo data showed the demo and production paths were close but not identical: 6 samples x 2101 wavelengths, max absolute difference `9.6e-7`, mean `3.5e-8`. The likely cause is the sigma difference identified in F-05.

## B. Object-Oriented Design

`PipelineSettings` is a frozen dataclass with resolved paths and processing parameters (`pipeline/run_config.py:45`, `pipeline/run_config.py:49` through `pipeline/run_config.py:57`), which is a good fit for orchestration. `RunConfig` is cohesive around config loading and derived settings, but its calibration application mutates global class defaults on `SigFileProcessor` (`pipeline/run_config.py:212`, `pipeline/run_config.py:251`). An empirical check confirmed that after applying a custom bronze calibration, a new `SigFileProcessor(correction_type="bronze")` used the custom values until another config reset them. This is re-entrant only by convention and makes concurrent or nested runs harder to reason about.

`SigFileProcessor` itself is reasonably cohesive for truncation and metadata inspection, but it stores calibration tables as class attributes (`pipeline/sig_processor.py:12`, `pipeline/sig_processor.py:17`) and `load_default_correction_types()` overwrites them (`pipeline/sig_processor.py:52`). `SVCDataProcessor` is a chainable mutable object: `load_csv()` creates `self.df` (`pipeline/processor.py:104`), `split_columns()` depends on it via `assert` (`pipeline/processor.py:109`), and later methods depend on attributes created by previous steps. That style is workable for notebooks but less explicit and less testable than returning immutable intermediate results or validating state with explicit exceptions. The global assignment to `warnings.formatwarning` in `group_by()` (`pipeline/processor.py:185`) is especially broad for a library helper.

## C. Dead Code, Unused Code, And Dependencies

Tool versions and runs:

- `ruff 0.15.0`; `ruff check .` reported 9 findings.
- `pyflakes 3.4.0`; literal `pyflakes .` traversed `.venv`, so tracked-file diagnostic was also run and reported 6 findings.
- `vulture 2.16`; literal `vulture . --min-confidence 80` traversed `.venv`, so tracked-file diagnostic was also run and reported 2 findings.
- `python3 -m py_compile $(git ls-files '*.py')` initially failed due sandboxed bytecode cache writes, then passed when `PYTHONPYCACHEPREFIX` was set to `/private/tmp`.

Tracked-source examples include unused imports in `pipeline/sig_processor.py:5`, unused `n_sensors` in `pipeline/resampler.py:129`, unused `bar_colors` in `notebooks/pipeline_demo/svc.py:692`, and unused `numpy` in `tests/test_resampler_parity.py:33`. Dependency audit found that `requirements.txt` declares `specdal` (`requirements.txt:1`) but no tracked Python file imports it; conversely `notebooks/pipeline_demo/svc.py` imports `matplotlib.pyplot` (`notebooks/pipeline_demo/svc.py:15`) but `requirements.txt` does not declare `matplotlib`.

## D. Coding Framework Consistency

Per-file conformance matrix:

| File | Future annotations | Module docstring | Docstring style | Public signatures typed | Imports | Naming | Logging/print | Error handling | Line length |
|---|---:|---:|---|---:|---|---|---|---|---|
| `notebooks/pipeline_demo/__init__.py` | no | no | missing | n/a | ok | ok | neither | no raises | max 0; >88 0 |
| `notebooks/pipeline_demo/svc.py` | yes | yes | mixed | 21/22 | late imports | ok | print 3 | raises `FileNotFoundError`, `IndexError`, `RuntimeError` | max 112; >88 13 |
| `pipeline/__init__.py` | no | no | missing | n/a | ok | ok | neither | no raises | max 0; >88 0 |
| `pipeline/cli.py` | yes | yes | reST | 1/1 | ok | ok | logging + print 3 | no raises | max 103; >88 2 |
| `pipeline/processor.py` | no | no | plain | 7/18 | ok | ok | print 10 | raises + asserts 9 | max 167; >88 41 |
| `pipeline/resampler.py` | yes | yes | mixed | 1/1 | ok | ok | neither | raises `ValueError` | max 94; >88 2 |
| `pipeline/run_config.py` | yes | yes | mixed | 7/7 | ok | ok | logging | raises `SystemExit`, `ValueError` | max 108; >88 13 |
| `pipeline/runner.py` | yes | yes | mixed | 4/4 | ok | ok | logging | no raises | max 119; >88 8 |
| `pipeline/sig_processor.py` | no | no | plain | 8/9 | ok | ok | print 5 | raises `FileNotFoundError`, `ValueError` | max 120; >88 13 |
| `run_pipeline.py` | no | yes | reST | n/a | ok | ok | neither | no raises | max 77; >88 0 |
| `tests/__init__.py` | no | no | missing | n/a | ok | ok | neither | no raises | max 0; >88 0 |
| `tests/conftest.py` | no | no | missing | 0/3 | ok | ok | neither | no raises | max 107; >88 5 |
| `tests/test_resampler_parity.py` | yes | yes | plain | 0/1 | ok | ok | neither | asserts 3 | max 89; >88 2 |

Summary: future annotations appear in 6/13 files (46%); module docstrings in 7/13 (54%); all public signatures are typed in 4/9 applicable files (44%); print calls occur in 4/13 files (31%); and 9/13 files (69%) have lines over 88 characters. The newer `cli.py`, `run_config.py`, and `runner.py` establish a clearer style than `sig_processor.py`, `processor.py`, and the demo helper.

## E. Folder Structure And Repo Hygiene

`.gitignore` correctly excludes private and generated data: `naming_ids/`, `data/`, `pipeline_outputs/`, `*.sig`, summary CSVs, and merged CSVs (`.gitignore:19` through `.gitignore:26`). `config/calibrations/.gitkeep` is tracked, preserving that empty directory. However, documentation still links to missing `naming_ids/README.md` (`README.md:20`, `FOLDER_STRUCTURE.md:72`, `pipeline/README.md:56`) while the whole directory is ignored (`.gitignore:19`). A local Markdown link check across 13 Markdown files checked 86 links and found 4 missing, all related to `naming_ids`.

Tracked directory README coverage also contradicts the docs. `README.md` states that every directory has its own README (`README.md:5`), and `FOLDER_STRUCTURE.md` repeats the claim (`FOLDER_STRUCTURE.md:3`), but tracked directories `config/calibrations`, `notebooks`, and `notebooks/pipeline_demo` do not have tracked README files. No packaging or CI files were tracked: no `pyproject.toml`, `setup.py`, `setup.cfg`, `.github/workflows/*`, `.python-version`, or `renv.lock`. A tracked parity report also contains a machine path (`docs/parity_a4any_sb_2025-cn_ch-svc-aviris_bottom_2026-05-27.md:7`).

## F. Terminal Runnability And Reproducibility

CLI guard behavior is strong. `python3 run_pipeline.py` used `config/config.json` and stopped with a clear placeholder message; `python3 run_pipeline.py nope.json` reported tried paths and available configs; `python3 run_pipeline.py config.json --input-dir /private/tmp/... --step 1` exited 0 with a clear "No SIG files found" warning and no outputs. The deprecated `--config` alias is hidden but still supported by `pipeline/cli.py:41` and `pipeline/cli.py:42`.

Reproducibility is weaker. `requirements.txt` is not exact-pinned (`requirements.txt:1` through `requirements.txt:5`), and the repository has no tracked `renv.lock`, despite the methods claim at `docs/supplementary_methods.md:96`. Python 3.9 syntax support appears plausible because all PEP 604 union syntax appears in files with `from __future__ import annotations`, and the compile check passed under Python 3.9 after bytecode cache redirection.

## G. Demo Notebook

The notebook is not currently smooth enough for a reviewer. It defines `DEMO_DATA` under `pipeline_demo/demo_data` (`notebooks/pipeline_demo.ipynb:72`) and `SPECTRA_FOLDER` as `demo_data/spectra` (`notebooks/pipeline_demo.ipynb:74`), then immediately calls `next(SPECTRA_FOLDER.glob("*.sig"))` (`notebooks/pipeline_demo.ipynb:106`) and later `SpectraCollection(SPECTRA_FOLDER)` (`notebooks/pipeline_demo.ipynb:248`). No such `.sig` files are tracked; local files are ignored symlinks into ignored `pipeline_outputs`.

Headless execution failed at the groups cell. The notebook tells users groups are 0-based (`notebooks/pipeline_demo.ipynb:364`), but hard-codes `(4, 5)` (`notebooks/pipeline_demo.ipynb:391`). In the local execution, the collection had only 5 spectra, indices `0-4`, so `average_pairs()` raised `IndexError` from `notebooks/pipeline_demo/svc.py:761`. The `--allow-errors` diagnostic captured two downstream `NameError` cells because `pairs` was never defined.

## H. Testing And Verification

The tracked test suite has one substantive test file: `tests/test_resampler_parity.py`. It tests `resample_spectra` against external R output (`tests/test_resampler_parity.py:78` through `tests/test_resampler_parity.py:133`), but skips when reference inputs are absent (`tests/test_resampler_parity.py:17`, `tests/README.md:10`). Phase 2 `pytest -q` therefore reported `1 skipped`, not a numeric parity pass. `tests/README.md` already acknowledges missing `processor.py` tests (`tests/README.md:37` through `tests/README.md:39`), and the audit found no direct tracked tests for `cli.py`, `run_config.py`, `runner.py`, `sig_processor.py`, `processor.py`, or `notebooks/pipeline_demo/svc.py`.

Minimal high-value tests:

- `RunConfig`: config path resolution, placeholder guard, `sig_input_dirs` expansion, processing default warnings, and calibration priority.
- `Pipeline`: `step` dispatch, missing summary behavior for `--step 2`, no-SIG input behavior, and summary CSV naming.
- `SigFileProcessor`: instrument extraction, mixed-instrument detection, missing instrument behavior, and truncation stop line.
- `processor.py`: sample-name normalization, `GroupSpec.from_csv`, aggregation methods, ungrouped handling, and warning behavior.
- Demo helper: `Spectrum.process()` parity with production helper, `average_pairs()` bounds, and notebook data preflight.
- CI: `python -m py_compile`, `ruff check`, `pytest -q`, and optional parity job gated on externally supplied reference data.

## I. Research Presentability

The repository has a strong manuscript-style algorithm description and two historical parity claims (`README.md:3`, `docs/README.md:21` through `docs/README.md:22`). However, a reviewer cannot reproduce those claims from tracked files alone because the parity test skips without external data, no `.sig` reference data or external data manifest is tracked, and exact dependency snapshots are absent. The methods document also contains a code/prose contradiction on smoothing: it says Pipeline B uses `scipy.cluster.vq.kmeans2` (`docs/supplementary_methods.md:48`), while the code imports and calls `kmeans` (`pipeline/resampler.py:19`, `pipeline/resampler.py:248`). This is either a documentation correction or a parity-sensitive code change; given the hard numerical parity constraint, the shortest safe correction is to revise prose unless a parity rerun is planned.

## Empirical Logs Appendix

All raw logs were captured under `/private/tmp/svc_audit_2026-06-03/logs/`.

| Command / check | Result | Evidence excerpt |
|---|---|---|
| `python3 -m py_compile $(git ls-files '*.py')` | Initial sandbox bytecode-cache failure, rerun passed with `PYTHONPYCACHEPREFIX`. | Initial `PermissionError` in `py_compile.log`; rerun exit 0 in `py_compile_rerun.log`. |
| `python3 -m ruff check .` | Failed with 9 findings. | E402 in `notebooks/pipeline_demo/svc.py:21`, F841 in `pipeline/resampler.py:129`, F401 in `pipeline/sig_processor.py:5`. |
| `pyflakes .` | Literal run traversed `.venv`; tracked-files diagnostic found 6 issues. | `pyflakes_tracked_files.log`. |
| `vulture . --min-confidence 80` | Literal run traversed `.venv`; tracked-files diagnostic found 2 issues. | `vulture_tracked_files.log`. |
| `python3 run_pipeline.py` | Exit 1, friendly placeholder guard. | `config/config.json still contains the placeholder "<PATH_TO_SIG_INPUT_ROOT>"`. |
| `python3 run_pipeline.py nope.json` | Exit 1, friendly missing-config message. | Listed tried paths and available `config.json`. |
| `python3 run_pipeline.py config.json --input-dir <tmp> --step 1` | Exit 0, no outputs. | Warned `No SIG files found` and printed `summary_csv: not produced`. |
| `python3 -m pytest -q` | Suite execution passed by skipping the only test. | `s [100%]`, `1 skipped in 0.44s`. |
| `jupyter nbconvert ...` | CLI subcommand unavailable from current module path; direct `python -m nbconvert` needed local-kernel escalation. | `Jupyter command jupyter-nbconvert not found`; sandbox port-bind `PermissionError`. |
| Notebook execution | Failed at groups cell; diagnostic run captured 3 errors. | `IndexError` for index 5; two `NameError: pairs is not defined` follow-ons. |
| Demo-vs-production numeric comparison | Local ignored data only; close but not identical. | 6 x 2101 cells; max diff `9.6e-7`, mean `3.5e-8`. |
| Production repeatability | Exact on local ignored six-file set. | max diff `0`, mean diff `0`. |

## Prioritized Remediation Roadmap

### Critical

1. **Make the demo notebook runnable from a fresh clone** — parity-safe. Track a minimal sanitized `.sig` demo set or provide a documented download script with checksums; update the grouping cell to match the data.
2. **Make reproducibility claims true** — parity-safe unless changing numerical code. Add exact Python lock/snapshot files, either add `renv.lock` or remove the claim, and document where parity `.sig` / R reference data are obtained.
3. **Add a small non-private test fixture** — parity-safe. It does not need to prove R parity; it should prevent basic CLI, truncation, grouping, and notebook-helper regressions.

### Major

4. **Replace demo imports of private resampler helpers with a public production API** — parity-safe if it only delegates to existing behavior; parity-sensitive if numeric defaults change.
5. **Eliminate mutable class calibration state** — parity-safe if behavior is preserved through instance settings.
6. **Add CI for compile, lint, and tests** — parity-safe. Include optional parity workflow triggered only when reference data secrets/paths are supplied.
7. **Resolve dependency manifest issues** — parity-safe. Add `matplotlib` for the demo or an optional `[demo]` extra; move/remove `specdal` unless historical compatibility requires it.
8. **Correct methods/code contradictions** — parity-sensitive if code changes; parity-safe if docs are corrected to current code behavior.

### Minor / Nit

9. **Standardize style with `ruff` configuration and formatter policy** — parity-safe for non-numeric formatting; use caution in parity-critical files.
10. **Fix broken docs and stale untracked docs** — parity-safe. Add `.gitignore` exception for `naming_ids/README.md` or remove the links; update or archive `refactor.md`; revise `docs/pip_packaging_guide.md` before committing.
11. **Remove machine paths from tracked reports** — parity-safe. Replace with dataset IDs or project-relative placeholders.

## Final Verdict

As-is, the repository is **not yet presentable at a research level** as a software-availability artifact. The production architecture and parity-oriented numerical code are credible, but a reviewer cannot rerun the notebook or parity claim from the tracked repository alone, and several reproducibility statements are materially unsupported by tracked files. The shortest path to "yes" is: ship or externally manifest the demo/parity data, make the notebook pass headlessly, add exact dependency snapshots, add focused non-parity tests and CI, and correct documentation that currently overstates reproducibility or contradicts code. These changes are mostly parity-safe; only changes to `pipeline/resampler.py`, `pipeline/sig_processor.py`, or documented algorithm constants should require a dedicated parity re-run.
