"""File selection helpers for run/inspect."""

from __future__ import annotations

from pathlib import Path

from core.services.run_artifacts import load_failed_from_manifest, manifest_path_for_rerun
from core.files.scanner import find_movie_files


def select_files(
    rerun_failed: Path | None,
    file_path: Path | None,
    root: Path | None,
    exts: list[str],
    ignore_substrings: list[str],
    max_files: int,
    only_exts: list[str],
) -> list[Path] | None:
    """Select files based on CLI options and scan rules."""
    if rerun_failed:
        manifest_path = manifest_path_for_rerun(rerun_failed)
        files = load_failed_from_manifest(manifest_path)
        if not files:
            print("No failed files found in manifest.")
            return []
    elif file_path:
        files = [file_path]
    else:
        if not root:
            print("No root directory configured.")
            return None
        files = find_movie_files(root, exts, ignore_substrings, max_files)

    if only_exts:
        files = [path for path in files if path.suffix.lower() in only_exts]
    return files
