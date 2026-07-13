# `.github/workflows/` — CI & Release Automation

GitHub Actions workflows for this repository.

## [`ci.yml`](ci.yml) — CI
Runs on every pull request, on pushes to `main`, and on manual dispatch
(`workflow_dispatch`). On Python 3.11 it:

1. Installs the package with dev + demo extras (`pip install ".[dev,demo]"`).
2. Byte-compiles all tracked Python files (`py_compile`).
3. Lints with `ruff check`.
4. Runs the test suite with `pytest -q`.
5. Builds the wheel, installs it with demo dependencies into a fresh virtual
   environment, copies the notebook to an empty directory outside the checkout,
   generates test-only `.sig` inputs, and executes the notebook with their path
   supplied through `SVC_DATA_FOLDER`. This verifies that the notebook does not
   succeed accidentally through repository-local imports or private field data.

## [`publish.yml`](publish.yml) — Publish to PyPI
Runs when a version tag matching `v*` (e.g. `v0.1.0`) is pushed, or on manual
dispatch. It builds the sdist + wheel (`python -m build`) and uploads them to
PyPI with `pypa/gh-action-pypi-publish`, authenticating via OIDC **Trusted
Publishing** — no stored token.

**One-time setup before the first release:** on pypi.org, add a Trusted
Publisher for this project (or a "pending publisher" if the project doesn't
exist there yet):

> Owner: `regs08` · Repository: `SVCProcessingPipeline` · Workflow file:
> `publish.yml` · Environment: `pypi`

If you'd rather not rely on Actions, publish manually instead:
`python -m build && python -m twine upload dist/*`.
