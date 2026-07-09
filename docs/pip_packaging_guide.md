# Publishing svcProcessingPipeline as a pip Package

**Status (2026-07-09):** Local packaging is **complete and verified**, and the
project now lives at its public GitHub home, https://github.com/regs08/SVCProcessingPipeline.
`[project.urls]` and `publish.yml` have been updated accordingly. What's left
is the PyPI-account-side setup and the actual release — see below.

---

## Where we are

### ✅ Done — local packaging

Everything below is in place and was verified on Python 3.11 in a clean venv.

- **`pyproject.toml` metadata** — name, `version = "0.1.0"`, description, readme,
  `requires-python = ">=3.11"`, runtime deps (`numpy`, `pandas`, `scipy`), the
  `demo`/`dev` extras, and the `svc-pipeline = "pipeline.cli:main"` console
  script. Added: PEP 639 license (`license = "GPL-3.0-only"`, `license-files = ["LICENSE"]`),
  `authors`, `keywords`, `classifiers`, and `[project.urls]`. Build backend pinned
  to `setuptools>=77` (required for the SPDX `license` string; also avoids the
  deprecation warnings the old `license = { text = "..." }` form now triggers).

- **`LICENSE`** — GNU General Public License v3.0. Bundled into the wheel
  automatically via `license-files`.

- **Config-path fix (the critical one for an installed package).** The CLI used
  to locate `config/` from the package's *own* location
  (`Path(__file__).resolve().parent.parent`). That works for an editable install
  but **breaks once pip-installed**: the package lands in `site-packages/`, which
  has no `config/` beside it, so `svc-pipeline config.json` failed with "Config
  not found." The CLI now resolves relative config / calibration / output paths
  against the **current working directory** (`Path.cwd()`); absolute paths are
  honored as-is. An installed user therefore runs `svc-pipeline` from a directory
  that contains their own `config/…`. See `pipeline/cli.py` (`base_dir = Path.cwd()`)
  and `RunConfig` in `pipeline/run_config.py` (`base_dir` parameter).

- **`.gitignore`** — now excludes `build/` and `dist/`.

### ✅ Done — verification

- `python -m build` → clean `svc_processing_pipeline-0.1.0` sdist + `py3-none-any` wheel.
- `pip wheel . --no-deps --no-build-isolation` → **PASSED**; generated wheel
  metadata reports `License-Expression: GPL-3.0-only` and bundles
  `dist-info/licenses/LICENSE`.
- Installed the wheel into a fresh 3.11 venv: `svc-pipeline --help` works, and
  config resolves from the working directory (verified by running from a temp
  dir containing `config/config.json`).
- `pytest` → **34 passed, 1 skipped** (the R-parity test, which skips without
  reference data).
- `ruff check .` → clean.

### ✅ Done — public home

1. **Public home picked and pushed:** https://github.com/regs08/SVCProcessingPipeline
   (`main` and `development` pushed; the old Cornell GHE remote,
   `github.coecis.cornell.edu`, is kept as `origin` for internal work).
2. **`[project.urls]` Repository** updated to the public URL.
3. **`publish.yml` switched to OIDC Trusted Publishing** — no stored
   `PYPI_API_TOKEN` secret needed anymore.

### 🔜 Remaining — to ship

1. **PyPI account with 2FA enabled** (required to upload) — do this yourself if
   not already done.
2. **Add the Trusted Publisher** on [pypi.org](https://pypi.org) (Publishing →
   pending publisher, since the project doesn't exist there yet): Owner
   `regs08` · Repository `SVCProcessingPipeline` · Workflow file `publish.yml` ·
   Environment `pypi`.
3. **Confirm the name `svc-processing-pipeline` is free** on pypi.org (checked
   2026-07-09: free).
4. **TestPyPI dry run** (recommended) — rehearse the upload→install round trip.
5. **Tag and release:** `git tag v0.1.0 && git push public --tags`.

---

## Publish workflow (OIDC — already applied)

`.github/workflows/publish.yml` now uses Trusted Publishing: GitHub proves
this workflow's identity to PyPI via OIDC at upload time, so there's no
`PYPI_API_TOKEN` secret to store or rotate. It fires on `v*` tags or manual
dispatch, builds the sdist/wheel, and uploads with
`pypa/gh-action-pypi-publish`.

**One-time PyPI-side setup (not yet done — do this before the first tag):**
on pypi.org, **Publishing → pending publisher** (the project doesn't exist on
PyPI yet) → add a **Trusted Publisher**:

- Owner: `regs08` · Repository: `SVCProcessingPipeline` · Workflow file:
  `publish.yml` · Environment: `pypi`.

---

## Manual publish (always works, no CI)

To publish by hand — useful for the very first release, or if you'd rather not
rely on Actions:

```bash
python -m build
python -m twine upload dist/*          # prompts for your PyPI token
```

Rehearse on **TestPyPI** first to test the full round trip without touching the
real index:

```bash
python -m twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ svc-processing-pipeline
```

Note: `twine upload` *publishes*; it is not the same as `pip install`. It is the
step that makes `pip install svc-processing-pipeline` work for everyone else.

---

## Releasing future versions

```bash
# 1. Bump the version in pyproject.toml, e.g. 0.1.0 -> 0.2.0
# 2. Commit + tag
git add pyproject.toml
git commit -m "Bump to 0.2.0"
git tag v0.2.0
# 3. Push commit and tag to the public remote — the tag triggers publish.yml
#    (origin is still the internal Cornell GHE mirror; publish.yml only runs
#    on GitHub, so tags must reach the `public` remote)
git push public && git push public --tags
```

Optional: `pip install bump2version`, then `bump2version patch|minor|major`
edits `pyproject.toml` and creates the matching tag automatically.

---

## Quick reference — local build & test loop

```bash
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev,demo]"      # editable dev install
python -m build                             # produce dist/*.whl + *.tar.gz
python -m twine check dist/*                # validate package metadata

# Faithful "as if installed from PyPI" test, in a throwaway venv:
python3.11 -m venv /tmp/pkgtest
/tmp/pkgtest/bin/pip install dist/svc_processing_pipeline-0.1.0-py3-none-any.whl
/tmp/pkgtest/bin/svc-pipeline --help
```

Installing the locally built wheel is mechanically identical to
`pip install svc-processing-pipeline` once published — same artifact, only the
source differs (local file vs the PyPI index).
