"""Filesystem scanning helpers for movie files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


def normalize_extensions(exts: Iterable[str]) -> List[str]:
    """Normalize extensions to lowercase dot-prefixed values.

    Args:
        exts: Iterable of extensions to normalize.

    Returns:
        Sorted list of unique normalized extensions.
    """
    out = []
    for e in exts:
        e = e.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        out.append(e)
    return sorted(set(out))


def should_ignore(path: Path, ignore_substrings: List[str]) -> bool:
    """Check whether a path should be ignored based on substrings.

    Args:
        path: Path to evaluate.
        ignore_substrings: Substrings that indicate the file should be ignored.

    Returns:
        True if the file should be ignored.
    """
    name = path.name.lower()
    return any(s.lower() in name for s in ignore_substrings)


def find_movie_files(root: Path, extensions: List[str], ignore_substrings: List[str], max_files: int) -> List[Path]:
    """Find movie files under a root directory.

    Args:
        root: Root directory to scan.
        extensions: Allowed file extensions.
        ignore_substrings: Substrings to skip.
        max_files: Maximum number of files to return (0 for no limit).

    Returns:
        List of movie file paths.
    """
    files: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in extensions:
            continue
        if should_ignore(p, ignore_substrings):
            continue
        files.append(p)
        if max_files and len(files) >= max_files:
            break
    return files
