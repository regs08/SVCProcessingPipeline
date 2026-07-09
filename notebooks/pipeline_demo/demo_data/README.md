# Demo Data Target

Place the external `.sig` demo files in `spectra/` by running:

```bash
python3 scripts/prepare_demo_data.py \
  --source-dir data/a4any_sb_2025-cn_ch-svc-aviris_bottom
```

The raw `.sig` files are ignored by Git because their headers contain
GPS/location metadata. The tracked manifest is
`notebooks/pipeline_demo/demo_data_manifest.json`.
