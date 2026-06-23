# Folder Structure

Authoritative map of the repository. Every directory has its own `README.md` describing its contents in depth — open the one closest to the code you are touching.

## Tree

```
svcProcessingPipeline/
├── README.md                       # Project entry point (start here)
├── FOLDER_STRUCTURE.md             # This file
├── LICENSE                         # GNU General Public License v3.0
├── ACKNOWLEDGMENTS.md              # Attribution, third-party licenses, citation
├── pyproject.toml                  # Package metadata, svc-pipeline console script, ruff config
├── .gitignore                      # Excludes data/, pipeline_outputs/, *.sig, naming_ids/, …
├── .github/workflows/              # CI + release automation — see .github/workflows/README.md
│   ├── README.md
│   ├── ci.yml                      # Compile + ruff + pytest on Python 3.11
│   └── publish.yml                 # Build + publish to PyPI on version tags
├── scripts/
│   └── prepare_demo_data.py        # Copy/download and verify external demo .sig files
│
├── pipeline/                       # Core Python package — see pipeline/README.md
│   ├── README.md
│   ├── __init__.py                 # (empty marker)
│   ├── cli.py                      # CLI glue: parse args, wire RunConfig → Pipeline
│   ├── run_config.py               # RunConfig — load run config + build PipelineSettings
│   ├── runner.py                   # Pipeline — run the processing + resampling stages
│   ├── sig_processor.py            # SigFileProcessor — truncate & inspect .sig files
│   ├── resampler.py                # resample_spectra() — pure-Python R replacement
│   └── processor.py                # SVCDataProcessor / SigSpectraAverager / GroupSpec
│
├── tests/                          # Pytest suite — see tests/README.md
│   ├── README.md
│   ├── __init__.py
│   ├── conftest.py                 # --r-reference-csv / --r-input-dir options + fixtures
│   ├── fixtures/sig_inputs/        # Compact synthetic .sig fixtures, not field data
│   ├── test_resampler_parity.py    # R-vs-Python numerical parity test (1e-3 tolerance)
│   └── test_*.py                   # Focused unit tests for config, runner, helpers, grouping
│
├── config/                         # Run + calibration configs — see config/README.md
│   ├── README.md
│   ├── config.json                 # Run-config template (instrument + processing + paths)
│   └── calibrations/               # Optional per-run sensor calibration JSONs (auto-inferred)
│       └── README.md
│
├── docs/                           # Manuscript-grade docs — see docs/README.md
│   ├── README.md
│   ├── pip_packaging_guide.md
│   ├── processing_config_reference.md  # Knob-by-knob config companion to supplementary_methods
│   ├── supplementary_methods.md    # Canonical algorithm spec (cite this)
│   └── parity_retest_prompt.md     # LLM prompt for re-running parity on new data
│
├── archived_r_scripts/             # Frozen R reference — see archived_r_scripts/README.md
│   ├── README.md
│   └── merge_resample_sig.R        # Pipeline A (spectrolab) — used to regenerate parity CSV
│
├── notebooks/                      # Demo/analysis notebooks (not on the production path)
│   ├── README.md
│   ├── pipeline_demo.ipynb                     # tracked — end-to-end pipeline demo
│   ├── pipeline_demo/                          # helper package for the demo notebook
│   │   ├── __init__.py
│   │   ├── README.md
│   │   ├── demo_data_manifest.json             # external raw-data manifest
│   │   ├── demo_data/                          # tracked README, ignored raw .sig target
│   │   └── svc.py
│   ├── weekly_sig_spectra_visualization.ipynb # gitignored
│   └── spectral_change_analysis.ipynb         # gitignored
│
├── naming_ids/                     # Sample-grouping lookup CSVs — see naming_ids/README.md
│   ├── README.md                   # tracked schema documentation
│   └── *.csv                       # gitignored per-date scan-id → group-name tables (private)
│
└── pipeline_outputs/               # Generated at runtime (gitignored)
    ├── sig_processed/<run>/        # Truncated .sig files + *_processed_sig_summary.csv
    └── sig_resampled/<run>/        # Merged CSV from resample_spectra()
```

## Reading order for a new contributor / LLM

1. **[README.md](README.md)** — project goals, install, and the one-command run.
2. **[pipeline/README.md](pipeline/README.md)** — module-by-module API reference for the production code.
3. **[docs/supplementary_methods.md](docs/supplementary_methods.md)** — the algorithm in formal scientific prose (the source of truth for *what* the code does).
4. **[config/README.md](config/README.md)** — how runs are parameterized.
5. **[tests/README.md](tests/README.md)** — how correctness is verified.
6. **[archived_r_scripts/README.md](archived_r_scripts/README.md)** — the R reference, kept for parity verification only.
7. **[docs/README.md](docs/README.md)** + parity reports — historical evidence and the LLM-driven re-test workflow.
8. **[notebooks/pipeline_demo.ipynb](notebooks/pipeline_demo.ipynb)** and **[naming_ids/README.md](naming_ids/README.md)** — analysis-side conveniences; not on the production hot path.

## Gitignored paths (do not commit)

- `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`
- `.env`, `.env.*`
- `pipeline_outputs/`, `sig_processed/`, `sig_resampled/`, `data/`
- `*.sig`, except synthetic fixtures under `tests/fixtures/`
- `*processed_sig_summary.csv`, `*merged_spectra.csv`
- `naming_ids/*.csv`
- `notebooks/spectral_change_analysis.ipynb`, `notebooks/weekly_sig_spectra_visualization.ipynb`
- macOS / log clutter: `.DS_Store`, `logs/`, `*.log`, `*.tmp`

Anything that contains private site data, machine paths, or run-specific artifacts belongs on this list.
