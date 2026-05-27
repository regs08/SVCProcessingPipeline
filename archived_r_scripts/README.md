# `archived_r_scripts/` — Legacy R Reference Implementation

R/`spectrolab` source preserved for reference and for regenerating Pipeline A outputs when running a new parity verification. **Not invoked by the production pipeline**, which is now 100 % Python ([`pipeline/resampler.py`](../pipeline/resampler.py)).

## Files

### [`merge_resample_sig.R`](merge_resample_sig.R)
The original resampling script. Reads `.sig` files from an input directory and writes a `merged_spectra.csv` to an output directory using `spectrolab`'s canonical pipeline:

```
read_spectra → guess_splice_at → match_sensors → smooth → resample(new_bands = 400:2500, fwhm = 10)
```

Usage:

```bash
Rscript archived_r_scripts/merge_resample_sig.R <input_dir> <output_dir> [output_filename]
```

Or via environment variables:

```bash
SIG_RESAMPLE_INPUT=<input_dir> \
SIG_RESAMPLE_OUTPUT=<output_dir> \
Rscript archived_r_scripts/merge_resample_sig.R
```

Default output filename is `merged_spectra.csv`.

Comment block at the top records the two known instrument serials:
- Bronze: `2212118`
- Silver: `1202103`

## Why keep it?
- **Parity verification.** [`tests/test_resampler_parity.py`](../tests/test_resampler_parity.py) compares Python output against a reference CSV produced by this script. New parity reports (see [`docs/parity_retest_prompt.md`](../docs/parity_retest_prompt.md)) regenerate that CSV from this script.
- **Provenance.** The manuscript ([`docs/supplementary_methods.md`](../docs/supplementary_methods.md)) cites this as Pipeline A; preserving it under version control keeps the audit chain intact.
- **Algorithmic reference.** When [`pipeline/resampler.py`](../pipeline/resampler.py) needs to be modified, this script (plus the underlying `spectrolab` source) is the authoritative behavioural specification.

## Requirements
- R ≥ 4.3 (parity reports were produced under R 4.5.1).
- `spectrolab` (0.0.18 / 0.0.19 verified) — Meireles et al., 2020, *JOSS*, 5(53), 2526. <https://doi.org/10.21105/joss.02526>
- `readr` (only for `write_csv`).

## Do not edit
Treat this script as frozen. If the production algorithm needs to change, change [`pipeline/resampler.py`](../pipeline/resampler.py) and re-run the parity test with **this** script as the reference — that is how we know the new Python behaviour is intentional and not a drift.
