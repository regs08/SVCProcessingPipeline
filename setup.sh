#!/usr/bin/env bash
#
# setup.sh — one-command setup for the SVC processing pipeline.
#
# What it does (so you don't have to remember the steps):
#   1. Creates an isolated .venv in this repo (Python 3.11+).
#   2. Installs the pipeline, its science libraries, and Jupyter into it.
#   3. Copies the bundled example dataset into place.
#
# It always operates on THIS repo, no matter which folder you run it from —
# that avoids the "Directory '.' is not installable" and "No module named
# matplotlib" errors that come from being in the wrong directory or environment.
#
# Usage:
#   ./setup.sh          # notebook / demo setup (what most lab users want)
#   ./setup.sh --dev    # the above plus the test & lint tools for development
#
set -euo pipefail

# ── Always work from the repo root (the folder this script lives in) ──────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ── Pick the extras: demo by default, dev+demo with --dev ─────────────────────
EXTRAS="demo"
if [[ "${1:-}" == "--dev" ]]; then
  EXTRAS="dev,demo"
  echo "==> Developer setup: installing [$EXTRAS] extras"
else
  echo "==> Notebook setup: installing [$EXTRAS] extras"
fi

# ── Find a Python 3.11+ interpreter ───────────────────────────────────────────
PYTHON=""
for candidate in python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "ERROR: Python 3.11 or newer is required but was not found." >&2
  echo "       Install it from https://www.python.org/downloads/ and re-run this script." >&2
  exit 1
fi
echo "==> Using $($PYTHON --version) ($(command -v "$PYTHON"))"

# ── 1. Create the virtual environment (skip if it already exists) ─────────────
if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment in .venv"
  "$PYTHON" -m venv .venv
else
  echo "==> Reusing existing .venv"
fi

# Use the venv's own python directly — no 'activate' needed, so this works the
# same whether you run the script or source it.
VENV_PY=".venv/bin/python"

# ── 2. Install everything into the venv ───────────────────────────────────────
echo "==> Upgrading pip"
"$VENV_PY" -m pip install --quiet --upgrade pip

echo "==> Installing the pipeline (editable) with [$EXTRAS] extras"
"$VENV_PY" -m pip install -e ".[$EXTRAS]"

echo "==> Installing JupyterLab"
"$VENV_PY" -m pip install jupyterlab

# ── 3. Stage the bundled example dataset ──────────────────────────────────────
echo "==> Copying the bundled example dataset into place"
"$VENV_PY" scripts/prepare_demo_data.py \
  --source-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom

# ── Done ──────────────────────────────────────────────────────────────────────
cat <<'DONE'

✅ Setup complete.

Next steps:
  1. Activate the environment (do this in each new terminal session):
       source .venv/bin/activate          # macOS / Linux
       # .venv\Scripts\activate           # Windows PowerShell
  2. Launch the notebook:
       jupyter lab
     then open notebooks/pipeline_demo.ipynb

Your prompt showing (.venv) means the environment is active.
DONE
