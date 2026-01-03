"""Write pipeline helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict


def has_sufficient_backup_space(path: Path, required_bytes: int) -> bool:
    """Return True if there is enough free disk space for a backup."""
    usage = shutil.disk_usage(path)
    return usage.free >= required_bytes


def filter_existing_tags(
    tags_to_write: Dict[str, str],
    existing_tags: Dict[str, str],
) -> tuple[Dict[str, str], list[str]]:
    """Drop tags that already exist and return skipped keys."""
    filtered: Dict[str, str] = {}
    skipped: list[str] = []
    for key, value in tags_to_write.items():
        existing_value = existing_tags.get(str(key).lower())
        if existing_value is not None and str(existing_value).strip():
            skipped.append(key)
            continue
        filtered[key] = value
    return filtered, skipped
