# Code Audit Execution Plan

Date: 2026-06-03

## Summary

- Deliver two Markdown artifacts: this plan (`docs/code_audit_plan_2026-06-03.md`) first, then `docs/code_audit_2026-06-03.md`.
- Do not modify source code. Writes are limited to the plan/report files and temporary execution outputs under `/private/tmp` or ignored runtime outputs produced by required commands.
- After each numbered phase, pause, summarize evidence collected, note blockers, and wait for explicit user confirmation before continuing.
- Treat `pipeline/resampler.py` and `pipeline/sig_processor.py` as parity-critical. Any recommendation touching numeric behavior will be tagged parity-sensitive and require `tests/test_resampler_parity.py`.

## Execution Phases

1. **Save plan and baseline state**
   - Write this plan to `docs/code_audit_plan_2026-06-03.md`.
   - Record `git status --short`, tracked Python file list, tracked docs, ignored/untracked artifacts, and current Python/tool versions.
   - Pause with summary.

2. **Empirical verification**
   - Use an isolated temp audit environment if needed; install only missing audit tools (`vulture`, `pyflakes`, `nbconvert`) and record versions.
   - Run and capture logs:
     - `python3 -m py_compile $(git ls-files '*.py')`
     - `ruff check .`
     - `pyflakes .`
     - `vulture . --min-confidence 80`
     - `python3 run_pipeline.py`
     - `python3 run_pipeline.py nope.json`
     - `python3 run_pipeline.py config.json --input-dir <tmp-empty-dir> --step 1`
     - `python3 -m pytest -q`
     - `jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 notebooks/pipeline_demo.ipynb --output /tmp/demo_run.ipynb`
   - If notebook execution stops early, rerun with `--allow-errors` to enumerate all cell errors/warnings, clearly labeling it diagnostic.
   - Pause with pass/fail summary and key stderr/stdout excerpts.

3. **Architecture, OO, and algorithm audit**
   - Build an AST-based dependency graph for all 13 tracked `.py` files; flag cycles, private/internal imports, and layer violations.
   - Compare `notebooks/pipeline_demo/svc.py` against production: verify it imports `pipeline.resampler` internals rather than reimplementing trim/splice/smooth/resample, and test numeric consistency on tracked demo data if present; otherwise use the local ignored processed `.sig` fallback and label it non-fresh-clone evidence.
   - Evaluate cohesion, mutable class state, public/private API boundaries, dataclasses, and type-hint completeness.
   - Pause with architecture findings draft.

4. **Static quality, dependencies, and convention matrix**
   - Produce the required per-file conformance matrix for all tracked `.py` files: future annotations, module docstring, docstring style, public signature typing, import grouping, naming, logging/print, error handling, and line-length/formatting.
   - Audit declared vs imported dependencies using `requirements.txt`, AST imports, `rg`, and tool output; specifically verify `specdal` usage claims.
   - Quantify counts and percentages for style deviations, unused code reports, undeclared imports, and unused declared dependencies.
   - Pause with matrix/dependency summary.

5. **Repo hygiene, docs, reproducibility, and tests**
   - Verify README/file-list reality, local Markdown links, missing documented directories, `.gitignore`, `config/calibrations/.gitkeep`, untracked docs, private/machine paths, packaging files, CI absence/presence, and Python-version claims.
   - Map test coverage by production module and identify minimal high-value additions.
   - Assess research presentability and parity reproducibility from a fresh clone.
   - Pause with docs/reproducibility/test summary.

6. **Write final audit report**
   - Create `docs/code_audit_2026-06-03.md` with executive summary, A-I scorecard, cited findings table, per-dimension narratives, dependency graph, conformance matrix, empirical logs appendix, prioritized roadmap, and final verdict.
   - Every finding will cite `path:line`, include severity, separate defect vs subjective preference, and tag recommendations as parity-safe or parity-sensitive.
   - Pause with final artifact path and a concise verdict.

## Public Interfaces / API Changes

- No source, public API, schema, or numeric behavior changes will be made during the audit.
- The report may recommend future API changes, likely a public production helper to replace demo imports of private `pipeline.resampler` internals, but that remains advisory.

## Test And Evidence Standards

- Claims that commands, tests, CLI, or notebook cells pass/fail must be backed by captured execution logs.
- Fresh-clone runnability is judged only from tracked files; local ignored `.sig` data may be used only as explicitly labeled supplemental evidence.
- Numeric consistency checks involving the demo path must report max/mean absolute difference when data are available.

## Assumptions

- Use date `2026-06-03` from the provided environment context.
- Plan file path defaults to `docs/code_audit_plan_2026-06-03.md`.
- Final audit file path is `docs/code_audit_2026-06-03.md`.
- Missing audit tools may be installed into a temporary environment if unavailable; if network approval is required, request it at that phase.

## Phase 1 Baseline State

### Git status

```text
 M docs/supplementary_methods.md
?? docs/pip_packaging_guide.md
?? refactor.md
```

### Tracked Python files

```text
notebooks/pipeline_demo/__init__.py
notebooks/pipeline_demo/svc.py
pipeline/__init__.py
pipeline/cli.py
pipeline/processor.py
pipeline/resampler.py
pipeline/run_config.py
pipeline/runner.py
pipeline/sig_processor.py
run_pipeline.py
tests/__init__.py
tests/conftest.py
tests/test_resampler_parity.py
```

Count: 13 tracked `.py` files.

### Tracked Markdown/docs files

```text
FOLDER_STRUCTURE.md
README.md
archived_r_scripts/README.md
config/README.md
docs/README.md
docs/parity_a4any_sb_2025-cn_ch-svc-aviris_bottom_2026-05-27.md
docs/parity_retest_prompt.md
docs/supplementary_methods.md
pipeline/README.md
tests/README.md
```

### Untracked and ignored artifacts

`git status --short --ignored` reported:

```text
 M docs/supplementary_methods.md
?? docs/pip_packaging_guide.md
?? refactor.md
!! .DS_Store
!! .claude/
!! .pytest_cache/
!! .venv/
!! __pycache__/
!! data/
!! notebooks/pipeline_demo/demo_data/
!! pipeline/__pycache__/
!! pipeline_outputs/
```

### Current Python and audit-tool availability

```text
python3 --version: Python 3.9.6
python3 -m ruff --version: ruff 0.15.0
python3 -m pytest --version: pytest 8.4.1
python3 -m jupyter --version:
  IPython          : 8.18.1
  ipykernel        : 6.30.1
  ipywidgets       : not installed
  jupyter_client   : 8.6.3
  jupyter_core     : 5.8.1
  jupyter_server   : not installed
  jupyterlab       : not installed
  nbclient         : not installed
  nbconvert        : not installed
  nbformat         : not installed
  notebook         : not installed
  qtconsole        : not installed
  traitlets        : 5.14.3
python3 -m nbconvert --version: unavailable (No module named nbconvert)
python3 -m vulture --version: unavailable (No module named vulture)
python3 -m pyflakes --version: unavailable (No module named pyflakes)
```

Phase 1 status: completed. Phase 2 will require installing or otherwise providing `vulture`, `pyflakes`, and notebook execution packages (`nbconvert`, `nbclient`, `nbformat`) before all required empirical commands can run.
