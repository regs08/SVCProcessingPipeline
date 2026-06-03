"""Command-line interface for the SIG processing pipeline.

This module is thin glue: it parses arguments, configures logging, and wires the
two collaborators together for each input directory —

* :class:`~pipeline.run_config.RunConfig` — loads the run config and builds the
  per-directory settings (*what to run*).
* :class:`~pipeline.runner.Pipeline` — runs the processing + resampling stages
  (*do the work*).

Invoke it via ``python3 run_pipeline.py [config]`` (or ``python3 -m pipeline.cli``).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .run_config import RunConfig
from .runner import Pipeline

# cli.py lives at <repo>/pipeline/cli.py, so the repo root is two levels up.
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    return logging.getLogger("sig_pipeline")


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
    logger = _configure_logging(args.verbose)

    config_arg = args.config
    if getattr(args, "config_flag", None):
        logger.warning(
            "--config is deprecated; pass the config as a positional argument: "
            "python3 run_pipeline.py %s",
            args.config_flag,
        )
        config_arg = args.config_flag

    run_config = RunConfig.load(_REPO_ROOT, str(config_arg), logger)
    run_config.ensure_no_placeholder(args.input_dir)

    if args.input_dir:
        input_dirs = [Path(str(args.input_dir)).expanduser()]
    else:
        input_dirs = run_config.input_directories()

    # Resolve the processing block once, up front: emits a one-time parity
    # warning for any non-default value before the per-directory work begins.
    run_config.processing_params()

    overall_results: list[tuple[Path, dict[str, Path | None]]] = []
    for input_dir in input_dirs:
        run_config.apply_sensor_calibrations(input_dir)
        settings = run_config.settings_for(input_dir, verbose=args.verbose)
        results = Pipeline(settings, logger).run(args.step)
        overall_results.append((input_dir, results))

    for directory, outputs in overall_results:
        print(f"\nInput directory: {directory.resolve()}")
        for label, path in outputs.items():
            if path:
                print(f"  {label}: {Path(path).resolve()}")
            else:
                print(f"  {label}: not produced")


if __name__ == "__main__":
    main()
