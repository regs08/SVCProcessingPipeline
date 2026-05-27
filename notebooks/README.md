# `notebooks/` — Exploratory & Visualization Notebooks

Jupyter notebooks used for interactive inspection of processed and resampled spectra. None of these are required for the production pipeline; they are convenience tools.

Notebooks generally assume the pipeline has already been run, i.e. `pipeline_outputs/sig_processed/<run>/` and `pipeline_outputs/sig_resampled/<run>/` exist.

## Notebooks

### [`sig_spectra_visualization.ipynb`](sig_spectra_visualization.ipynb) — *tracked*
Quick plots over processed/resampled outputs. Update placeholder strings (e.g. `<REPO_ROOT>/pipeline_outputs/...`) with your actual run folders before executing cells. Keep notebooks committed without personal paths.

### [`weekly_sig_spectra_visualization.ipynb`](weekly_sig_spectra_visualization.ipynb) — *gitignored*
Weekly-run variant; held out of version control via [`.gitignore`](../.gitignore) because it tends to accumulate machine-specific paths and run-specific data.

### [`spectral_change_analysis.ipynb`](spectral_change_analysis.ipynb) — *gitignored*
Ad-hoc spectral-change analyses. Also gitignored for the same reason.

## Conventions
- **No machine paths in committed notebooks.** Use `<REPO_ROOT>` / `<RUN_NAME>` placeholders and resolve them at the top of the notebook.
- Notebooks should import from `pipeline.*` rather than re-implementing pipeline logic — see [`pipeline/processor.py`](../pipeline/processor.py) for `SVCDataProcessor` / `SigSpectraAverager` helpers built for this use case.
- Group-spec CSVs typically come from [`naming_ids/`](../naming_ids/); load them with `GroupSpec.from_csv(...)`.
- Clear cell outputs before committing, or use a `nbstripout` filter, to keep diffs reviewable.
