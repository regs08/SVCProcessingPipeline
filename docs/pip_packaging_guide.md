# Publishing svcProcessingPipeline as a pip Package

## Prerequisites
- GitHub repo connected to this project
- Python 3.9+
- Account on [pypi.org](https://pypi.org)

---

## Phase 1: Set Up the Package Locally

### Step 1 — Confirm `pyproject.toml` in the project root

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "svc-processing-pipeline"
version = "0.1.0"
description = "SVC hyperspectral processing pipeline"
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "numpy",
    "pandas",
    "scipy",
]

[project.scripts]
svc-pipeline = "pipeline.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["pipeline*"]
```

### Step 2 — Keep concrete-module imports

`pipeline/__init__.py` is intentionally empty. Public API users should import
from concrete modules:

```python
from pipeline.resampler import process_sig_file, resample_spectra
from pipeline.sig_processor import SigFileProcessor
from pipeline.processor import GroupSpec, SVCDataProcessor, SigSpectraAverager
```

### Step 3 — Test the local install

```bash
pip install -e ".[dev,demo]"
python -c "import pipeline; print('ok')"
svc-pipeline --help
```

The `-e` flag is an editable install — code changes reflect immediately without reinstalling.

### Step 4 — Verify the build

```bash
pip install build
python -m build
```

This produces `dist/svc_processing_pipeline-0.1.0.tar.gz` and a `.whl` file. If it runs without errors the package is well-formed.

---

## Phase 2: Register on PyPI

### Step 5 — Create a PyPI account

Go to [pypi.org](https://pypi.org) → Register.

Enable 2FA (required for publishing).

### Step 6 — Generate a PyPI API token

1. Log in → Account Settings → API Tokens → Add API Token
2. Scope: **Entire account** for the first publish; switch to project-scoped after the first upload
3. Copy the token — it starts with `pypi-` and is only shown once

### Step 7 — Add the token as a GitHub secret

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `PYPI_API_TOKEN`
4. Value: paste the token

---

## Phase 3: Set Up GitHub Actions Auto-Publish

### Step 8 — Create the workflow file

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"      # runs on tags like v0.1.0, v1.2.3

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build package
        run: |
          pip install build
          python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

### Step 9 — Commit the workflow

```bash
git add .github/workflows/publish.yml pyproject.toml
git commit -m "Add pip packaging and PyPI publish workflow"
git push
```

---

## Phase 4: Cut the First Release

### Step 10 — Tag and push

```bash
git tag v0.1.0
git push --tags
```

This triggers the GitHub Action. Check the **Actions** tab on GitHub to watch the run. If it passes, the package will be live at:

```
https://pypi.org/project/svc-processing-pipeline/
```

Users can then install it with:

```bash
pip install svc-processing-pipeline
```

---

## Releasing Future Versions

Every new release is a three-step process:

```bash
# 1. Bump the version in pyproject.toml
#    e.g., version = "0.2.0"

# 2. Commit and tag
git add pyproject.toml
git commit -m "Bump to 0.2.0"
git tag v0.2.0

# 3. Push both the commit and the tag
git push && git push --tags
```

The GitHub Action runs automatically and publishes the new version to PyPI.

---

## Add an MIT License

Before publishing to PyPI, add a `LICENSE` file to the project root. Without one, the code is technically "all rights reserved" and users cannot legally install or use it.

Create `LICENSE` in the project root with the following content (replace the year and name):

```
MIT License

Copyright (c) 2026 Cole Regnier

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Then add the license field to `pyproject.toml` under `[project]`:

```toml
license = { text = "MIT" }
```

Commit it alongside the other packaging files in Step 9.

---

## Optional: Automate Version Bumping

To avoid manually editing `pyproject.toml` each time, install `bump2version`:

```bash
pip install bump2version
```

Then run one of:

```bash
bump2version patch   # 0.1.0 → 0.1.1
bump2version minor   # 0.1.0 → 0.2.0
bump2version major   # 0.1.0 → 1.0.0
```

This edits `pyproject.toml` and creates the git tag automatically.
