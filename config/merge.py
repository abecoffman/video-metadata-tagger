"""Config merging helpers."""

from __future__ import annotations

from typing import Any, Dict


def merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overrides into base."""
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_sections(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Merge per-section overrides into the base config."""
    merged = dict(base)
    for section, values in overrides.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = merge_dicts(merged[section], values)
        else:
            merged[section] = values
    return merged
