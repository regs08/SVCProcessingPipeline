# Pipeline Demo Notebook

[`pipeline_demo_notebook.ipynb`](pipeline_demo_notebook.ipynb) is a pip-first walkthrough
of Stage 1 truncation, Stage 2 resampling, reference/outlier filtering, plotting,
CSV export, and repeat-scan averaging.

## Run without cloning the repository

Download the notebook, open it in a Python 3.11 or newer Jupyter environment,
and run it top to bottom. The setup cells check the kernel version, then install
`svc-processing[demo]>=0.1.7` into the current kernel. No repository clone or
manual Python-path setup is required.

The tutorial assumes you already have a folder of authorized raw `.sig` scans.
Set `DATA_FOLDER` to that containing folder before continuing. The public repo
does not include field scans because SVC headers can contain timestamps and GPS
coordinates.

The reusable notebook API (`Spectrum`, `SpectraCollection`, `build_config`, and
plot/group helpers) is installed as `pipeline.notebook`. This directory's
[`svc.py`](svc.py) is only a compatibility re-export for older cloned notebooks.

## Use your own data

In the settings cells:

- point `DATA_FOLDER` at the folder containing your raw `.sig` files;
- leave `INSTRUMENT = "auto"` or select `"bronze"` / `"silver"` explicitly;
- set `END_LINE` to the exact maximum wavelength from the first data column when
  the calibrated default does not match your instrument; and
- choose an `OUTPUT_FOLDER` where the processed files and CSVs should be saved.

You can download the notebook alone, or clone the repository to get all project
documentation and config examples:

```bash
git clone https://github.com/regs08/SVCProcessingPipeline.git
cd SVCProcessingPipeline
```

Cloning does not download raw field scans. If you copy authorized scans beneath
the ignored `data/` directory, locate them with `find data -name '*.sig'`; use
the containing directory as `DATA_FOLDER`.

## Headless development check

CI builds a wheel, installs it into a clean virtual environment, copies the
notebook outside the repository, and executes it there. From a configured local
development environment, the shorter equivalent is:

```bash
SVC_DATA_FOLDER=/path/to/your/sig/folder \
  MPLBACKEND=Agg jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=600 \
  notebooks/pipeline_demo/pipeline_demo_notebook.ipynb \
  --output /tmp/demo_run.ipynb
```

## External field data

[`demo_data_manifest.json`](demo_data_manifest.json) and
[`../../scripts/prepare_demo_data.py`](../../scripts/prepare_demo_data.py) remain
available for explicitly authorized parity work with the external field dataset.
Those raw scans are ignored by Git and are not downloaded or packaged by the
pip-first notebook.
