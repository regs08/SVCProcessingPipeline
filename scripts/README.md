# `scripts/` - Repository Utilities

Utilities here support reproducibility and setup, but are not production
pipeline entry points.

| File | Purpose |
|---|---|
| [`prepare_demo_data.py`](prepare_demo_data.py) | Copy, download, and verify the external `.sig` files used by the demo notebook. |

Production processing should use the installed `svc-pipeline` console script.
