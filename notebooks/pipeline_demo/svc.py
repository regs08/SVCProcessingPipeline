"""
High-level wrappers around the SVC pipeline for use in demo notebooks.

Designed for readers with limited Python experience: every public method has a
single, obvious purpose and uses descriptive variable names throughout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Make the project root importable regardless of where the notebook is opened
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.resampler import (
    _read_sig,
    _sensor_segment_indices,
    _guess_splice_at,
    _trim_and_assign,
    _apply_match_sensors,
    _smooth_fwhm,
    _gaussian_resample,
)
from pipeline.processor import SigSpectraAverager

# Standard output wavelength grid used by the pipeline (matches spectrolab)
STANDARD_WAVELENGTHS = np.arange(400, 2501, dtype=float)


# ── Single spectrum ────────────────────────────────────────────────────────────

class Spectrum:
    """
    One SVC spectrum loaded from a .sig file.

    Usage
    -----
    spectrum = Spectrum("path/to/file.sig")
    print(spectrum)           # summary
    spectrum.plot()           # raw plot
    spectrum.process()        # run splice correction + smooth + resample
    spectrum.plot()           # processed plot
    """

    def __init__(self, filepath: str | Path) -> None:
        path = Path(filepath)
        self.name = path.stem
        self.filepath = path

        raw_wavelengths, raw_reflectance = _read_sig(path)
        self._raw_wavelengths = raw_wavelengths
        self._raw_reflectance = raw_reflectance

        segments = _sensor_segment_indices(raw_wavelengths)
        self.sensor_count = len(segments)
        self.splice_wavelengths = _guess_splice_at(segments, raw_wavelengths)
        self._segments = segments

        # Populated by process()
        self.wavelengths: np.ndarray | None = None
        self.reflectance: np.ndarray | None = None
        self._corrected_wavelengths: np.ndarray | None = None
        self._corrected_reflectance: np.ndarray | None = None
        self.is_processed: bool = False

    # ── dunder ──────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Spectrum\n"
            f"  name              : {self.name}\n"
            f"  bands             : {len(self._raw_wavelengths)}"
            f"  ({self._raw_wavelengths.min():.1f} – {self._raw_wavelengths.max():.1f} nm)\n"
            f"  sensor count      : {self.sensor_count}\n"
            f"  splice wavelengths: {[f'{w:.1f} nm' for w in self.splice_wavelengths]}\n"
            f"  reflectance range : {self._raw_reflectance.min():.4f}"
            f" – {self._raw_reflectance.max():.4f}\n"
            f"  processed         : {self.is_processed}\n"
        )

    # ── processing ──────────────────────────────────────────────────────────

    def process(self) -> "Spectrum":
        """
        Run the full pipeline on this spectrum.

        Steps
        -----
        1. Trim sensor overlaps at splice wavelengths
        2. Apply multiplicative sensor correction (match_sensors)
        3. Gaussian smooth with per-band bandwidth
        4. Gaussian resample to 400 – 2500 nm at 1 nm spacing
        """
        sensor_indices = _trim_and_assign(
            self._segments, self._raw_wavelengths, self.splice_wavelengths
        )
        corrected_wavelengths, corrected_reflectance = _apply_match_sensors(
            self._raw_wavelengths,
            self._raw_reflectance,
            sensor_indices,
            self.splice_wavelengths,
            fixed_sensor=min(2, self.sensor_count),
        )
        self._corrected_wavelengths = corrected_wavelengths
        self._corrected_reflectance = corrected_reflectance

        smoothed_reflectance = _smooth_fwhm(corrected_wavelengths, corrected_reflectance)

        self.wavelengths = STANDARD_WAVELENGTHS.copy()
        self.reflectance = _gaussian_resample(
            corrected_wavelengths, smoothed_reflectance, STANDARD_WAVELENGTHS
        )
        self.is_processed = True
        return self

    # ── plotting ────────────────────────────────────────────────────────────

    def plot_processing_steps(self) -> None:
        """
        Show a three-panel comparison for this spectrum.

        Panel 1 — raw data in file order (sensor fold-backs visible)
        Panel 2 — after multiplicative splice correction
        Panel 3 — final output: smooth + resampled to 400 – 2 500 nm

        Call process() before calling this method.
        """
        if not self.is_processed:
            raise RuntimeError(
                "Call spectrum.process() before plotting processing steps."
            )

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        axes[0].plot(self._raw_wavelengths, self._raw_reflectance, lw=0.8, color="steelblue")
        for splice_wavelength in self.splice_wavelengths:
            axes[0].axvline(splice_wavelength, color="red", lw=0.8, ls="--", alpha=0.6)
        axes[0].set_title("Raw (sensor fold-backs)")
        axes[0].set_xlabel("Wavelength (nm)")
        axes[0].set_ylabel("Reflectance")

        axes[1].plot(self._corrected_wavelengths, self._corrected_reflectance, lw=0.8, color="darkorange")
        for splice_wavelength in self.splice_wavelengths:
            axes[1].axvline(splice_wavelength, color="red", lw=0.8, ls="--", alpha=0.6)
        axes[1].set_title("After splice correction")
        axes[1].set_xlabel("Wavelength (nm)")

        axes[2].plot(self.wavelengths, self.reflectance, lw=0.8, color="forestgreen")
        axes[2].set_title("After smooth + resample  (400 – 2 500 nm)")
        axes[2].set_xlabel("Wavelength (nm)")

        for ax in axes:
            ax.grid(alpha=0.2)

        fig.suptitle(self.name, fontsize=10)
        plt.tight_layout()
        plt.show()

    def plot(self, ax=None, **kwargs) -> plt.Axes:
        """
        Plot this spectrum.  Uses processed data if available, raw otherwise.
        Pass an existing Axes object via `ax` to overlay on an existing figure.
        """
        standalone = ax is None
        if standalone:
            _, ax = plt.subplots(figsize=(10, 4))

        if self.is_processed:
            ax.plot(self.wavelengths, self.reflectance,
                    label=self.name, **kwargs)
        else:
            ax.plot(self._raw_wavelengths, self._raw_reflectance,
                    label=self.name, **kwargs)

        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance")
        ax.grid(alpha=0.2)

        if standalone:
            ax.set_title(self.name)
            ax.legend()
            plt.tight_layout()
            plt.show()

        return ax


# ── Collection of spectra ──────────────────────────────────────────────────────

class SpectraCollection:
    """
    A set of SVC spectra loaded from a folder of .sig files.

    Usage
    -----
    collection = SpectraCollection("path/to/sig/folder")
    collection.summary()                   # print per-file info
    collection.plot_raw()                  # visualize before processing
    collection.process()                   # run the full pipeline
    collection.plot_processing_steps()     # before / after comparison
    collection.plot()                      # all processed spectra
    """

    def __init__(self, directory: str | Path, n_files: int | None = None) -> None:
        directory = Path(directory)
        sig_files = sorted(directory.glob("*.sig"))
        if n_files is not None:
            sig_files = sig_files[:n_files]
        if not sig_files:
            raise FileNotFoundError(f"No .sig files found in {directory}")

        self.name = directory.name
        self.spectra = [Spectrum(path) for path in sig_files]

    # ── dunder ──────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.spectra)

    def __repr__(self) -> str:
        processed_count = sum(1 for spectrum in self.spectra if spectrum.is_processed)
        return (
            f"SpectraCollection\n"
            f"  name      : {self.name}\n"
            f"  spectra   : {len(self.spectra)}\n"
            f"  processed : {processed_count} / {len(self.spectra)}\n"
        )

    # ── filtering ───────────────────────────────────────────────────────────

    def filter_reference_scans(self, reflectance_threshold: float = 0.9) -> "SpectraCollection":
        """
        Remove white-reference panel scans from the collection in place.

        A scan is identified as a reference panel when its **median raw reflectance**
        exceeds ``reflectance_threshold`` (default 0.9).  Reference panels are
        measured against a Spectralon target and have reflectance close to 1.0
        across the entire spectrum.

        Parameters
        ----------
        reflectance_threshold : scans with median reflectance above this value
                                are removed (default 0.9)
        """
        count_before = len(self.spectra)
        self.spectra = [
            spectrum for spectrum in self.spectra
            if np.median(spectrum._raw_reflectance) < reflectance_threshold
        ]
        count_removed = count_before - len(self.spectra)
        print(f"filter_reference_scans: removed {count_removed}, {len(self.spectra)} remaining.")
        return self

    def filter_outliers(self, n_std: float = 2.5) -> "SpectraCollection":
        """
        Remove spectral outliers from the collection in place.

        A spectrum is an outlier when its mean raw reflectance falls more than
        ``n_std`` standard deviations from the group mean.  Run this *after*
        ``filter_reference_scans`` so that the reference panels do not skew the
        group statistics.

        Parameters
        ----------
        n_std : number of standard deviations beyond which a scan is removed
                (default 2.5)
        """
        mean_reflectances = np.array(
            [spectrum._raw_reflectance.mean() for spectrum in self.spectra]
        )
        group_mean = mean_reflectances.mean()
        group_std  = mean_reflectances.std()

        count_before = len(self.spectra)
        self.spectra = [
            spectrum
            for spectrum, mean_r in zip(self.spectra, mean_reflectances)
            if abs(mean_r - group_mean) <= n_std * group_std
        ]
        count_removed = count_before - len(self.spectra)
        print(f"filter_outliers:        removed {count_removed}, {len(self.spectra)} remaining.")
        return self

    # ── inspection ──────────────────────────────────────────────────────────

    def summary(self) -> None:
        """Print a one-block summary for every spectrum in the collection."""
        for spectrum in self.spectra:
            print(spectrum)

    # ── processing ──────────────────────────────────────────────────────────

    def process(self) -> "SpectraCollection":
        """Run the full pipeline on every spectrum in the collection."""
        for spectrum in self.spectra:
            spectrum.process()
        return self

    # ── plotting ────────────────────────────────────────────────────────────

    def plot_raw(self) -> None:
        """
        Plot all spectra in file order (wavelengths are NOT sorted).

        The wavelength sequence resets twice — once near 1 000 nm and once
        near 1 830 nm — where the second and third sensor arrays begin.
        These fold-backs are the artifact the pipeline corrects.
        """
        fig, ax = plt.subplots(figsize=(12, 5))
        for spectrum in self.spectra:
            ax.plot(
                spectrum._raw_wavelengths,
                spectrum._raw_reflectance,
                lw=0.7, alpha=0.7,
                label=spectrum.name,
            )
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance")
        ax.set_title("Raw spectra — sensor fold-backs visible at splice boundaries")
        ax.legend(fontsize="x-small", ncol=2)
        ax.grid(alpha=0.2)
        plt.tight_layout()
        plt.show()

    def plot_processing_steps(self, spectrum_index: int = 1) -> None:
        """
        Show a three-panel before / after comparison for one spectrum.

        Parameters
        ----------
        spectrum_index : int
            Position in the collection (0-based).  Defaults to 1 to skip the
            white-reference panel which is typically stored at index 0.
        """
        spectrum = self.spectra[spectrum_index]
        if not spectrum.is_processed:
            raise RuntimeError(
                "Call collection.process() before plotting processing steps."
            )

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        # Panel 1 — raw (file order, fold-backs visible)
        axes[0].plot(
            spectrum._raw_wavelengths, spectrum._raw_reflectance,
            lw=0.8, color="steelblue",
        )
        for splice_wavelength in spectrum.splice_wavelengths:
            axes[0].axvline(splice_wavelength, color="red", lw=0.8, ls="--", alpha=0.6)
        axes[0].set_title("Raw (sensor fold-backs)")
        axes[0].set_xlabel("Wavelength (nm)")
        axes[0].set_ylabel("Reflectance")

        # Panel 2 — after multiplicative splice correction
        axes[1].plot(
            spectrum._corrected_wavelengths, spectrum._corrected_reflectance,
            lw=0.8, color="darkorange",
        )
        for splice_wavelength in spectrum.splice_wavelengths:
            axes[1].axvline(splice_wavelength, color="red", lw=0.8, ls="--", alpha=0.6)
        axes[1].set_title("After splice correction")
        axes[1].set_xlabel("Wavelength (nm)")

        # Panel 3 — final output (smooth + resampled to 400–2500 nm)
        axes[2].plot(spectrum.wavelengths, spectrum.reflectance, lw=0.8, color="forestgreen")
        axes[2].set_title("After smooth + resample  (400 – 2 500 nm)")
        axes[2].set_xlabel("Wavelength (nm)")

        for ax in axes:
            ax.grid(alpha=0.2)

        fig.suptitle(spectrum.name, fontsize=10)
        plt.tight_layout()
        plt.show()

    def plot(self, title: str | None = None) -> None:
        """Overlay all processed spectra on one figure."""
        unprocessed = [s for s in self.spectra if not s.is_processed]
        if unprocessed:
            raise RuntimeError(
                f"{len(unprocessed)} spectra not yet processed.  "
                "Call collection.process() first."
            )

        fig, ax = plt.subplots(figsize=(12, 5))
        for spectrum in self.spectra:
            ax.plot(spectrum.wavelengths, spectrum.reflectance,
                    lw=0.8, alpha=0.8, label=spectrum.name)

        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance")
        ax.set_title(title or f"Processed spectra — {self.name}")
        ax.legend(fontsize="x-small", ncol=2)
        ax.grid(alpha=0.2)
        plt.tight_layout()
        plt.show()


# ── Grouping helpers (work on the resampled CSV) ───────────────────────────────

def average_groups(csv_path: str | Path, groups: list[tuple]) -> pd.DataFrame:
    """
    Load a resampled spectra CSV and compute a mean spectrum per group.

    Parameters
    ----------
    csv_path : path to the *_merged_spectra.csv produced by the pipeline
    groups   : list of scan-number tuples, e.g. [(1, 2, 3), (4, 5, 6)]

    Returns
    -------
    DataFrame with one row per group and wavelength columns 400 – 2 500 nm
    """
    averager = SigSpectraAverager.from_csv(str(csv_path), sample_col="sample_name")
    return averager.aggregate(groups)


# ── Collection export ──────────────────────────────────────────────────────────

def save_spectra_csv(collection: "SpectraCollection", output_path: str | Path) -> Path:
    """
    Save all processed spectra in a collection to a CSV file.

    The file has one row per spectrum, a ``sample_name`` index column, and one
    column per wavelength (400 – 2 500, labelled by integer nm value).

    Parameters
    ----------
    collection  : SpectraCollection whose spectra have all been processed
    output_path : destination file path (created if it does not exist)

    Returns
    -------
    Path to the saved file
    """
    unprocessed = [s for s in collection.spectra if not s.is_processed]
    if unprocessed:
        raise RuntimeError(
            f"{len(unprocessed)} spectra not yet processed.  "
            "Call collection.process() first."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = {
        spectrum.name: spectrum.reflectance
        for spectrum in collection.spectra
    }
    dataframe = pd.DataFrame(
        rows,
        index=STANDARD_WAVELENGTHS.astype(int),
    ).T
    dataframe.index.name = "sample_name"
    dataframe.to_csv(output_path)
    return output_path


# ── Group mean plot ────────────────────────────────────────────────────────────

def plot_group_means(
    collections: list,
    labels: list[str],
    title: str | None = None,
) -> plt.Axes:
    """
    Overlay the mean spectrum from each collection on a single figure.

    Each mean is computed as the simple arithmetic average of all processed
    spectra in that collection.  Individual spectra are drawn faded behind
    each mean so you can see the within-group spread.

    Parameters
    ----------
    collections : list of SpectraCollection objects (all processed)
    labels      : display name for each collection (same order as collections)
    title       : optional figure title
    """
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(12, 5))

    for group_index, (collection, label) in enumerate(zip(collections, labels)):
        unprocessed = [s for s in collection.spectra if not s.is_processed]
        if unprocessed:
            raise RuntimeError(
                f"Collection '{label}' has {len(unprocessed)} unprocessed spectra.  "
                "Call collection.process() first."
            )
        color = color_cycle[group_index % len(color_cycle)]

        all_reflectance = np.array([s.reflectance for s in collection.spectra])
        for individual_reflectance in all_reflectance:
            ax.plot(STANDARD_WAVELENGTHS, individual_reflectance,
                    color=color, lw=0.6, alpha=0.25)

        mean_reflectance = all_reflectance.mean(axis=0)
        ax.plot(STANDARD_WAVELENGTHS, mean_reflectance,
                color=color, lw=2.0, label=f"{label}  (n={len(collection)})")

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Reflectance")
    ax.set_title(title or "Group means  (individuals faded)")
    ax.legend()
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
    return ax


# ── DM vs healthy comparison helpers ──────────────────────────────────────────

def _reflectance_at(spectrum: "Spectrum", wavelength_nm: float) -> float:
    """Return the processed reflectance value nearest to wavelength_nm."""
    index = int(np.searchsorted(spectrum.wavelengths, wavelength_nm))
    return float(spectrum.reflectance[np.clip(index, 0, len(spectrum.reflectance) - 1)])


def compute_indices(spectrum: "Spectrum") -> dict:
    """
    Compute a set of spectral indices for one processed spectrum.

    Indices returned
    ----------------
    NDVI        : Normalised Difference Vegetation Index  (RED=670 nm, NIR=800 nm)
    NDWI        : Normalised Difference Water Index — Gao 1996  (NIR=860 nm, SWIR=1 240 nm)
    Simple Ratio: NIR / RED  (800 nm / 670 nm)

    Parameters
    ----------
    spectrum : a Spectrum that has already been processed (spectrum.process())

    Returns
    -------
    dict mapping index name → float value
    """
    if not spectrum.is_processed:
        raise RuntimeError(
            "Call spectrum.process() before computing indices."
        )

    red       = _reflectance_at(spectrum, 670)
    nir_800   = _reflectance_at(spectrum, 800)
    nir_860   = _reflectance_at(spectrum, 860)
    swir_1240 = _reflectance_at(spectrum, 1240)

    ndvi         = (nir_800 - red) / (nir_800 + red)
    ndwi         = (nir_860 - swir_1240) / (nir_860 + swir_1240)
    simple_ratio = nir_800 / red if red > 0 else float("nan")

    return {
        "NDVI":         round(ndvi, 4),
        "NDWI":         round(ndwi, 4),
        "Simple Ratio": round(simple_ratio, 4),
    }


def plot_comparison(
    spectrum_a: "Spectrum",
    label_a: str,
    spectrum_b: "Spectrum",
    label_b: str,
    title: str | None = None,
) -> plt.Axes:
    """
    Overlay two processed spectra on a single figure for direct visual comparison.

    Parameters
    ----------
    spectrum_a : first Spectrum (already processed)
    label_a    : legend label for spectrum_a
    spectrum_b : second Spectrum (already processed)
    label_b    : legend label for spectrum_b
    title      : optional figure title (auto-generated if omitted)
    """
    for spectrum, label in ((spectrum_a, label_a), (spectrum_b, label_b)):
        if not spectrum.is_processed:
            raise RuntimeError(
                f"'{label}' must be processed before plotting.  "
                "Call spectrum.process() first."
            )

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(spectrum_a.wavelengths, spectrum_a.reflectance,
            color="saddlebrown", lw=1.5, label=label_a)
    ax.plot(spectrum_b.wavelengths, spectrum_b.reflectance,
            color="forestgreen", lw=1.5, label=label_b)

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Reflectance")
    ax.set_title(title or f"{label_a}  vs  {label_b}")
    ax.legend()
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
    return ax


def plot_difference(
    spectrum_a: "Spectrum",
    label_a: str,
    spectrum_b: "Spectrum",
    label_b: str,
    title: str | None = None,
) -> plt.Axes:
    """
    Plot the per-wavelength reflectance difference (spectrum_a minus spectrum_b).

    A zero line is drawn for reference.  Regions where spectrum_a is higher are
    shaded green; regions where spectrum_b is higher are shaded brown.  Both
    spectra must be on the same 400 – 2 500 nm grid (i.e. both processed).

    Parameters
    ----------
    spectrum_a : first Spectrum (already processed) — the minuend
    label_a    : legend label for spectrum_a
    spectrum_b : second Spectrum (already processed) — the subtrahend
    label_b    : legend label for spectrum_b
    title      : optional figure title
    """
    for spectrum, label in ((spectrum_a, label_a), (spectrum_b, label_b)):
        if not spectrum.is_processed:
            raise RuntimeError(
                f"'{label}' must be processed before plotting.  "
                "Call spectrum.process() first."
            )

    difference = spectrum_a.reflectance - spectrum_b.reflectance
    wavelengths = spectrum_a.wavelengths

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(wavelengths, difference, color="steelblue", lw=1.0)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.fill_between(
        wavelengths, difference, 0,
        where=(difference > 0),
        color="forestgreen", alpha=0.25,
        label=f"{label_a} higher",
    )
    ax.fill_between(
        wavelengths, difference, 0,
        where=(difference < 0),
        color="saddlebrown", alpha=0.25,
        label=f"{label_b} higher",
    )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel(f"Reflectance difference  ({label_a} − {label_b})")
    ax.set_title(title or f"Spectral difference:  {label_a} minus {label_b}")
    ax.legend()
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
    return ax


def plot_index_comparison(
    indices_a: dict,
    label_a: str,
    indices_b: dict,
    label_b: str,
    title: str | None = None,
) -> None:
    """
    Display spectral indices as a grouped bar chart — one panel per index.

    Using one panel per index keeps axes at their natural scales, which is
    especially helpful when bounded indices (NDVI, NDWI ∈ [−1, 1]) and
    unbounded ones (Simple Ratio) appear together.

    Parameters
    ----------
    indices_a : dict returned by compute_indices() for the first spectrum
    label_a   : display name for the first spectrum
    indices_b : dict returned by compute_indices() for the second spectrum
    label_b   : display name for the second spectrum
    title     : optional overall figure title
    """
    index_names  = list(indices_a.keys())
    number_of_indices = len(index_names)

    fig, axes = plt.subplots(1, number_of_indices, figsize=(4.5 * number_of_indices, 5))
    if number_of_indices == 1:
        axes = [axes]

    bar_colors = [("saddlebrown", label_a), ("forestgreen", label_b)]

    for ax, index_name in zip(axes, index_names):
        values = [indices_a[index_name], indices_b[index_name]]
        bars = ax.bar(
            [label_a, label_b],
            values,
            color=["saddlebrown", "forestgreen"],
            alpha=0.85,
            width=0.5,
        )
        ax.set_title(index_name, fontweight="bold")
        ax.set_ylabel("Index value")
        ax.grid(axis="y", alpha=0.3)
        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + abs(bar.get_height()) * 0.04 + 1e-6,
                f"{bar.get_height():.3f}",
                ha="center", va="bottom", fontsize=10,
            )

    fig.suptitle(title or f"Spectral indices:  {label_a}  vs  {label_b}", fontsize=12)
    plt.tight_layout()
    plt.show()


def average_pairs(
    collection: "SpectraCollection",
    groups: list[tuple] | None = None,
    group_size: int = 2,
) -> pd.DataFrame:
    """
    Average defined groups of processed spectra.

    Parameters
    ----------
    collection : SpectraCollection (all spectra must be processed)
    groups     : explicit list of index tuples, e.g. [(0, 1), (2, 3, 4), (5, 7)].
                 Each tuple selects spectra by their **0-based** position in
                 ``collection.spectra``.  Groups may be different sizes and
                 indices may appear in any order.
                 If omitted, consecutive groups of ``group_size`` are used.
    group_size : used only when ``groups`` is None (default 2)

    Returns
    -------
    DataFrame with one row per group (index = "pair_1", "pair_2", …) and
    wavelength columns 400 – 2 500 nm.
    """
    unprocessed = [s for s in collection.spectra if not s.is_processed]
    if unprocessed:
        raise RuntimeError(
            f"{len(unprocessed)} spectra not yet processed.  "
            "Call collection.process() first."
        )

    if groups is None:
        groups = [
            tuple(range(i, min(i + group_size, len(collection.spectra))))
            for i in range(0, len(collection.spectra), group_size)
        ]

    n = len(collection.spectra)
    rows = {}
    for group_number, indices in enumerate(groups, start=1):
        bad = [i for i in indices if i >= n or i < 0]
        if bad:
            names = [s.name for s in collection.spectra]
            raise IndexError(
                f"pair_{group_number} contains out-of-range index/indices {bad}. "
                f"Collection has {n} spectra (indices 0 – {n - 1}).\n"
                f"Available spectra:\n"
                + "\n".join(f"  [{i}] {name}" for i, name in enumerate(names))
            )
        group = [collection.spectra[i] for i in indices]
        averaged_reflectance = np.mean([s.reflectance for s in group], axis=0)
        rows[f"pair_{group_number}"] = averaged_reflectance

    dataframe = pd.DataFrame(rows, index=STANDARD_WAVELENGTHS.astype(int)).T
    dataframe.index.name = "pair"
    return dataframe


def plot_paired_averages(
    collection: "SpectraCollection",
    averaged_df: pd.DataFrame,
    groups: list[tuple] | None = None,
    group_size: int = 2,
    title: str | None = None,
) -> plt.Axes:
    """
    Plot individual scans faded behind their group-average spectra.

    Each colour represents one group.  Individual scans within a group share the
    same colour at low opacity; the bold line is their mean.

    Parameters
    ----------
    collection  : SpectraCollection (all spectra must be processed)
    averaged_df : DataFrame returned by average_pairs()
    groups      : same list of index tuples passed to average_pairs().
                  If omitted, consecutive groups of ``group_size`` are assumed.
    group_size  : used only when ``groups`` is None (default 2)
    title       : optional figure title
    """
    if groups is None:
        groups = [
            tuple(range(i, min(i + group_size, len(collection.spectra))))
            for i in range(0, len(collection.spectra), group_size)
        ]

    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    wavelength_columns = list(averaged_df.columns)
    wavelengths = np.array([int(col) for col in wavelength_columns])

    fig, ax = plt.subplots(figsize=(12, 5))

    for pair_index, (pair_label, row) in enumerate(zip(averaged_df.index, averaged_df.itertuples(index=False))):
        color = color_cycle[pair_index % len(color_cycle)]
        indices = groups[pair_index]
        group = [collection.spectra[i] for i in indices]

        for spectrum in group:
            ax.plot(
                spectrum.wavelengths, spectrum.reflectance,
                color=color, lw=0.7, alpha=0.3,
            )

        scan_names = ", ".join(s.name for s in group)
        ax.plot(
            wavelengths, np.array(list(row)).astype(float),
            color=color, lw=2.0,
            label=f"{pair_label}  [{', '.join(str(i) for i in indices)}]  ({scan_names})",
        )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Reflectance")
    ax.set_title(title or f"Group averages — {collection.name}")
    ax.legend(fontsize="x-small", ncol=1)
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
    return ax


def plot_groups(
    csv_path: str | Path,
    groups: list[tuple],
    averaged_dataframe: pd.DataFrame,
) -> None:
    """
    Plot individual scans (faded) behind their group mean spectra (bold).

    Parameters
    ----------
    csv_path           : path to the *_merged_spectra.csv
    groups             : same list of tuples passed to average_groups()
    averaged_dataframe : the DataFrame returned by average_groups()
    """
    full_dataframe = pd.read_csv(csv_path, index_col=0)
    wavelength_columns = [col for col in full_dataframe.columns if str(col).isdigit()]
    wavelengths = np.array([int(col) for col in wavelength_columns])

    averaged_wavelength_columns = [
        col for col in averaged_dataframe.columns
        if isinstance(col, (int, float)) or (isinstance(col, str) and str(col).isdigit())
    ]
    averaged_wavelengths = np.array([int(col) for col in averaged_wavelength_columns])

    all_scan_numbers = {scan_number for group in groups for scan_number in group}
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fig, ax = plt.subplots(figsize=(12, 5))

    # Individual scans — faded, colored by which group they belong to
    for sample_name in full_dataframe.index:
        try:
            scan_number = int(str(sample_name).replace(".sig", "").split(".")[-1])
        except ValueError:
            continue
        if scan_number not in all_scan_numbers:
            continue
        group_index = next(
            index for index, group in enumerate(groups) if scan_number in group
        )
        color = color_cycle[group_index % len(color_cycle)]
        ax.plot(
            wavelengths,
            full_dataframe.loc[sample_name, wavelength_columns].values.astype(float),
            color=color, alpha=0.25, lw=0.7,
        )

    # Group means — bold, with legend labels
    for group_index, (_, row) in enumerate(averaged_dataframe.iterrows()):
        color = color_cycle[group_index % len(color_cycle)]
        label = f"Group {group_index + 1}  (scans {list(groups[group_index])})"
        ax.plot(
            averaged_wavelengths,
            row[averaged_wavelength_columns].values.astype(float),
            color=color, lw=2.0, label=label,
        )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Reflectance")
    ax.set_title("Individual scans (faded)  vs  group means (bold)")
    ax.legend()
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
