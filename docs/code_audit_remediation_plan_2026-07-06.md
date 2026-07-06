# Code Audit Remediation Plan — 2026-07-06

Follow-up to the architecture/code-quality audit run from
[`code_audit_prompt.md`](code_audit_prompt.md). Items below are marked
**Implemented** (done and verified in this session) or **Deferred** (not
scheduled — a judgment call, not something awaiting a diff). All eight
actionable items from the original audit have been implemented; nothing is
left pending.

Full test suite after all implemented items: **34 passed, 1 skipped**
(the R-parity test skips without reference data, as usual). `ruff check
pipeline/ tests/` and `pyflakes pipeline/` — all checks passed after every
item below.

---

## Implemented

### 1. Reuse `group_by()`'s result in `SigSpectraAverager.aggregate(method=None)`

**Why it mattered**: grouping and aggregation were already separate steps
(`group_by()` computes `self.grouped_entries`; `average_groups()` reduces
each group to one row) — this was not a missing architectural decoupling.
The bug was narrower: the `method=None` "raw rows, no aggregation" branch of
`aggregate()` didn't trust the grouping `group_by()` had just computed. It
re-derived row membership itself by rescanning `self.processor.entries`
against the requested member tuple. Both computations selected the same
entries, but not necessarily in the same order — `grouped_entries` orders
rows by the sequence group members were requested in (e.g. `members=(5, 3)`
puts scan 5 before scan 3), while the manual rescan used original file
order. That meant `aggregate(method="mean")` and `aggregate(method=None)`
could silently disagree on row order for the identical group definition.

**What changed**: [`pipeline/processor.py`](../pipeline/processor.py) —
`SigSpectraAverager.aggregate()`'s `method is None` branch now iterates
`zip(normalized_groups, self.processor.grouped_entries)` and pulls
`entry.index` directly from the group, instead of rescanning
`self.processor.entries`.

**Verification**: added
`test_sig_spectra_averager_raw_rows_follow_requested_member_order` to
[`tests/test_processor.py`](../tests/test_processor.py), which requests
group members in reverse order `(2, 1)` and asserts the raw output follows
that order — this test fails under the old rescan logic and passes under
the fix. Full suite green.

### 2. Remove the redundant/imprecise `_SIGMA_NM` constant in `resampler.py`

**Why it mattered**: the FWHM→sigma conversion was computed four times in
the file — an approximate module constant (`_SIGMA_NM = _FWHM_NM / 2.355`)
and three precise computations (`_sigma_from_fwhm()` plus two inline uses in
`_smooth_fwhm()`). `_SIGMA_NM` was dead in production: it was only
`_gaussian_resample`'s default `sigma` argument, and the sole call site
(`process_sig_file`) always passed `sigma=_sigma_from_fwhm(fwhm_nm)`
explicitly, overriding the default.

**What changed**: [`pipeline/resampler.py`](../pipeline/resampler.py) —
deleted the `_SIGMA_NM` module constant; `_gaussian_resample`'s `sigma`
parameter is now required (no default), since every call site already
passes it explicitly.

**Numerics**: unchanged. No production call site relied on the deleted
default, so this required no parity re-test — flagged here explicitly
given `resampler.py`'s parity-critical status.

**Verification**: full suite green (parity test skips without reference
data, unaffected either way).

### 3. Stop globally monkey-patching `warnings.formatwarning`

**Why it mattered**: `SVCDataProcessor.group_by()` unconditionally
overwrote `warnings.formatwarning` — a process-wide global — just to
shorten the printed warning text. That affected every other warning raised
anywhere else in the same Python process (other libraries, notebooks), not
just this pipeline's own warnings.

**What changed**: [`pipeline/processor.py`](../pipeline/processor.py) —
removed the `warnings.formatwarning = _simple_warn_format` assignment (and
the now-unused local function) from `group_by()`. Existing
`pytest.warns(UserWarning, match=...)` assertions check the warning
*message*, not the display formatting, so they were unaffected.

**Verification**: full suite green.

### 4. Route `SigFileProcessor`'s logging and error handling through a logger

**Why it mattered**: `process_sig_files()` swallowed per-file errors with a
bare `except Exception as e: print(...)` and used raw `print()` for all
verbose output, instead of the `logging` module the rest of the pipeline
(`cli.py`, `run_config.py`, `runner.py`) standardizes on.

**Design note**: the demo notebook
([`notebooks/pipeline_demo/svc.py:163`](../notebooks/pipeline_demo/svc.py))
calls `SigFileProcessor(...).process_sig_files(..., verbose=verbose)`
directly, without configuring Python logging — so a straight swap to
`logging` would have silently dropped INFO-level verbose output in the demo
notebook (Python's logging drops INFO records when nothing has configured
a handler). To avoid that regression, the fix is dual-mode: if a logger is
supplied, use it; otherwise, fall back to the exact previous `print()`
behavior.

**What changed**:
- [`pipeline/sig_processor.py`](../pipeline/sig_processor.py) —
  `SigFileProcessor.__init__` accepts an optional `logger:
  Optional[logging.Logger] = None`; added `_log_info`/`_log_error` helpers
  that route through the logger when present, else `print()` (unchanged
  behavior for existing callers, including the demo notebook and tests).
  `process_sig_files()`'s verbose messages and the previously-swallowed
  per-file exception now go through `_log_info`/`_log_error`.
- [`pipeline/runner.py`](../pipeline/runner.py) — both `SigFileProcessor(...)`
  construction sites (`inspection_processor`, `processor`) now pass
  `logger=logger`, so the orchestrated CLI path logs consistently with the
  rest of a run.

**Verification**: full suite green; manual smoke run —
`python -m pipeline.cli config.json --input-dir <fixture dir> --step 1
--verbose` — confirmed `INFO:`-formatted messages route through the
configured root logger end-to-end with no behavior change to the produced
summary CSV.

### 5. Add `tests/test_cli.py` smoke coverage

**Why it mattered**: `pipeline/cli.py` is the actual `svc-pipeline` entry
point users run, but had no dedicated test.

**What changed**: new file
[`tests/test_cli.py`](../tests/test_cli.py) — pure addition, no production
code changes. Covers: `_parse_args()` defaults and flag parsing (`--step`,
`--input-dir`, `--verbose`); `main()` end-to-end with `--input-dir`
overriding an unedited placeholder config and processing only that
directory; `main()` exiting via the placeholder guard when no
`--input-dir` override is given.

**Verification**: full suite green (33 passed, up from 29).

### 6. Decouple `SigFileProcessor` calibration tables from global class state

**Why it mattered**: `SigFileProcessor.DEFAULT_CORRECTION_TYPES` /
`DEFAULT_INSTRUMENT_NUMBERS` were class attributes monkey-patched at runtime
by `RunConfig.apply_sensor_calibrations()` and by the
`load_default_correction_types()` classmethod. This already caused friction:
`tests/test_run_config.py`'s calibration test had to manually save/restore
both class attributes in a `try`/`finally` to avoid leaking state into
other tests. In a multi-directory run (`process_all_subdirs`), these
globals were reset and rewritten once per input directory, so correctness
depended on strict sequential ordering.

**What changed**:
- [`pipeline/sig_processor.py`](../pipeline/sig_processor.py) —
  `SigFileProcessor.__init__` now accepts optional `correction_types` /
  `instrument_numbers` dicts, stored as instance attributes
  (`self._correction_types`/`self._instrument_numbers`), defaulting to the
  class-wide `DEFAULT_CORRECTION_TYPES`/`DEFAULT_INSTRUMENT_NUMBERS` when
  not supplied (unchanged behavior for any caller that doesn't pass them —
  the demo notebook, existing tests). `get_supported_correction_types()`
  and `_extract_instrument_name()` now read the instance attributes instead
  of the class attributes directly. Added a pure
  `parse_correction_types_file()` static method (parses a calibration JSON
  into a dict, no mutation); `load_default_correction_types()` now
  delegates to it but keeps its original mutating contract for direct,
  explicit callers.
- [`pipeline/run_config.py`](../pipeline/run_config.py) — replaced
  `apply_sensor_calibrations()` (mutated the class) with a private, pure
  `_resolve_calibrations(input_dir)` (plus helper
  `_instrument_block_calibrations()`) that returns
  `(correction_types, instrument_numbers)` as plain dicts, preserving the
  exact same priority order and merge/replace semantics as before (inline
  `instrument` block merges over built-in defaults; `sensor_calibration_file`
  / auto-inferred file fully replaces the correction-types table, matching
  the original classmethod's behavior). `PipelineSettings` gained
  `correction_types`/`instrument_numbers` fields, populated by
  `settings_for()`.
- [`pipeline/runner.py`](../pipeline/runner.py) — both `SigFileProcessor(...)`
  construction sites pass `correction_types=settings.correction_types`,
  `instrument_numbers=settings.instrument_numbers` (the truncation-only
  `processor` instance doesn't need them and doesn't receive them); the
  end-line lookup reads `settings.correction_types` instead of
  `SigFileProcessor.DEFAULT_CORRECTION_TYPES`.
- [`pipeline/cli.py`](../pipeline/cli.py) — dropped the now-removed
  `run_config.apply_sensor_calibrations(input_dir)` call; `settings_for()`
  resolves calibration internally.
- [`tests/test_run_config.py`](../tests/test_run_config.py) — calibration
  test now calls `_resolve_calibrations()` directly and asserts on the
  returned dicts; the `try`/`finally` save-restore is gone entirely, and
  `test_settings_for_resolves_output_paths` gained assertions on the new
  `PipelineSettings` fields.
- [`tests/test_runner.py`](../tests/test_runner.py) — `_settings()` helper
  updated with the two new required `PipelineSettings` fields.
- [`pipeline/README.md`](../pipeline/README.md) — doc sync: `RunConfig`,
  `SigFileProcessor.__init__`, and the constructor-injectable calibration
  tables are now described; also fixed a stale reference to the already-removed
  `_SIGMA_NM` constant (item 2) that hadn't been synced yet.

**Verification**: full suite green (33 passed). Manual smoke test: ran
`svc-pipeline` against a temp copy of `tests/fixtures/sig_inputs/bronze_a.sig`
+ `bronze_b.sig` with an inline `instrument.bronze.end_line` override
different from the built-in default — confirmed (a) the truncation actually
used the overridden end-line, not the built-in one, and (b)
`SigFileProcessor.DEFAULT_CORRECTION_TYPES` was completely unchanged
before and after the run, proving the class-level global is no longer
touched.

### 7. Standardize path handling and typing style

**Why it mattered**: `sig_processor.py` and `processor.py` used
`os.path`/`abspath`/`expanduser` and old-style
`typing.Optional/Dict/Union/List/Sequence`; `cli.py`, `run_config.py`,
`runner.py`, and `resampler.py` already used `pathlib.Path` and
`from __future__ import annotations` + builtin generics. Purely a
consistency issue, not a bug — but four sub-decisions had real, visible
consequences, so they were confirmed explicitly before implementing:

1. **Path resolution**: `os.path.abspath()` does not resolve symlinks;
   pathlib's idiomatic `.resolve()` does. Chose **`.resolve()`**, matching
   the convention already used in `runner.py`/`cli.py`. Visible effect:
   printed/logged paths from `SigFileProcessor` are now canonical — e.g. on
   this Mac, `/tmp/foo` becomes `/private/tmp/foo` in messages (confirmed in
   the manual smoke test below). No change to which files are read/written.
2. **Public signatures**: chose to **leave them as `str`-only** (no widening
   to `str | Path`) — minimal footprint, every existing caller already
   passes `str`.
3. **`Dict[str, any]` typo**: `check_instrument_consistency`'s return type
   hint used the lowercase `any` (the builtin function) instead of
   `typing.Any` — a pre-existing type-hint mistake, harmless at runtime.
   Chose to **fix it** to `dict[str, Any]` since it was directly adjacent to
   the line already being modernized.
4. **`Iterable`/`Sequence` source**: `processor.py` imported these from
   `typing` (deprecated aliases since Python 3.9). Chose to **move to
   `collections.abc`** — these are also used in real `isinstance()` checks
   (not just annotations) in `processor.py`, and `collections.abc.Iterable`/
   `Sequence` are literally what the `typing` aliases wrap, so this is
   behavior-identical and more correct.

**What changed**:
- [`pipeline/sig_processor.py`](../pipeline/sig_processor.py) — full
  rewrite of path handling: `process_sig_files()`/`_process_single_file()`
  now operate on `Path` objects internally (`Path.iterdir()`, `Path.mkdir()`,
  `Path.open()`) instead of `os.listdir`/`os.path.join`/bare `open()`;
  `extract_instrument_from_file()`, `get_file_metadata()`,
  `check_instrument_consistency()` use `Path(...).expanduser().resolve()`
  instead of `abspath(expanduser(...))`. Typing modernized throughout:
  `from __future__ import annotations` added, `Union`/`Optional`/`Dict`
  replaced with `X | Y` / `dict[...]`; only `Any` remains imported from
  `typing`. `__init__`'s untyped `str = None` parameters (`correction_value`,
  `instrument_number`, `correction_type`, `correction_config`) were also
  corrected to `str | None = None` while touching those exact lines.
- [`pipeline/processor.py`](../pipeline/processor.py) — typing-only
  changes: `Iterable`/`Sequence` now imported from `collections.abc`;
  `List`/`Optional`/`Union` replaced with builtin generics / `X | None`
  throughout (including the `isinstance(x, Iterable)` runtime checks, which
  still work identically since `collections.abc.Iterable` is the real class
  `typing.Iterable` aliased to). `Literal` stays imported from `typing` (no
  builtin replacement exists). No path-handling changes needed here — this
  file was already pandas/pathlib-based.
- [`tests/test_sig_processor.py`](../tests/test_sig_processor.py) — updated
  `test_process_single_file_truncates_at_end_line` to pass `Path` objects
  to `_process_single_file()` instead of `str`, matching its new (private,
  internal-only) contract.

**Verification**: full suite green (33 passed, 1 skipped); `ruff check` and
`pyflakes` clean on `pipeline/`. Manual smoke tests: (a) ran
`check_instrument_consistency()`/`get_file_metadata()` directly against a
mixed bronze/silver fixture folder under `/tmp` — correctly detected mixed
instruments and parsed headers, and the resolved paths showed
`/private/tmp/...` as expected; (b) ran the full `svc-pipeline` CLI
end-to-end against bronze fixtures — truncation output unchanged, calibration
resolution unaffected; (c) confirmed `notebooks/pipeline_demo/svc.py` and all
public `pipeline.*` imports still succeed.

### 8. Resolve the three orphaned public getters in `sig_processor.py`

**Why it mattered**: `get_supported_correction_types`,
`get_correction_end_line`, `get_correction_config` had no callers anywhere
in the repo (code, tests, or notebooks) and weren't documented in
`pipeline/README.md`. On closer look the three weren't equally redundant:
`get_correction_end_line()` and `get_correction_config()` just re-expose
attributes that are already plain public instance attributes
(`.end_line_value`, `.correction_type`, `.instrument_number`) — pure
boilerplate. `get_supported_correction_types()` is different: it returns
`list(self._correction_types.keys())`, and `_correction_types` is the
underscore-prefixed instance attribute introduced by item 6's calibration
refactor — the only sanctioned way to see which correction types an
instance knows about without reaching into "private" state.

**What changed**:
- [`pipeline/sig_processor.py`](../pipeline/sig_processor.py) — deleted
  `get_correction_end_line()` and `get_correction_config()`; kept
  `get_supported_correction_types()` with a docstring.
- [`pipeline/README.md`](../pipeline/README.md) — documented
  `get_supported_correction_types()`, with a note that the underlying
  values are plain public attributes to be read directly.
- [`tests/test_sig_processor.py`](../tests/test_sig_processor.py) — added
  `test_get_supported_correction_types_reflects_injected_table()`, covering
  both the class-default case and an injected `correction_types=` table
  (the scenario item 6 made possible).

**Note on scope**: confirmed via repo-wide grep that nothing in this
codebase (code, tests, notebooks) called the two deleted methods. `pyproject.toml`
is at `version = "0.1.0"` (pre-1.0, no back-compat guarantee expected). This
can't rule out private/external scripts outside this repo calling them.

**Verification**: full suite green (34 passed, 1 skipped, up from 33);
`ruff check` clean.

---

## Deferred — not scheduled

### 9. SRP: consider splitting `SVCDataProcessor`

`SVCDataProcessor` bundles ~20 methods across IO, name parsing, grouping,
aggregation, ungrouped-row handling, concatenation, debug printing, and CSV
saving into one class. It's a notebook-facing fluent builder, not on the
production CLI path — "nice to have," not urgent. The audit's own bar is
"citable, readable, deployable," not textbook-clean, and this file already
clears that bar. Revisit only if `processor.py` keeps growing or becomes
hard to navigate in practice.
