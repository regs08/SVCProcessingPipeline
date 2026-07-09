# `naming_ids/` - Private Grouping Tables

This directory is reserved for private scan-to-sample grouping CSV files used by
post-hoc averaging workflows. The CSV data are ignored by Git because they can
encode field collection identifiers.

Tracked files in this directory should document schema only. A typical table has
these columns:

| Column | Meaning |
|---|---|
| `scan_id` or `scans` | One scan number, or a `;`/`,`-separated group of scan numbers **in the same cell** — e.g. `1;2` averages scans 1 and 2 into one output row. Two separate rows sharing the same `name` do *not* get merged; grouping is per-row. |
| `name` | Output sample or group name. Rows named `reference` are skipped. |
| `reference` | Optional marker column that is dropped by `GroupSpec.from_csv()`. |

Use `pipeline.processor.GroupSpec.from_csv()` or
`pipeline.processor.SigSpectraAverager` to consume these tables from Python
(notebook workflows). From the terminal, point `svc-pipeline` at one of these
files via the config's `groups_csv` key or the `--groups-csv` flag — see
[`config/README.md`](../config/README.md#grouping--stage-3-optional).
