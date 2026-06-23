# Publishing svcProcessingPipeline as a pip Package

**Status (2026-06-04):** Local packaging is **complete and verified**. The only
remaining work is the publish setup, intentionally deferred until the project
moves to its public GitHub home — that's the final "ship it" step.

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
- `pytest` → **28 passed, 1 skipped** (the R-parity test, which skips without
  reference data).
- `ruff check .` → clean.

### 🔜 Remaining — to ship (do these together, last)

1. **Pick the public home.** Plan: a public **github.com** repo. (The current
   remote is Cornell GHE Server, `github.coecis.cornell.edu`, which cannot use
   PyPI's OIDC Trusted Publishing — that only trusts github.com.)
2. **Update `[project.urls]` Repository** from the GHE URL to the public
   `https://github.com/<user>/<repo>`.
3. **Switch `publish.yml` to OIDC Trusted Publishing** (see below) — removes the
   API-token secret entirely.
4. **Confirm the name `svc-processing-pipeline` is free** on [pypi.org](https://pypi.org).
5. **TestPyPI dry run** (recommended) — rehearse the upload→install round trip.
6. **Tag and release:** `git tag v0.1.0 && git push --tags`.

Prerequisite for any publish path: a **PyPI account with 2FA enabled** (required
to upload).

---

## Target publish workflow (OIDC — for the public github.com repo)

Trusted Publishing lets GitHub Actions authenticate to PyPI with **no stored
token**. The repo currently ships a *token-based* `publish.yml` because Cornell
GHE Server can't do OIDC. Once the project lives on public github.com, replace it
with this:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"          # fires on version tags like v0.1.0
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi          # optional; lets you add release-approval rules
    permissions:
      id-token: write          # REQUIRED for trusted publishing — no token needed
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build sdist and wheel
        run: |
          python -m pip install --upgrade build
          python -m build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # no `password:` — identity is proven via OIDC
```

**One-time PyPI setup** (do this before the first tag): pypi.org → your project,
or **Publishing → pending publisher** if the project doesn't exist yet → add a
**Trusted Publisher**:

- Owner: `<user>` · Repository: `<repo>` · Workflow file: `publish.yml` ·
  Environment: `pypi` (only if you kept the `environment:` line).

The change from the token version currently in the repo is exactly: drop
`with: password: ${{ secrets.PYPI_API_TOKEN }}`, add `permissions: id-token: write`.
No `PYPI_API_TOKEN` secret needed.

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
# 3. Push commit and tag — the tag triggers publish.yml
git push && git push --tags
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
