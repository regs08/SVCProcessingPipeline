# `notebooks/` - Demo And Analysis Notebooks

Tracked notebook assets:

| Path | Purpose |
|---|---|
| [`pipeline_demo.ipynb`](pipeline_demo.ipynb) | Pip-first tutorial for loading, processing, plotting, exporting, and averaging SVC spectra. |
| [`pipeline_demo/`](pipeline_demo/) | Compatibility imports and documentation for the demo notebook. |

The demo notebook is intentionally separate from the production path. Production
processing enters through `svc-pipeline`, `pipeline.cli`, and the modules in
`pipeline/`.

Run the notebook top to bottom in a Python 3.11 or newer kernel. The setup cells
check the kernel version, then install `svc-processing[demo]>=0.1.6` into the
current kernel. Set `DATA_FOLDER` to the folder containing your authorized raw
scans; field data remain outside the public repository because instrument
headers can contain GPS and time metadata.

For a headless check from the repository root of a development clone:

```bash
SVC_DATA_FOLDER=/path/to/your/sig/folder \
  MPLBACKEND=Agg jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=600 notebooks/pipeline_demo.ipynb \
  --output /tmp/demo_run.ipynb
```

See [`pipeline_demo/README.md`](pipeline_demo/README.md) for the full setup and
headless execution command.
