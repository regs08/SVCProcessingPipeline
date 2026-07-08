# In-Depth Methods & Configuration Guide

A plain-language, in-depth guide to what this pipeline does, why it's built
the way it is, and how to configure it — written for a non-coder lab reader,
not a citable methods section. Answers three questions with confidence:

1. **What is each stage of the process?** → [Part 1](#part-1--the-pipeline-stages).
2. **Why do we run it with these parameter values?** → [Part 2](#part-2--the-parameters).
3. **Why is the pipeline built this way at all** (Python over R, this
   algorithm over off-the-shelf alternatives)? → [Part 3](#part-3--why-the-pipeline-is-built-this-way).

This is the practical, accessible companion to the formal
[supplementary_methods.md](supplementary_methods.md). Where they overlap,
the supplementary methods is the citable version with equations, formal
rationale, and parity statistics, meant for the manuscript; this file is the
one to read to actually understand and operate the pipeline, or to explain a
setting out loud. Code pointers are given so you can confirm any claim here
against the source.

---

## How the run is wired

You invoke the pipeline as `svc-pipeline [config]` (default `config/config.json`).
A run has **two CLI steps** ([cli.py](../pipeline/cli.py#L44-L52),
[runner.py](../pipeline/runner.py#L37-L58)):

| `--step` | Name | What it produces | Output dir |
|----------|------|------------------|------------|
| `1` | Process | Truncated copies of each `.sig` + a summary CSV | `processed_dir` |
| `2` | Resample | One merged, analysis-ready spectra CSV | `resampled_dir` |
| `all` | Both | Step 1 then Step 2 (the default) | both |

Step 1 is a light **pre-processing/truncation** pass. Step 2 is the real
scientific work: the five-stage resampling algorithm reproduced from R/`spectrolab`.

### Stages at a glance

| # | Stage | Config keys that affect it | Code |
|---|-------|----------------------------|------|
| 0 | Truncate file at the instrument end-line | `instrument.*.end_line`, `end_line_overrides` | [sig_processor.py:113](../pipeline/sig_processor.py#L113) |
| 1 | Parse `.sig`; perturb duplicate wavelengths; drop trailing junk | *(none — automatic)* | [resampler.py:`_read_sig`](../pipeline/resampler.py#L44) |
| 2 | Infer splice wavelengths from sensor boundaries | *(none — derived from data)* | [resampler.py:`_guess_splice_at`](../pipeline/resampler.py#L191) |
| 3 | Trim sensor overlap + radiometric sensor matching | `splice_interp_wvl`, `fixed_sensor` | [resampler.py:`_apply_match_sensors`](../pipeline/resampler.py#L237) |
| 4 | Resolution-matched Gaussian smoothing | *(none — `k=3` is hardcoded)* | [resampler.py:`_smooth_fwhm`](../pipeline/resampler.py#L313) |
| 5 | Gaussian resampling onto a 1 nm grid | `band_min`, `band_max`, `resample_fwhm_nm` | [resampler.py:`_gaussian_resample`](../pipeline/resampler.py#L348) |

Two things worth knowing up front:
- **Not every algorithmic choice is in the config.** The smoothing cluster count
  (`k = 3`) and the "three detectors" assumption (`_N_SENSORS = 3`) are constants
  in [resampler.py](../pipeline/resampler.py), not config keys, because they are
  tied to the instrument's physical design and should not vary per run.
- **The `processing` block is parity-locked.** Its five keys default to the
  values that make this pipeline numerically identical to R/`spectrolab`
  ([run_config.py:26](../pipeline/run_config.py#L26)). Changing any of them logs a
  warning that parity is no longer guaranteed
  ([run_config.py:197](../pipeline/run_config.py#L197)).

---

## Part 1 — The pipeline stages

In execution order. Each stage lists what comes in, what goes out, and the config
keys (if any) that steer it.

### Stage 0 — Truncate at the instrument end-line *(Step 1)*

**What:** The instrument is auto-detected from each `.sig` header (by serial
number), and all files in a directory must agree
([runner.py:79-91](../pipeline/runner.py#L79-L91)). Each file is then copied
line-by-line up to **and including** the line that begins with the instrument's
`end_line` wavelength, after which copying stops
([sig_processor.py:113-120](../pipeline/sig_processor.py#L113-L120)).

**Why it exists:** A correct SVC scan ends at the last band of Sensor 3
(~2520 nm). Some exports append corrupt trailing rows after that point. Cutting at
the known end-line removes them before anything else runs.

**In / out:** raw `.sig` → truncated `.sig` in `processed_dir`.

> Related: Stage 1 independently drops trailing junk inside `_read_sig` (the
> `_N_SENSORS = 3` safety net), so code paths that read raw files directly — e.g.
> the demo notebook, which skips Stage 0 — are also protected.

### Stage 1 — Parse and clean the band vector *(Step 2)*

**What:** Read wavelength (col 1) and reflectance (col 4 / 100) from the data
section. Exact-duplicate wavelengths at detector boundaries are nudged apart by a
tiny `1.2357e-05 × min-spacing` offset so both bands survive overlap trimming, and
any rows beyond the three valid detector sweeps are discarded
([resampler.py:44](../pipeline/resampler.py#L44)).

**Why:** Naively collapsing duplicate wavelengths drops a band and shifts
reflectance near the SWIR boundary; the perturbation preserves the band count for
parity. See [supplementary_methods.md §3](supplementary_methods.md).

### Stage 2 — Infer splice wavelengths *(Step 2)*

**What:** A new detector segment starts wherever the wavelength sequence jumps
backward. The splice wavelength between two detectors is computed from their
shared boundary ([resampler.py:191](../pipeline/resampler.py#L191)).

**Why:** Splices are *derived from the data*, not configured, so the pipeline
adapts to each file's exact band centres instead of assuming fixed boundaries.

### Stage 3 — Trim overlap + match sensors *(Step 2)*

**What:** Overlapping bands are clipped at the splice so each wavelength comes from
exactly one detector. Then the VNIR detector (Sensor 1) is rescaled by a
wavelength-ramped multiplicative factor so its reflectance agrees with the fixed
Sensor 2 at the first splice ([resampler.py:237](../pipeline/resampler.py#L237)).

**Why:** The three detectors are independently calibrated and disagree slightly
where they meet, producing artificial steps. Matching removes the step while
preserving spectral shape. Controlled by `fixed_sensor` and `splice_interp_wvl`
(see Part 2).

### Stage 4 — Resolution-matched Gaussian smoothing *(Step 2)*

**What:** A locally-adaptive Gaussian smoother whose kernel width tracks the native
band spacing, quantized into `k = 3` clusters (one per detector region).

**Why:** Fixed-width filters over- or under-smooth because the VNIR is densely
sampled (~1.3 nm) while the SWIR is coarser (~2.4–3.7 nm). Matching the kernel to
the local sampling smooths noise without flattening real features.

#### Why `k = 3`?

The smoothing width is *derived from* local band spacing, and each detector has its
own roughly-constant native spacing. So the per-band widths fall into three natural
groups — one per detector — and `kmeans(k=3)` lands almost exactly on them. Measured
on a real file ([resampler.py:337](../pipeline/resampler.py#L337)):

| Detector | Native spacing Δλ | `k=3` cluster center |
|----------|-------------------|----------------------|
| Sensor 1 (VNIR) | 1.31 nm | 1.26 nm |
| Sensor 3 (SWIR-2) | 2.46 nm | 2.44 nm |
| Sensor 2 (SWIR-1) | 3.69 nm | 3.66 nm |

So `k = 3` means *"give each detector its own smoothing strength."* Two caveats:
the mapping is **emergent** — kmeans clusters on the bandwidth value, not on detector
identity, so a few bands near a splice can land in a neighbor's cluster; and the
authoritative reason the value is `3` is **parity with `spectrolab`'s `make_fwhm`**,
for which "one per detector" is the physical justification rather than an
independent derivation. (Cluster centers shown are pre-doubling; Stage 4 then
applies `2×`, so the smoothing FWHMs used are ≈ 2.5 / 4.9 / 7.3 nm.)

### Stage 5 — Gaussian resampling to a 1 nm grid *(Step 2)*

**What:** Every spectrum is resampled onto integer wavelengths from `band_min` to
`band_max` using a Gaussian kernel of width `resample_fwhm_nm`.

**Why:** Different samples don't measure at identical wavelengths. A shared grid
makes spectra directly comparable for plotting, statistics, and ML. Controlled by
`band_min`, `band_max`, `resample_fwhm_nm` (see Part 2).

**Out:** one merged CSV — rows = samples, columns = integer wavelengths.

> **A 1 nm grid is *not* 1 nm resolution.** This trips people up: the native bands
> are spaced ~1.3 nm (VNIR) to ~3.7 nm (SWIR) apart — all *coarser* than 1 nm in the
> SWIR — so how can we output every 1 nm? Because resampling is **interpolation**, not
> new measurement. The pipeline fits a smooth Gaussian-weighted curve through the
> measured bands and reads it off at each integer nm; values between real bands are
> points *on that curve*, not new data. Two distinct quantities are at play:
>
> - **Band spacing** = how *often* we sample (the ruler's tick marks).
> - **Resolution (FWHM)** = how *blurry* each value is (what sets real detail). The
>   instrument's *native* FWHM varies by detector (~3.5–9.5 nm); the pipeline
>   standardizes everything to a common ~10 nm effective bandwidth.
>
> The 1 nm grid is just a common ruler, chosen finer than the densest native spacing
> so it never discards detail. Consequently adjacent 1 nm columns are **not
> independent** — the spectrum carries ~10 nm-scale information sampled every 1 nm,
> not 2101 independent measurements. *Mental model: 1 nm is the spacing of the ruler
> we lay the spectrum on, not the sharpness of the spectrum.* For the full physical
> picture — how the tick spacing and the blur are each set by the hardware — see
> [Appendix A](#appendix-a--spacing-resolution-and-resampling-a-concept-primer).

---

## Part 2 — The parameters

For each key: what it controls, why the value is what it is, and what changing it
does. Current values are from [config/config.json](../config/config.json).

### `processing` block — the parity-locked algorithm knobs

> All five default to the R/`spectrolab` parity values
> ([run_config.py:26](../pipeline/run_config.py#L26)). Editing any of them is a
> deliberate scientific choice that breaks the parity guarantee and emits a
> warning. Treat changes as a new processing decision, not a tweak.

#### `band_min = 400`, `band_max = 2500`

- **Stage:** 5 (output grid).
- **What:** Lower/upper bounds of the 1 nm output grid → 2101 output bands.
- **Why these values:** The instrument records ~340–2520 nm, but the extreme edges
  are noisy. 400–2500 nm keeps the usable reflective domain and drops the noisy
  fringes, matching the established workflow.
- **If you change it:** Narrowing is reasonable to exclude a study-specific noisy
  or atmospheric region. Widening past the instrument range just pads with
  poorly-constrained estimates. Either way, outputs are no longer column-aligned
  with prior 400–2500 nm results.
- **Note:** The 1 nm step is an *interpolation grid*, not the instrument's
  resolution — see the callout under [Stage 5](#stage-5--gaussian-resampling-to-a-1-nm-grid-step-2).

#### `resample_fwhm_nm = 10.0`

- **Stage:** 5 (resampling kernel width).
- **What:** Full-width at half-maximum of the Gaussian resampling kernel
  (σ ≈ 4.25 nm).
- **Why this value:** 10 nm is a moderate bandwidth — broad enough to stabilize
  estimates across uneven native spacing and damp narrow spikes, narrow enough to
  preserve the broad absorption/reflectance features used in field spectroscopy.
  It also matches `spectrolab`'s default.
- **If you change it:** Larger → smoother, better for broad-trend or noisy-signal
  work but blurs narrow features. Smaller → sharper, only if signal quality
  supports less smoothing.

#### `splice_interp_wvl = [5.0, 2.0]`

- **Stage:** 3 (sensor matching).
- **What:** Half-widths (nm) of the windows around each splice used to compute the
  matching ratio. `±5 nm` for the first splice, `±2 nm` for the second.
- **Why these values:** They keep the matching decision local to the splice so the
  correction reflects the boundary mismatch, not the whole spectrum. The values
  mirror `spectrolab`'s `interpolate_wvl` default.
- **Important nuance:** Because matching follows `spectrolab`'s `iter = 1` branch,
  **only the first splice is actually corrected** ([resampler.py:264](../pipeline/resampler.py#L264)),
  so the `5.0` is the one that matters in practice; the `2.0` is carried for
  completeness but not applied in the normal 3-sensor case.

#### `fixed_sensor = 2`

- **Stage:** 3 (sensor matching).
- **What:** **1-based** index of the detector held fixed (the radiometric anchor):
  `1` = VNIR, `2` = SWIR-1, `3` = SWIR-2.
- **Why `2`:** At the ~1000 nm splice the silicon VNIR detector is at its noisy
  dying edge while the InGaAs SWIR-1 is in a healthy part of its range — so SWIR-1
  is the more trustworthy reference there. With `fixed_sensor = 2`, SWIR-1 stays as
  measured and the VNIR is scaled to meet it. This is `spectrolab`'s default.
- **If you change it:** Re-anchoring changes which detector is treated as "truth"
  and deviates from the reference algorithm. Change only with strong
  instrument-specific evidence.

### `instrument` block — per-instrument calibration

```json
"instrument": {
  "bronze": { "end_line": "2520.4", "serial": "2212118" },
  "silver": { "end_line": "2517.9", "serial": "1202103" }
}
```

#### `end_line`

- **Stage:** 0 (truncation).
- **What:** The wavelength string marking the last valid band of Sensor 3. Stage 0
  cuts each file after the line starting with this value.
- **Why per-instrument:** The two physical units end their final detector at
  slightly different wavelengths (`bronze` 2520.4 nm, `silver` 2517.9 nm), so the
  truncation point is instrument-specific.
- **Caveat:** Matching is `startswith`, so the value must be the exact leading
  text of that band's line.

#### `serial`

- **Stage:** 0 (instrument auto-detection).
- **What:** The instrument's serial number, read from each `.sig` header to decide
  whether a file is `bronze` or `silver`
  ([runner.py:93-99](../pipeline/runner.py#L93-L99)). All files in a directory must
  resolve to the same instrument or the run aborts.
- **Why:** It selects the correct `end_line` (and any calibration) automatically,
  so you never hand-label files.

### `end_line_overrides`

- **Stage:** 0.
- **What:** A map keyed by instrument type (`"bronze"` / `"silver"`) that overrides
  the `end_line` for that instrument in this run
  ([runner.py:97](../pipeline/runner.py#L97)). Empty `{}` by default.
- **Why:** An escape hatch for a batch whose firmware/export wrote a different
  end-of-scan line, without editing the shared `instrument` block.

### I/O & run-control keys

These don't affect the science — only where files are read from and written to.

| Key | Meaning |
|-----|---------|
| `sig_input_dir` | Root directory of raw `.sig` files (the `<PATH_...>` placeholder must be edited or overridden with `--input-dir`). |
| `process_all_subdirs` | If `true`, each subdirectory containing `.sig` files is processed as its own group ([run_config.py:164](../pipeline/run_config.py#L164)). |
| `processed_dir` | Subfolder for Stage 0 truncated `.sig` copies (default `sig_processed`). |
| `resampled_dir` | Subfolder for the final resampled CSV (default `sig_resampled`). |
| `output_dir` | Root that `processed_dir`/`resampled_dir` are created under (default `pipeline_outputs`). |
| `summary_csv_name` | Filename suffix for the per-group Step 1 summary CSV. |
| `merged_csv_name` | Filename suffix for the merged Step 2 spectra CSV. |

---

## Quick "is it safe to change?" guide

| Key(s) | Safe to change? | When you might | Cost |
|--------|-----------------|----------------|------|
| `output_dir`, `*_dir`, `*_csv_name` | ✅ Freely | Reorganizing outputs | None |
| `sig_input_dir`, `process_all_subdirs` | ✅ Freely | Pointing at new data | None |
| `serial`, `end_line` | ⚠️ Only for a new physical instrument | Adding a unit / firmware change | Wrong value mis-truncates files |
| `band_min`, `band_max` | ⚠️ With justification | Excluding a noisy/atmospheric region | Outputs no longer column-aligned; parity warning |
| `resample_fwhm_nm` | ⚠️ With justification | Noisier data or broad-trend analysis | Parity warning; changes smoothing |
| `splice_interp_wvl`, `fixed_sensor` | ⛔ Avoid | Only with strong instrument evidence | Breaks detector reconciliation **and** parity |

The rule of thumb: **I/O keys are yours to set; `instrument` keys track the
hardware; the `processing` block is locked to the validated `spectrolab` algorithm
and should move only as a documented scientific decision.**

---

## Part 3 — Why the pipeline is built this way

Two design decisions sit above the config file and aren't things you can
tune — they're why this codebase exists in this form at all. The full
formal argument (with citations) is `supplementary_methods.md` §6–7; this is
the plain-language version.

### Why Python instead of the original R/`spectrolab` pipeline?

The original pipeline was written in R against the `spectrolab` package. This
repo is an independent Python reimplementation ("Pipeline B" in
`supplementary_methods.md`), verified to reproduce R's output to within
1.10 × 10⁻⁶ absolute reflectance across 66 real samples — far below the
instrument's own noise floor, so the two are numerically interchangeable.
Given that, Python won on practical grounds:

- **One toolchain, not two.** Everything downstream of this pipeline
  (statistics, figures, ML) is already Python. Keeping R in the loop just
  for this one step means maintaining an R install, `spectrolab`, and an
  R↔Python handoff indefinitely.
- **Faster.** NumPy's vectorized, BLAS-backed operations outperform the R
  reference on equivalent hardware.
- **Simpler to install and pip-package.** `pip install -e .` and a single
  `pyproject.toml` cover the whole dependency graph — no parallel R
  environment/lockfile to keep in sync.

The R implementation is kept in [`archived_r_scripts/`](../archived_r_scripts/)
purely as the frozen reference for the parity test, not as a second
production path.

### Why not use an existing Python spectroscopy library?

Before writing a from-scratch reimplementation, the obvious alternative —
`specdal`, the closest existing community library for field spectroscopy —
was evaluated and rejected. It falls short in four concrete ways for this
instrument:

- It's built for a different instrument's file convention (ASD, not SVC) and
  has no logic to auto-detect this instrument's sensor boundaries from the
  file itself — you'd have to bolt that detection on yourself, which is most
  of the hard part of this pipeline anyway.
- Its detector-boundary correction only shifts each sensor by a constant
  offset. If one detector is systematically *tilted* relative to its
  neighbor (not just offset), that tilt survives uncorrected. `spectrolab`'s
  approach (reproduced here — see [Part 1, Stage 3](#stage-3--trim-overlap--match-sensors-step-2))
  fixes both the offset and the tilt.
- It doesn't trim overlapping bands where two sensors both measure the same
  wavelength — those would either duplicate or get flattened by a plain
  average, neither of which matches the splice-trimming this pipeline (and
  `spectrolab`) uses.
- It has no resolution-matched smoothing — no equivalent of
  [Stage 4](#stage-4--resolution-matched-gaussian-smoothing-step-2)'s
  per-detector adaptive Gaussian kernel.

On top of the technical gaps, most published SVC HR-1024i work in the field
uses `spectrolab` as the reference tool — so reproducing its exact algorithm
(rather than approximating it with a different library) is also what keeps
this pipeline's output comparable to the rest of the literature.

---

## Appendix A — Spacing, resolution, and resampling (a concept primer)

The most common source of confusion about this pipeline is conflating three
*distinct* quantities. Keeping them separate explains why we can output a 1 nm grid
from coarser bands, and why that grid is not a resolution claim.

| Quantity | Plain meaning | What physically sets it | HR-1024i value |
|----------|---------------|--------------------------|----------------|
| **Spectral coverage** | The total wavelength range | Grating + detector layout | ~340–2520 nm |
| **Sampling interval** (band spacing) | How *often* a measurement is taken — the ruler's tick marks | Detector **pixel pitch** projected through the grating (≈ range ÷ pixel count) | ~1.3 / 3.7 / 2.5 nm per detector |
| **Spectral resolution** (FWHM) | How *blurry* each measurement is — a width *centered on the band*, not a 0-to-X range | Width of the **entrance-slit image** on the detector | native ~3.5 / 9.5 / 6.5 nm; pipeline imposes ~10 nm |

### How the tick spacing is set

The instrument is a dispersive spectrometer: a grating spreads incoming light by
wavelength across a fixed row of detector pixels, and each pixel permanently catches
one fixed slice. So the spacing is not chosen per scan — it is **range ÷ pixel
count**:

| Detector | Pixels | Range | Range ÷ pixels | Measured Δλ |
|----------|--------|-------|----------------|-------------|
| VNIR (Si) | 512 | ~670 nm | ≈1.31 nm | 1.31 |
| SWIR-1 (InGaAs) | 256 | ~940 nm | ≈3.67 nm | 3.69 |
| SWIR-2 (ext. InGaAs) | 256 | ~630 nm | ≈2.46 nm | 2.46 |

Grating dispersion is slightly nonlinear, so the spacing drifts band-to-band; that
is why each `.sig` file stores a factory-calibrated centre wavelength for *every*
band rather than one spacing number.

### How the blur (resolution) is set — and why it is wider than the spacing

The blur is set by a *different* part of the instrument: the **entrance slit**,
whose image on the detector is the window of light each band integrates. Designers
deliberately make that slit image span **~2–3 pixels** so the optical response is
never undersampled. The direct consequence:

> **resolution (FWHM) ≈ 2–3 × sampling interval**

| Detector | Sampling | Native FWHM | ratio |
|----------|----------|-------------|-------|
| VNIR | ~1.5 nm | ~3.5 nm | ≈2.3× |
| SWIR-1 | ~3.8 nm | ~9.5 nm | ≈2.5× |
| SWIR-2 | ~2.5 nm | ~6.5 nm | ≈2.6× |

This intentional over-spanning is *why neighbouring bands overlap and are
correlated* — the property that makes resampling valid in the first place.

### Native vs. imposed resolution

The instrument's native FWHM **varies by detector** (above). The flat **10 nm**
we use everywhere is the bandwidth the *pipeline imposes* (`resample_fwhm_nm`),
chosen ≈ the instrument's **broadest** native resolution (SWIR-1's ~9.5 nm). The
logic: you can smooth a sharp region down to a coarser common bandwidth, but you
cannot sharpen a blurry one — so a single achievable effective resolution is
applied across the whole spectrum.

### Resampling and upsampling

**Resampling** re-expresses the spectrum on a new set of ticks by **interpolation**.
For each target wavelength, the output is a **distance-weighted average of nearby
measured bands**, weighted by a Gaussian whose width comes from the FWHM
(σ ≈ 4.25 nm for 10 nm). *Every* nearby band contributes, weighted — nothing is
selected or discarded.

**Upsampling** is resampling onto a grid with *more* points (finer spacing) than the
original measurements — e.g. emitting a value every 1 nm from bands measured every
2.5 nm. It adds grid points by interpolation; it never adds real detail or sharpens
the blur.

**Worked example** — native bands every 2.5 nm, computing the new 1 nm tick at 2001 nm:

```
Measured band centres:  2000.0   2002.5   2005.0  ...
New 1 nm grid:          2000  2001  2002  2003  2004  2005

weight_i   = exp( -0.5 * ((λ_i − 2001) / 4.25)² )
value(2001) = Σ(weight_i × reflectance_i) / Σ(weight_i)
```

The value at 2001 nm is a point *on the fitted curve*, not a measurement. The band
centred at 2002.5 nm, with its ~10 nm blur, is actually sensitive to ~1997.5–2007.5
nm (centre ± FWHM/2), which is why it overlaps its neighbours.

### Mental models to keep

- **Spacing** = where the ruler's ticks are. **Resolution** = how wide/blurry each
  reading is, centred on its tick. **Coverage** = the whole range.
- **resolution ≈ 2–3 × spacing**, by slit design — that overlap is what permits
  resampling.
- A **1 nm grid is the spacing of the ruler we lay the spectrum on, not the
  sharpness of the spectrum.** Adjacent 1 nm columns are correlated, not independent.
- **Upsampling** adds ticks; it never adds detail.
