# `notebooks/` - Demo And Analysis Notebooks

Tracked notebook assets:

| Path | Purpose |
|---|---|
| [`pipeline_demo.ipynb`](pipeline_demo.ipynb) | Headless-runnable demo of loading, processing, plotting, exporting, and averaging SVC spectra. |
| [`pipeline_demo/`](pipeline_demo/) | Helper package and external demo-data manifest used by the demo notebook. |

The demo notebook is intentionally separate from the production path. Production
processing enters through `svc-pipeline`, `pipeline.cli`, and the modules in
`pipeline/`.

Raw `.sig` demo files are external and ignored by Git. Prepare them with:

```bash
python3 scripts/prepare_demo_data.py \
  --source-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom
```

See [`pipeline_demo/README.md`](pipeline_demo/README.md) for the full setup and
headless execution command.
