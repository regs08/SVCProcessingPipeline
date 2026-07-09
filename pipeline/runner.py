"""Execution of the three SIG processing stages.

:class:`Pipeline` runs, for a single resolved
:class:`~pipeline.run_config.PipelineSettings`:

* Stage 1 (:meth:`Pipeline.process_sig_files`) — truncate raw ``.sig`` files at
  the calibration end-line and write a per-run summary CSV.
* Stage 2 (:meth:`Pipeline.resample`) — run the pure-Python resampler over the
  processed files.
* Stage 3 (:meth:`Pipeline.group_and_average`) — optional; only runs when the
  config supplies a ``groups_csv``. Groups repeat scans of the same sample and
  averages them into one spectrum per group.

Config loading that produces the ``PipelineSettings`` lives in
``pipeline/run_config.py``; the CLI that wires them together lives in
``pipeline/cli.py``.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from .processor import GroupSpec, SigSpectraAverager
from .resampler import resample_spectra
from .run_config import PipelineSettings
from .sig_processor import SigFileProcessor


class Pipeline:
    """Runs the processing + resampling stages for one input directory."""

    def __init__(self, settings: PipelineSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger

    # ── public entry point ───────────────────────────────────────────────────

    def run(self, step: str) -> dict[str, Path | None]:
        """Run the requested step(s) and report the produced artifacts.

        ``step``: ``"1"`` = Stage 1 only, ``"2"`` = Stage 2 only (Stage 1 must
        have run previously), ``"3"`` = Stage 3 only (Stage 2 must have run
        previously; requires ``groups_csv`` to be configured), ``"all"`` = every
        stage that's configured to run (Stage 3 only if ``groups_csv`` is set).
        """
        summary_csv: Path | None = None
        if step in {"1", "all"}:
            summary_csv = self.process_sig_files()
        elif step == "2":
            summary_csv = self.settings.summary_csv if self.settings.summary_csv.exists() else None
            if summary_csv is None:
                self.logger.error(
                    "Summary CSV not found at %s (run --step 1 first).",
                    self.settings.summary_csv.resolve(),
                )

        merged_csv: Path | None = None
        if step in {"2", "all"}:
            merged_csv = self.resample(summary_csv)
        elif step == "3":
            merged_path = self.settings.resampled_dir / self.settings.merged_csv_name
            merged_csv = merged_path if merged_path.exists() else None
            if merged_csv is None:
                self.logger.error("Merged CSV not found at %s (run --step 2 first).", merged_path.resolve())

        grouped_csv: Path | None = None
        if step in {"3", "all"} and self.settings.groups_csv is not None:
            grouped_csv = self.group_and_average(merged_csv)

        return {"summary_csv": summary_csv, "merged_csv": merged_csv, "grouped_csv": grouped_csv}

    # ── Stage 1: process raw .sig files ──────────────────────────────────────

    def process_sig_files(self) -> Path | None:
        settings = self.settings
        logger = self.logger
        input_dir = settings.input_dir
        output_dir = settings.processed_dir
        summary_csv = settings.summary_csv
        verbose = settings.verbose

        output_dir.mkdir(parents=True, exist_ok=True)
        if not input_dir.exists():
            logger.error("Input directory missing: %s", input_dir.resolve())
            return None

        if verbose:
            logger.info("Starting SIG processing: %s -> %s", input_dir.resolve(), output_dir.resolve())
            logger.info("Checking instrument consistency")

        inspection_processor = SigFileProcessor(
            correction_type="silver",
            correction_types=settings.correction_types,
            instrument_numbers=settings.instrument_numbers,
            logger=logger,
        )
        consistency = inspection_processor.check_instrument_consistency(str(input_dir))

        for warning in consistency.get("warnings", []):
            logger.warning("%s", warning)

        if consistency.get("total_files", 0) == 0:
            logger.warning("No SIG files found in %s", input_dir.resolve())
            return None

        if not consistency.get("consistent", False):
            logger.error("Instrument mismatch detected; aborting processing.")
            return None

        instrument_name = str(consistency.get("instrument_name") or "")
        instrument_value = str(consistency.get("instrument") or "")
        sensor_type = instrument_name.lower()

        end_line_value = settings.end_line_overrides.get(sensor_type) or settings.correction_types.get(sensor_type)
        if not end_line_value:
            logger.error("No end-line value available for sensor type '%s'", sensor_type)
            return None

        if verbose:
            logger.info("Instrument verified: %s (%s)", instrument_name, instrument_value)
            logger.info("Clearing previous processed SIG outputs")

        for path in output_dir.glob("*.sig"):
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("Could not remove %s: %s", path, exc)

        if verbose:
            logger.info("Running SigFileProcessor (end line %s)", end_line_value)

        processor = SigFileProcessor(correction_value=end_line_value, logger=logger)
        processor.process_sig_files(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            verbose=False,
        )

        if verbose:
            logger.info("Building processed SIG summary")

        rows = list(
            self._collect_summary_rows(
                input_dir,
                output_dir,
                instrument_value,
                instrument_name,
                sensor_type,
                end_line_value,
            )
        )
        if not rows:
            logger.warning("No processed SIG files were produced.")
            return None

        summary_csv.parent.mkdir(parents=True, exist_ok=True)

        if verbose:
            logger.info("Writing summary CSV to %s", summary_csv.resolve())

        with summary_csv.open("w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Processed SIG summary written to %s", summary_csv.resolve())
        if verbose:
            logger.info("Completed SIG processing")
        return summary_csv

    # ── Stage 2: resample ────────────────────────────────────────────────────

    def resample(self, summary_csv: Path | None) -> Path | None:
        settings = self.settings
        logger = self.logger
        if summary_csv is None:
            logger.error("Skipping resampling because SIG processing did not produce a summary.")
            return None

        input_dir = settings.processed_dir
        output_dir = settings.resampled_dir
        output_file = settings.merged_csv_name
        verbose = settings.verbose

        output_dir.mkdir(parents=True, exist_ok=True)

        if verbose:
            logger.info("Starting Python resampler on %s", input_dir.resolve())

        logger.info("Running Python resampler: %s -> %s/%s", input_dir, output_dir, output_file)
        # Every key is guaranteed present by RunConfig.processing_params(); no fallbacks needed.
        params = settings.processing_params
        merged_path = resample_spectra(
            input_dir, output_dir, output_file,
            band_min=params["band_min"],
            band_max=params["band_max"],
            fwhm_nm=params["resample_fwhm_nm"],
            fixed_sensor=params["fixed_sensor"],
            interp_wvl=params["splice_interp_wvl"],
        )

        if merged_path.exists():
            logger.info("Merged spectra available at %s", merged_path.resolve())
            return merged_path

        logger.warning("Merged spectra file was not created at %s", merged_path)
        return None

    # ── Stage 3: group & average (optional) ──────────────────────────────────

    def group_and_average(self, merged_csv: Path | None) -> Path | None:
        """Average repeat scans of the same sample into one spectrum per group.

        Requires ``settings.groups_csv`` (checked by the caller) and a merged
        CSV from Stage 2. Groups are read via :meth:`GroupSpec.from_csv`
        (``scans``/``scan_id`` + ``name`` columns) and applied with
        :class:`SigSpectraAverager`.
        """
        settings = self.settings
        logger = self.logger
        if merged_csv is None:
            logger.error("Skipping grouping because no merged CSV is available.")
            return None

        groups_csv = settings.groups_csv
        if groups_csv is None or not groups_csv.exists():
            logger.error("Groups CSV not found: %s", groups_csv.resolve() if groups_csv else groups_csv)
            return None

        groups = GroupSpec.from_csv(groups_csv)
        if not groups:
            logger.warning("No groups found in %s; nothing to average.", groups_csv.resolve())
            return None

        if settings.verbose:
            logger.info("Grouping %s using %s (%s)", merged_csv, groups_csv.resolve(), settings.group_agg_method)

        averager = SigSpectraAverager.from_csv(merged_csv)
        grouped_df = averager.aggregate(groups, method=settings.group_agg_method)

        output_path = settings.resampled_dir / settings.grouped_csv_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        grouped_df.to_csv(output_path, index=False)
        logger.info("Grouped/averaged spectra written to %s", output_path.resolve())
        return output_path

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _collect_summary_rows(
        input_dir: Path,
        output_dir: Path,
        instrument_value: str,
        instrument_name: str,
        sensor_type: str,
        end_line_value: str,
    ) -> Iterable[dict[str, str]]:
        for output_path in sorted(output_dir.glob("*.sig")):
            yield {
                "input_file": str(input_dir / output_path.name),
                "processed_file": str(output_path),
                "instrument_value": instrument_value,
                "instrument_name": instrument_name,
                "correction_type": sensor_type,
                "end_line_value": end_line_value,
            }
