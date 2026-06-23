# Acknowledgments & Citation

## Relationship to spectrolab

The resampling stage ([`pipeline/resampler.py`](pipeline/resampler.py)) is an
**independent, pure-Python reimplementation** of the spectra-processing algorithm
in the **spectrolab** R package. No spectrolab source code is included or
distributed in this repository — only the published algorithm (sensor matching,
FWHM smoothing, Gaussian resampling) was reimplemented in NumPy/SciPy and
numerically verified against spectrolab's output (see the *Verification* section
of the [README](README.md)).

The frozen reference script
[`archived_r_scripts/merge_resample_sig.R`](archived_r_scripts/merge_resample_sig.R)
*calls* spectrolab but contains none of its source. Running it requires
installing `spectrolab` separately under its own **GPL-3** license.

This repository is distributed under **GPL-3.0-only** for license compatibility
with `spectrolab`, which is the reference implementation for the resampling
algorithm.

## Third-party software

| Software | License | Use in this project |
|---|---|---|
| [spectrolab](https://github.com/meireles/spectrolab) | GPL-3 | Algorithm reimplemented (no source copied); R reference for the parity test |
| [specdal](https://github.com/EnSpec/SpecDAL) | MIT | Related field-spectroscopy toolkit consulted during design; not a dependency |
| [numpy](https://numpy.org), [scipy](https://scipy.org), [pandas](https://pandas.pydata.org) | BSD-3-Clause | Runtime numerical core |

## How to cite

If you use this software, please also cite **spectrolab**, whose algorithm it
reimplements:

> Meireles JE, Schweiger A, Cavender-Bares J (2017). *spectrolab: Class and
> Methods for Spectral Data in R.* R package.
> doi:[10.5281/zenodo.3934575](https://doi.org/10.5281/zenodo.3934575).
> <https://CRAN.R-project.org/package=spectrolab>

For the canonical, version-specific reference, run `citation("spectrolab")` in R.

To cite this pipeline itself, reference the repository and its author
(Cole Regnier); a versioned archive/DOI may be added on release.
