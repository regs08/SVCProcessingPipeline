"""Prefect-based orchestration for SIG processing and resampling."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List

from prefect import flow, get_run_logger, task

from sig_preprocessor.sig_processor import SigFileProcessor


def _collect_summary_rows(
    input_dir: Path,
    output_dir: Path,
    instrument_value: str,
    instrument_name: str,
    correction_type: str,
    end_line_value: str,
) -> Iterable[Dict[str, str]]:
    for output_path in sorted(output_dir.glob("*.sig")):
        yield {
            "input_file": str(input_dir / output_path.name),
            "processed_file": str(output_path),
            "instrument_value": instrument_value,
            "instrument_name": instrument_name,
            "correction_type": correction_type,
            "end_line_value": end_line_value,
        }


def _acquire_logger() -> logging.Logger:
    try:
        return get_run_logger()
    except RuntimeError:
        logger = logging.getLogger("sig_pipeline")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


def _process_sig_files(settings: Dict[str, Path | str], logger: logging.Logger) -> Path | None:
    input_dir = Path(settings["input_dir"])
    output_dir = Path(settings["processed_dir"])
    summary_csv = Path(settings["summary_csv"])
    verbose = bool(settings.get("verbose", False))

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

    if correction_type not in SigFileProcessor.DEFAULT_CORRECTION_TYPES:
        logger.error("Unsupported instrument '%s'", instrument_name)
        return None

    if verbose:
        logger.info("Instrument verified: %s (%s)", instrument_name, instrument_value)
        logger.info("Clearing previous processed SIG outputs")

    overrides = settings.get("end_line_overrides") or {}
    custom_end_line = overrides.get(correction_type)
    default_end_line = SigFileProcessor.DEFAULT_CORRECTION_TYPES.get(correction_type)
    end_line_value = custom_end_line or default_end_line

    if not end_line_value:
        logger.error("No end-line value available for correction type '%s'", correction_type)
        return None

    for path in output_dir.glob("*.sig"):
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Could not remove %s: %s", path, exc)

    if verbose:
        logger.info(
            "Running SigFileProcessor with correction type '%s' (end line %s)",
            correction_type,
            end_line_value,
        )

    if custom_end_line:
        instrument_number = None
        match = re.search(r"(\d{7})", instrument_value)
        if match:
            instrument_number = match.group(1)
        processor = SigFileProcessor(
            correction_value=custom_end_line,
            instrument_number=instrument_number,
        )
    else:
        processor = SigFileProcessor(correction_type=correction_type)

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


def _resample_with_r(
    settings: Dict[str, Path | str],
    summary_csv: Path | None,
    logger: logging.Logger,
) -> Path | None:
    if summary_csv is None:
        logger.error("Skipping resampling because SIG processing did not produce a summary.")
        return None

    merge_script = Path(settings["merge_script"])
    input_dir = Path(settings["processed_dir"])
    output_dir = Path(settings["resampled_dir"])
    output_file = settings["merged_csv_name"]
    verbose = bool(settings.get("verbose", False))
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
    if verbose:
        logger.info("Executing Rscript command")
    subprocess.run(cmd, check=True)

    merged_path = output_dir / output_file
    if merged_path.exists():
        logger.info("Merged spectra available at %s", merged_path.resolve())
        if verbose:
            logger.info("Completed resampling step")
        return merged_path

    logger.warning("Merged spectra file was not created at %s", merged_path)
    return None


@task
def process_sig_files_task(settings: Dict[str, Path | str]) -> Path | None:
    logger = _acquire_logger()
    return _process_sig_files(settings, logger)


@task
def resample_with_r_task(
    settings: Dict[str, Path | str],
    summary_csv: Path | None,
) -> Path | None:
    logger = _acquire_logger()
    return _resample_with_r(settings, summary_csv, logger)


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.expanduser().open() as cfg:
        return json.load(cfg)


def _expand_input_directories(config: Dict[str, Any]) -> List[Path]:
    """
    Resolve the set of SIG input directories to process based on configuration options.

    Supports any of the following config keys (in priority order):
        - "sig_input_dirs": explicit list of directories (list or semicolon-separated string)
        - "sig_input_dir": single directory path
            + if "process_all_subdirs" is truthy, iterate over immediate subdirectories
              that contain at least one `.sig` file

    Returns:
        List[Path]: Concrete directory paths to process.
    """
    explicit_dirs = config.get("sig_input_dirs")
    resolved: List[Path] = []

    if explicit_dirs:
        if isinstance(explicit_dirs, str):
            candidates = [item.strip() for item in explicit_dirs.split(";") if item.strip()]
        else:
            candidates = explicit_dirs
        for entry in candidates:
            resolved.append(Path(entry).expanduser())
        return resolved

    base_dir_str = config.get("sig_input_dir")
    if not base_dir_str:
        raise ValueError("Configuration must provide 'sig_input_dir' or 'sig_input_dirs'.")
    base_dir = Path(base_dir_str).expanduser()

    process_subdirs = bool(config.get("process_all_subdirs"))
    if not process_subdirs:
        return [base_dir]

    if not base_dir.is_dir():
        return [base_dir]

    subdirs = []
    for child in sorted(base_dir.iterdir()):
        if child.is_dir():
            if any(grandchild.suffix.lower() == ".sig" for grandchild in child.glob("*.sig")):
                subdirs.append(child)
    return subdirs or [base_dir]


def _resolve_output_path(base: Path | None, path_value: str) -> Path:
    path_obj = Path(path_value).expanduser()
    if path_obj.is_absolute() or base is None:
        return path_obj
    return base / path_obj


def build_settings(config: Dict[str, Any], verbose: bool) -> Dict[str, Path | str]:
    input_dir = Path(config["sig_input_dir"]).expanduser()
    output_root = Path(config["output_dir"]).expanduser() if config.get("output_dir") else None
    processed_root = _resolve_output_path(output_root, config["processed_dir"])
    resampled_root = _resolve_output_path(output_root, config["resampled_dir"])
    merge_script = Path(config["merge_script"]).expanduser()

    source_name = input_dir.name or "sig_input"
    processed_dir = processed_root / source_name
    resampled_dir = resampled_root / source_name
    summary_csv = processed_dir / f"{source_name}_{config['summary_csv_name']}"
    merged_csv_name = f"{source_name}_{config['merged_csv_name']}"

    return {
        "source_name": source_name,
        "input_dir": input_dir,
        "processed_dir": processed_dir,
        "resampled_dir": resampled_dir,
        "summary_csv": summary_csv,
        "merge_script": merge_script,
        "merged_csv_name": merged_csv_name,
        "output_root": output_root,
        "end_line_overrides": config.get("end_line_overrides", {}),
        "verbose": verbose,
    }


@flow
def sig_pipeline_flow(config: Dict[str, Any], verbose: bool = False):
    settings = build_settings(config, verbose)

    summary_csv = process_sig_files_task(settings)
    merged_csv = resample_with_r_task(settings, summary_csv)

    return {
        "summary_csv": summary_csv,
        "merged_csv": merged_csv,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SIG processing pipeline")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging before and after each processing step",
    )
    parser.add_argument(
        "--config",
        default="config/pipeline_config.json",
        help="Path to the pipeline configuration file",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))
    input_dirs = _expand_input_directories(config)
    overall_results = []

    for input_dir in input_dirs:
        config_for_dir = dict(config)
        config_for_dir["sig_input_dir"] = str(input_dir)
        try:
            results = sig_pipeline_flow(config=config_for_dir, verbose=args.verbose)
        except RuntimeError as exc:
            print(f"Prefect execution failed for {input_dir} ({exc}); falling back to direct function call.")
            logger = _acquire_logger()
            settings = build_settings(config_for_dir, args.verbose)
            summary_csv = _process_sig_files(settings, logger)
            merged_csv = _resample_with_r(settings, summary_csv, logger)
            results = {"summary_csv": summary_csv, "merged_csv": merged_csv}
        overall_results.append((input_dir, results))

    for directory, outputs in overall_results:
        print(f"\nInput directory: {Path(directory).resolve()}")
        for label, path in outputs.items():
            if path:
                print(f"  {label}: {Path(path).resolve()}")
            else:
                print(f"  {label}: not produced")


if __name__ == "__main__":
    main()
