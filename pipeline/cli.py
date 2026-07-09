"""Command-line interface for the SIG processing pipeline.

This module is thin glue: it parses arguments, configures logging, and wires the
two collaborators together for each input directory —

* :class:`~pipeline.run_config.RunConfig` — loads the run config and builds the
  per-directory settings (*what to run*).
* :class:`~pipeline.runner.Pipeline` — runs the processing + resampling stages
  (*do the work*).

Invoke it as ``svc-pipeline [config]`` after installation.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .run_config import RunConfig
from .runner import Pipeline


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
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Write a starter config/config.json in the current directory and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logger = _configure_logging(args.verbose)

    # Resolve relative config, calibration, and output paths against the current
    # working directory so the installed `svc-pipeline` command works from any
    # directory. Absolute paths in the config are always honoured as-is.
    base_dir = Path.cwd()

    if args.init_config:
        target = RunConfig.write_starter_config(base_dir)
        print(f"Wrote starter config: {target.resolve()}")
        print('Edit "sig_input_dir" to point at your .sig data, then run: svc-pipeline')
        return

    run_config = RunConfig.load(base_dir, str(args.config), logger)
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
