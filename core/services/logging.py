"""Logging helpers for metadata output."""

from __future__ import annotations

from typing import Dict

from core.mapping.transforms import extract_itunmovi_people
from logger import get_logger

log = get_logger()


def log_serialized_metadata(
    tags: Dict[str, object],
    *,
    label: str,
    indent: str = "    - ",
) -> None:
    """Log serialized metadata for a tag set."""
    if not tags:
        return
    log.info(label)
    for key, value in tags.items():
        if key == "iTunMOVI":
            people = extract_itunmovi_people(str(value))
            if not people:
                continue
            for role, names in people.items():
                if not names:
                    continue
                log.info(f"{indent}{role}: {', '.join(names)}")
            continue
        if isinstance(value, list):
            text = ", ".join(value)
        else:
            text = str(value)
        preview = text if len(text) <= 120 else (text[:117] + "...")
        log.info(f"{indent}{key}: {preview}")
