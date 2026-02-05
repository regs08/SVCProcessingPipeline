"""CLI orchestration for SIG processing and resampling.

Step 1: Process raw `.sig` files into cleaned `.sig` files + a summary CSV.
Step 2: Run the R resampling script (`merge_resample_sig.R`) to produce a merged CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sig_preprocessor.sig_processor import SigFileProcessor

BUILTIN_CORRECTION_TYPES = dict(SigFileProcessor.DEFAULT_CORRECTION_TYPES)


@dataclass(frozen=True)
class PipelineSettings:
    source_name: str
    input_dir: Path
    processed_dir: Path
    resampled_dir: Path
    summary_csv: Path
    merge_script: Path
    merged_csv_name: str
    end_line_overrides: dict[str, str]
    verbose: bool


def _collect_summary_rows(
    input_dir: Path,
    output_dir: Path,
    instrument_value: str,
    instrument_name: str,
    correction_type: str,
    end_line_value: str,
) -> Iterable[dict[str, str]]:
    for output_path in sorted(output_dir.glob("*.sig")):
        yield {
            "input_file": str(input_dir / output_path.name),
            "processed_file": str(output_path),
            "instrument_value": instrument_value,
            "instrument_name": instrument_name,
            "correction_type": correction_type,
            "end_line_value": end_line_value,
        }


def _configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    return logging.getLogger("sig_pipeline")


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().open() as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    return data


def _resolve_under(base: Path, value: str) -> Path:
    path_obj = Path(value).expanduser()
    if path_obj.is_absolute():
        return path_obj
    return base / path_obj


def _load_project_correction_types(
    config: dict[str, Any],
    input_dir: Path,
    repo_root: Path,
    logger: logging.Logger,
) -> None:
    """
    Load DEFAULT_CORRECTION_TYPES for this run.

    Priority:
      1) config["correction_types_file"] (if provided)
      2) config/calibrations/<project_name>.json (if present)

    Always resets to built-in defaults first to avoid cross-run bleed.
    """
    SigFileProcessor.DEFAULT_CORRECTION_TYPES = dict(BUILTIN_CORRECTION_TYPES)

    explicit = config.get("correction_types_file")
    if explicit:
        correction_path = _resolve_under(repo_root, str(explicit))
        SigFileProcessor.load_default_correction_types(correction_path)
        logger.info("Loaded correction types from %s", correction_path.resolve())
        return

    inferred = repo_root / "config" / "calibrations" / f"{input_dir.name}.json"
    if inferred.exists():
        SigFileProcessor.load_default_correction_types(inferred)
        logger.info("Loaded correction types from %s", inferred.resolve())
    else:
        logger.debug("No calibration file found at %s; using built-in defaults.", inferred)


def _expand_input_directories(config: dict[str, Any]) -> list[Path]:
    explicit_dirs = config.get("sig_input_dirs")
    if explicit_dirs:
        if isinstance(explicit_dirs, str):
            candidates = [item.strip() for item in explicit_dirs.split(";") if item.strip()]
        else:
            candidates = list(explicit_dirs)
        return [Path(entry).expanduser() for entry in candidates]

    base_dir_str = config.get("sig_input_dir")
    if not base_dir_str:
        raise ValueError("Configuration must provide 'sig_input_dir' or 'sig_input_dirs'.")
    base_dir = Path(str(base_dir_str)).expanduser()

    if not bool(config.get("process_all_subdirs")):
        return [base_dir]

    if not base_dir.is_dir():
        return [base_dir]

    subdirs: list[Path] = []
    for child in sorted(base_dir.iterdir()):
        if child.is_dir() and any(grandchild.suffix.lower() == ".sig" for grandchild in child.glob("*.sig")):
            subdirs.append(child)
    return subdirs or [base_dir]


def build_settings(config: dict[str, Any], *, repo_root: Path, verbose: bool) -> PipelineSettings:
    input_dir = Path(str(config["sig_input_dir"])).expanduser()
    source_name = input_dir.name or "sig_input"

    output_root: Path | None = None
    if config.get("output_dir"):
        output_root = _resolve_under(repo_root, str(config["output_dir"]))

    base_output = output_root or repo_root
    processed_root = _resolve_under(base_output, str(config["processed_dir"]))
    resampled_root = _resolve_under(base_output, str(config["resampled_dir"]))
    merge_script = _resolve_under(repo_root, str(config["merge_script"]))

    processed_dir = processed_root / source_name
    resampled_dir = resampled_root / source_name
    summary_csv = processed_dir / f"{source_name}_{config['summary_csv_name']}"
    merged_csv_name = f"{source_name}_{config['merged_csv_name']}"

    overrides_raw = config.get("end_line_overrides") or {}
    end_line_overrides = {
        str(key).strip().lower(): str(value).strip() for key, value in overrides_raw.items() if key is not None
    }

    return PipelineSettings(
        source_name=source_name,
        input_dir=input_dir,
        processed_dir=processed_dir,
        resampled_dir=resampled_dir,
        summary_csv=summary_csv,
        merge_script=merge_script,
        merged_csv_name=merged_csv_name,
        end_line_overrides=end_line_overrides,
        verbose=verbose,
    )


def process_sig_files(settings: PipelineSettings, logger: logging.Logger) -> Path | None:
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

    inspection_processor = SigFileProcessor(correction_type="silver")
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
    correction_type = instrument_name.lower()

    end_line_value = settings.end_line_overrides.get(correction_type) or SigFileProcessor.DEFAULT_CORRECTION_TYPES.get(
        correction_type
    )
    if not end_line_value:
        logger.error("No end-line value available for correction type '%s'", correction_type)
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

    processor = SigFileProcessor(correction_value=end_line_value)
    processor.process_sig_files(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        verbose=False,
    )

    if verbose:
        logger.info("Building processed SIG summary")

    rows = list(
        _collect_summary_rows(
            input_dir,
            output_dir,
            instrument_value,
            instrument_name,
            correction_type,
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


def resample_with_r(
    settings: PipelineSettings,
    summary_csv: Path | None,
    logger: logging.Logger,
) -> Path | None:
    if summary_csv is None:
        logger.error("Skipping resampling because SIG processing did not produce a summary.")
        return None

    merge_script = settings.merge_script
    input_dir = settings.processed_dir
    output_dir = settings.resampled_dir
    output_file = settings.merged_csv_name
    verbose = settings.verbose
    output_dir.mkdir(parents=True, exist_ok=True)

    if not merge_script.exists():
        logger.error("Merge script not found: %s", merge_script)
        return None

    if verbose:
        logger.info("Preparing to run merge script %s", merge_script.resolve())
        logger.info("Input directory: %s", input_dir.resolve())

    cmd = [
        "Rscript",
        str(merge_script),
        str(input_dir),
        str(output_dir),
        output_file,
    ]

    logger.info("Running R merge script: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

    merged_path = output_dir / output_file
    if merged_path.exists():
        logger.info("Merged spectra available at %s", merged_path.resolve())
        return merged_path

    logger.warning("Merged spectra file was not created at %s", merged_path)
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SIG processing pipeline")
    parser.add_argument(
        "--config",
        default="config/weekly_data.json",
        help="Path to the pipeline configuration file",
    )
    parser.add_argument(
        "--input-dir",
        help="Override the config's sig_input_dir and process only this directory.",
    )
    parser.add_argument(
        "--step",
        choices=["1", "2", "all"],
        default="all",
        help="Which step to run: 1=process+summary CSV, 2=R resampling only, all=run both steps.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging before and after each processing step",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parent
    logger = _configure_logging(args.verbose)

    config_path = _resolve_under(repo_root, str(args.config))
    config = _load_json(config_path)

    if args.input_dir:
        input_dirs = [Path(str(args.input_dir)).expanduser()]
    else:
        input_dirs = _expand_input_directories(config)

    overall_results: list[tuple[Path, dict[str, Path | None]]] = []

    for input_dir in input_dirs:
        config_for_dir = dict(config)
        config_for_dir["sig_input_dir"] = str(input_dir)

        _load_project_correction_types(config_for_dir, input_dir, repo_root, logger)
        settings = build_settings(config_for_dir, repo_root=repo_root, verbose=args.verbose)

        summary_csv: Path | None
        if args.step in {"1", "all"}:
            summary_csv = process_sig_files(settings, logger)
        else:
            summary_csv = settings.summary_csv if settings.summary_csv.exists() else None
            if summary_csv is None:
                logger.error("Summary CSV not found at %s (run --step 1 first).", settings.summary_csv.resolve())

        merged_csv: Path | None = None
        if args.step in {"2", "all"}:
            merged_csv = resample_with_r(settings, summary_csv, logger)

        overall_results.append((input_dir, {"summary_csv": summary_csv, "merged_csv": merged_csv}))

    for directory, outputs in overall_results:
        print(f"\nInput directory: {directory.resolve()}")
        for label, path in outputs.items():
            if path:
                print(f"  {label}: {Path(path).resolve()}")
            else:
                print(f"  {label}: not produced")


if __name__ == "__main__":
    main()
