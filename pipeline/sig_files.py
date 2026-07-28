"""Discovery helpers for SVC ``.sig`` files."""

from __future__ import annotations

from pathlib import Path


_TEMPORARY_FILE_PREFIXES = ("~$", "._", ".")


def is_sig_file(path: str | Path) -> bool:
    """Return whether *path* looks like a real SVC file rather than a temp file."""
    candidate = Path(path)
    return (
        candidate.is_file()
        and candidate.suffix.lower() == ".sig"
        and not candidate.name.startswith(_TEMPORARY_FILE_PREFIXES)
    )


def find_sig_files(directory: str | Path) -> list[Path]:
    """Return sorted SVC candidates, excluding common lock/metadata artifacts."""
    return sorted(path for path in Path(directory).glob("*.sig") if is_sig_file(path))
