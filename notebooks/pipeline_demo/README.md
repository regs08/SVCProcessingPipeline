# Pipeline Demo Notebook

This directory contains the helper package for `notebooks/pipeline_demo.ipynb`.
The notebook uses an external 15-file SVC HR-1024i demo dataset. Raw `.sig`
files are intentionally not tracked because their headers contain GPS/location
metadata.

## Prepare Demo Data

From the repository root, copy and verify the selected local files:

```bash
python3 scripts/prepare_demo_data.py \
  --source-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom
```

The script copies the manifest-listed files into
`notebooks/pipeline_demo/demo_data/spectra/` and verifies byte sizes and SHA256
checksums against `notebooks/pipeline_demo/demo_data_manifest.json`.

Once the external artifact is published, record its URL or DOI in the manifest.
Then a fresh clone can prepare the same data with:

```bash
python3 scripts/prepare_demo_data.py --download-url <artifact-url>
```

## Run The Notebook

```bash
MPLBACKEND=Agg jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=600 \
  notebooks/pipeline_demo.ipynb \
  --output /tmp/demo_run.ipynb
```

The notebook is **config-driven**. The opening cells let you set a data folder,
output folder, and instrument, then `build_config(...)` bundles them and
auto-detects the instrument from the `.sig` headers. To run it on your own scans,
edit the settings cell and point `DATA_FOLDER` at your folder.

For the bundled demo, an optional cell verifies the external `.sig` files against
`demo_data_manifest.json` and raises a clear setup error if any are missing or a
checksum differs. `config.prepare()` then truncates the raw files (Stage 1) into
`pipeline_outputs/notebook_run/processed_sig/`, mirroring the production
Stage 1 -> Stage 2 boundary while keeping generated `.sig` copies under ignored
output paths.
