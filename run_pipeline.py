#!/usr/bin/env python3
"""Command-line entry point for the SIG processing pipeline.

The orchestration logic lives in :mod:`pipeline.cli`; this wrapper stays
intentionally tiny so the entry point is trivial to read and to package later
as a console script. Run it with, e.g.::

    python3 run_pipeline.py config.json
"""

from pipeline.cli import main

if __name__ == "__main__":
    main()
