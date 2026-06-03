"""Orchestration for SIG processing and resampling.

This module is the implementation behind the ``run_pipeline.py`` entry point:

Step 1: Process raw ``.sig`` files into cleaned ``.sig`` files + a summary CSV.
Step 2: Run the pure-Python resampler (``pipeline/resampler.py``) to produce a merged CSV.

Invoke it via ``python3 run_pipeline.py [config]`` (or ``python3 -m pipeline.cli``).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .sig_processor import SigFileProcessor
from .resampler import resample_spectra

# cli.py lives at <repo>/pipeline/cli.py, so the repo root is two levels up.
_REPO_ROOT = Path(__file__).resolve().parent.parent

BUILTIN_SENSOR_CALIBRATIONS = dict(SigFileProcessor.DEFAULT_CORRECTION_TYPES)
BUILTIN_INSTRUMENT_NUMBERS  = dict(SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS)

# Parity-verified defaults — deviating from these invalidates the R/spectrolab parity claim.
_PARITY_DEFAULTS: dict[str, object] = {
    "band_min":          400,
    "band_max":          2500,
    "resample_fwhm_nm":  10.0,
    "splice_interp_wvl": [5.0, 2.0],
    "fixed_sensor":      2,
}


@dataclass(frozen=True)
class PipelineSettings:
    source_name: str
    input_dir: Path
    processed_dir: Path
    resampled_dir: Path
    summary_csv: Path
    merged_csv_name: str
    end_line_overrides: dict[str, str]
    verbose: bool
    processing_params: dict


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


def _configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    return logging.getLogger("sig_pipeline")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.expanduser().open() as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise SystemExit(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a JSON object: {path}")
    return data


def _resolve_under(base: Path, value: str) -> Path:
    path_obj = Path(value).expanduser()
    if path_obj.is_absolute():
        return path_obj
    return base / path_obj


def _resolve_config(repo_root: Path, value: str) -> Path:
    """Resolve a run-config argument with friendly fallbacks.

    Tries, in order: the path as given (relative to repo root), the same name
    under config/, and the same again with a .json suffix appended.
    """
    raw = Path(value).expanduser()
    if raw.is_absolute():
        candidates = [raw]
    else:
        names = [raw]
        if raw.suffix == "":
            names.append(raw.with_suffix(".json"))
        candidates = []
        for name in names:
            candidates.append(repo_root / name)             # e.g. <repo>/config.json
            candidates.append(repo_root / "config" / name)  # e.g. <repo>/config/config.json
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    available = sorted(p.name for p in (repo_root / "config").glob("*.json"))
    raise SystemExit(
        f"Config not found: '{value}'.\n"
        f"  Tried: {', '.join(str(c) for c in candidates)}\n"
        f"  Available in config/: {', '.join(available) or '(none)'}\n"
        f"  Usage: python3 run_pipeline.py [CONFIG] [--step ...] [--verbose]"
    )


def _load_instrument_block(
    config: dict[str, Any],
    logger: logging.Logger,
) -> bool:
    """Apply the 'instrument' block from the run config (highest-priority calibration source).

    Format:
        "instrument": {
            "bronze": {"end_line": "2520.4", "serial": "2212118"},
            "silver": {"end_line": "2517.9", "serial": "1202103"}
        }

    Returns True if the block was present and applied.
    """
    block = config.get("instrument")
    if not block:
        return False

    end_lines: dict[str, str] = {}
    serials: dict[str, str] = {}
    for sensor_type, values in block.items():
        key = str(sensor_type).strip().lower()
        if isinstance(values, dict):
            if "end_line" in values:
                end_lines[key] = str(values["end_line"]).strip()
            if "serial" in values:
                serials[key] = str(values["serial"]).strip()
        else:
            # Allow flat {"bronze": "2520.4"} as a shorthand
            end_lines[key] = str(values).strip()

    if end_lines:
        SigFileProcessor.DEFAULT_CORRECTION_TYPES = {
            **dict(BUILTIN_SENSOR_CALIBRATIONS),
            **end_lines,
        }
        logger.info("Instrument end-lines from config: %s", end_lines)

    if serials:
        SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS = {
            **dict(BUILTIN_INSTRUMENT_NUMBERS),
            **serials,
        }
        logger.info("Instrument serials from config: %s", serials)

    return True


def _load_sensor_calibrations(
    config: dict[str, Any],
    input_dir: Path,
    repo_root: Path,
    logger: logging.Logger,
) -> None:
    SigFileProcessor.DEFAULT_CORRECTION_TYPES = dict(BUILTIN_SENSOR_CALIBRATIONS)
    SigFileProcessor.DEFAULT_INSTRUMENT_NUMBERS = dict(BUILTIN_INSTRUMENT_NUMBERS)

    # 1. instrument block in run config (highest priority)
    if _load_instrument_block(config, logger):
        return

    # 2. explicit sensor_calibration_file in run config
    explicit = config.get("sensor_calibration_file") or config.get("correction_types_file")
    if explicit:
        sensor_calibration_path = _resolve_under(repo_root, str(explicit))
        SigFileProcessor.load_default_correction_types(sensor_calibration_path)
        logger.info("Loaded sensor calibration from %s", sensor_calibration_path.resolve())
        return

    # 3. auto-inferred calibrations/<input_dir_name>.json
    inferred = repo_root / "config" / "calibrations" / f"{input_dir.name}.json"
    if inferred.exists():
        SigFileProcessor.load_default_correction_types(inferred)
        logger.info("Loaded sensor calibration from %s", inferred.resolve())
    else:
        logger.debug("No sensor calibration file found at %s; using built-in defaults.", inferred)


def _load_processing_params(
    config: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Read the optional 'processing' block and warn on any non-parity values."""
    block = config.get("processing") or {}
    params: dict[str, Any] = {}

    for key, default in _PARITY_DEFAULTS.items():
        if key in block:
            value = block[key]
            # Normalise list → tuple for interp_wvl
            if isinstance(value, list):
                value = tuple(value)
            params[key] = value
            default_cmp = tuple(default) if isinstance(default, list) else default
            if value != default_cmp:
                logger.warning(
                    "processing.%s = %s differs from parity-verified default %s — "
                    "R/spectrolab parity is no longer guaranteed.",
                    key, value, default,
                )
        else:
            params[key] = tuple(default) if isinstance(default, list) else default

    return params


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


def build_settings(
    config: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool,
    processing_params: dict | None = None,
) -> PipelineSettings:
    input_dir = Path(str(config["sig_input_dir"])).expanduser()
    source_name = input_dir.name or "sig_input"

    output_root: Path | None = None
    if config.get("output_dir"):
        output_root = _resolve_under(repo_root, str(config["output_dir"]))

    base_output = output_root or repo_root
    processed_root = _resolve_under(base_output, str(config["processed_dir"]))
    resampled_root = _resolve_under(base_output, str(config["resampled_dir"]))

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
        merged_csv_name=merged_csv_name,
        end_line_overrides=end_line_overrides,
        verbose=verbose,
        processing_params=processing_params or {},
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
    sensor_type = instrument_name.lower()

    end_line_value = settings.end_line_overrides.get(sensor_type) or SigFileProcessor.DEFAULT_CORRECTION_TYPES.get(
        sensor_type
    )
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


def resample_with_python(
    settings: PipelineSettings,
    summary_csv: Path | None,
    logger: logging.Logger,
) -> Path | None:
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
    p = settings.processing_params
    merged_path = resample_spectra(
        input_dir, output_dir, output_file,
        band_min=p.get("band_min", 400),
        band_max=p.get("band_max", 2500),
        fwhm_nm=p.get("resample_fwhm_nm", 10.0),
        fixed_sensor=p.get("fixed_sensor", 2),
        interp_wvl=p.get("splice_interp_wvl", (5.0, 2.0)),
    )

    if merged_path.exists():
        logger.info("Merged spectra available at %s", merged_path.resolve())
        return merged_path

    logger.warning("Merged spectra file was not created at %s", merged_path)
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SIG processing pipeline")
    parser.add_argument(
        "config",
        nargs="?",
        default="config.json",
        help="Run-config JSON. Bare names resolve under config/ (default: config.json).",
    )
    # Deprecated alias — keep for one release so existing scripts/cron don't break.
    parser.add_argument("--config", dest="config_flag", help=argparse.SUPPRESS)
    parser.add_argument(
        "--input-dir",
        help="Override the config's sig_input_dir and process only this directory.",
    )
    parser.add_argument(
        "--step",
        choices=["1", "2", "all"],
        default="all",
        help="Which step to run: 1=process+summary CSV, 2=Python resampling only, all=run both steps.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging before and after each processing step",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = _REPO_ROOT
    logger = _configure_logging(args.verbose)

    config_arg = args.config
    if getattr(args, "config_flag", None):
        logger.warning(
            "--config is deprecated; pass the config as a positional argument: "
            "python3 run_pipeline.py %s",
            args.config_flag,
        )
        config_arg = args.config_flag

    config_path = _resolve_config(repo_root, str(config_arg))
    config = _load_json(config_path)
    logger.info("Using config: %s", config_path)

    PLACEHOLDER = "<PATH_TO_SIG_INPUT_ROOT>"
    sig_input_dirs = config.get("sig_input_dirs") or []
    if isinstance(sig_input_dirs, str):
        sig_input_dirs = [sig_input_dirs]
    raw_inputs = [config.get("sig_input_dir"), *sig_input_dirs]
    if not args.input_dir and any(value == PLACEHOLDER for value in raw_inputs if value):
        raise SystemExit(
            f'{config_path} still contains the placeholder "{PLACEHOLDER}".\n'
            f'  Edit "sig_input_dir" to point at your .sig data directory, '
            f"or pass --input-dir <path>."
        )

    if args.input_dir:
        input_dirs = [Path(str(args.input_dir)).expanduser()]
    else:
        input_dirs = _expand_input_directories(config)

    overall_results: list[tuple[Path, dict[str, Path | None]]] = []

    processing_params = _load_processing_params(config, logger)

    for input_dir in input_dirs:
        config_for_dir = dict(config)
        config_for_dir["sig_input_dir"] = str(input_dir)

        _load_sensor_calibrations(config_for_dir, input_dir, repo_root, logger)
        settings = build_settings(
            config_for_dir,
            repo_root=repo_root,
            verbose=args.verbose,
            processing_params=processing_params,
        )

        summary_csv: Path | None
        if args.step in {"1", "all"}:
            summary_csv = process_sig_files(settings, logger)
        else:
            summary_csv = settings.summary_csv if settings.summary_csv.exists() else None
            if summary_csv is None:
                logger.error("Summary CSV not found at %s (run --step 1 first).", settings.summary_csv.resolve())

        merged_csv: Path | None = None
        if args.step in {"2", "all"}:
            merged_csv = resample_with_python(settings, summary_csv, logger)

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
