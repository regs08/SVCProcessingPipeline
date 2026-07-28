#!/usr/bin/env python3
"""Prepare external demo data for the SVC pipeline notebook."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "notebooks" / "pipeline_demo" / "demo_data_manifest.json"
DEFAULT_TARGET = REPO_ROOT / "notebooks" / "pipeline_demo" / "demo_data" / "spectra"


class DemoDataError(RuntimeError):
    """Raised when demo data cannot be prepared or verified."""


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and minimally validate the demo-data manifest."""
    with path.open() as handle:
        manifest = json.load(handle)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise DemoDataError(f"Manifest contains no files: {path}")
    return manifest


def file_sha256(path: Path) -> str:
    """Return the SHA256 checksum for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_files(target_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Return verification errors for files in target_dir."""
    errors: list[str] = []
    for item in manifest["files"]:
        path = target_dir / item["name"]
        if not path.exists():
            errors.append(f"missing: {path}")
            continue
        expected_size = int(item["size_bytes"])
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            errors.append(f"size mismatch: {path.name} expected {expected_size}, got {actual_size}")
        expected_sha = str(item["sha256"])
        actual_sha = file_sha256(path)
        if actual_sha != expected_sha:
            errors.append(f"sha256 mismatch: {path.name} expected {expected_sha}, got {actual_sha}")
    return errors


def copy_manifest_files(source_dir: Path, target_dir: Path, manifest: dict[str, Any]) -> None:
    """Copy the manifest-listed .sig files from source_dir to target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    for item in manifest["files"]:
        source = source_dir / item["name"]
        if not source.exists():
            missing.append(str(source))
            continue
        shutil.copy2(source, target_dir / item["name"])
    if missing:
        raise DemoDataError("Source directory is missing manifest files:\n" + "\n".join(missing))


def extract_archive(archive_path: Path, destination: Path) -> None:
    """Extract a zip or tar archive into destination."""
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)
        return
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as archive:
            archive.extractall(destination)
        return
    raise DemoDataError(f"Unsupported archive format: {archive_path}")


def copy_from_extracted_archive(extract_dir: Path, target_dir: Path, manifest: dict[str, Any]) -> None:
    """Find manifest-listed files anywhere under extract_dir and copy them to target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []
    for item in manifest["files"]:
        matches = sorted(extract_dir.rglob(item["name"]))
        if not matches:
            missing.append(item["name"])
            continue
        shutil.copy2(matches[0], target_dir / item["name"])
    if missing:
        raise DemoDataError("Archive is missing manifest files:\n" + "\n".join(missing))


def download_to_temp(url: str, temp_dir: Path) -> Path:
    """Download url into temp_dir and return the archive path."""
    suffix = Path(url.split("?", 1)[0]).suffix or ".archive"
    target = temp_dir / f"demo_data{suffix}"
    urllib.request.urlretrieve(url, target)
    return target


def prepare_from_archive(
    *,
    archive_path: Path | None,
    download_url: str | None,
    target_dir: Path,
    manifest: dict[str, Any],
) -> None:
    """Prepare data from a local archive or a downloadable external artifact."""
    artifact_url = download_url or manifest.get("artifact_url")
    with tempfile.TemporaryDirectory(prefix="svc_demo_data_") as temp_name:
        temp_dir = Path(temp_name)
        archive = archive_path
        if archive is None:
            if not artifact_url:
                raise DemoDataError(
                    "No artifact URL is recorded in the manifest. "
                    "Provide --source-dir, --archive, or --download-url."
                )
            archive = download_to_temp(str(artifact_url), temp_dir)
        extract_dir = temp_dir / "extract"
        extract_archive(archive, extract_dir)
        copy_from_extracted_archive(extract_dir, target_dir, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy or verify external .sig demo data for "
            "notebooks/pipeline_demo/pipeline_demo_notebook.ipynb."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--archive", type=Path, help="Local zip/tar artifact containing the .sig files.")
    parser.add_argument("--download-url", help="External artifact URL. Overrides manifest artifact_url.")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
        target_dir = args.target_dir.expanduser()
        if args.verify_only:
            pass
        elif args.source_dir:
            copy_manifest_files(args.source_dir.expanduser(), target_dir, manifest)
        elif args.archive or args.download_url or manifest.get("artifact_url"):
            prepare_from_archive(
                archive_path=args.archive.expanduser() if args.archive else None,
                download_url=args.download_url,
                target_dir=target_dir,
                manifest=manifest,
            )
        errors = verify_files(target_dir, manifest)
    except DemoDataError as exc:
        print(f"Demo data preparation failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Demo data preparation failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Demo data verification failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print(
            "Run scripts/prepare_demo_data.py with --source-dir or publish/fetch the external artifact.",
            file=sys.stderr,
        )
        return 1

    print(f"Demo data verified: {len(manifest['files'])} files in {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
