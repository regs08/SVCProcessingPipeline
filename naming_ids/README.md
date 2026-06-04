# `naming_ids/` - Private Grouping Tables

This directory is reserved for private scan-to-sample grouping CSV files used by
post-hoc averaging workflows. The CSV data are ignored by Git because they can
encode field collection identifiers.

Tracked files in this directory should document schema only. A typical table has
these columns:

| Column | Meaning |
|---|---|
| `scan_id` or `scans` | One scan number or a comma/semicolon-separated group of scan numbers. |
| `name` | Output sample or group name. Rows named `reference` are skipped. |
| `reference` | Optional marker column that is dropped by `GroupSpec.from_csv()`. |

Use `pipeline.processor.GroupSpec.from_csv()` or
`pipeline.processor.SigSpectraAverager` to consume these tables.
