"""Configuration loading and normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from config.merge import merge_sections
from config.models import (
    Config,
    MatchingConfig,
    ScanConfig,
    SerializationConfig,
    TmdbConfig,
    WriteConfig,
)


BASE_DIR = Path(__file__).resolve().parent.parent
MODULE_CONFIG_PATHS = {
    "tmdb": BASE_DIR / "tmdb" / "config.json",
    "scan": BASE_DIR / "file_io" / "config.json",
    "matching": BASE_DIR / "core" / "matching_config.json",
    "write": BASE_DIR / "ffmpeg" / "config.json",
    "serialization": BASE_DIR / "core" / "serialization_config.json",
}


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_default_sections() -> Dict[str, Any]:
    raw: Dict[str, Any] = {}
    for section, file_path in MODULE_CONFIG_PATHS.items():
        if file_path.exists():
            raw[section] = _load_json(file_path)
    return raw


def config_from_dict(raw: Dict[str, Any]) -> Config:
    """Build a Config instance from a raw dictionary."""
    tmdb_raw = raw.get("tmdb", {}) or {}
    scan_raw = raw.get("scan", {}) or {}
    matching_raw = raw.get("matching", {}) or {}
    write_raw = raw.get("write", {}) or {}
    serialization_raw = raw.get("serialization", {}) or {}
    tags_raw = raw.get("tags", {}) or {}

    tmdb = TmdbConfig(
        api_key_env=str(tmdb_raw.get("api_key_env", "TMDB_API_KEY")),
        api_key=str(tmdb_raw.get("api_key", "")),
        language=str(tmdb_raw.get("language", "en-US")),
        include_adult=_as_bool(tmdb_raw.get("include_adult"), False),
        min_score=_as_float(tmdb_raw.get("min_score", 2.0), 2.0),
        request_delay_seconds=_as_float(tmdb_raw.get("request_delay_seconds", 0.25), 0.25),
    )
    scan = ScanConfig(
        extensions=_as_list(scan_raw.get("extensions")),
        ignore_substrings=_as_list(scan_raw.get("ignore_substrings")),
        max_files=_as_int(scan_raw.get("max_files", 0), 0),
    )
    matching = MatchingConfig(
        strip_tokens=_as_list(matching_raw.get("strip_tokens")),
        prefer_year_from_filename=_as_bool(matching_raw.get("prefer_year_from_filename"), True),
    )

    test_mode_raw = write_raw.get("test_mode", None)
    test_mode: str | None = None
    if isinstance(test_mode_raw, str) and test_mode_raw.lower() in ("basic", "verbose"):
        test_mode = test_mode_raw.lower()
    elif test_mode_raw is True:
        test_mode = "basic"

    write = WriteConfig(
        enabled=_as_bool(write_raw.get("enabled"), True),
        dry_run=_as_bool(write_raw.get("dry_run"), False),
        override_existing=_as_bool(write_raw.get("override_existing"), False),
        backup_original=_as_bool(write_raw.get("backup_original"), True),
        backup_dir=str(write_raw.get("backup_dir", "runs")),
        backup_suffix=str(write_raw.get("backup_suffix", ".bak")),
        cover_art_enabled=_as_bool(write_raw.get("cover_art_enabled"), False),
        cover_art_size=str(write_raw.get("cover_art_size", "w500")),
        ffmpeg_path=str(write_raw.get("ffmpeg_path", "ffmpeg")),
        ffmpeg_analyzeduration=write_raw.get("ffmpeg_analyzeduration"),
        ffmpeg_probe_size=write_raw.get("ffmpeg_probe_size"),
        atomic_replace=_as_bool(write_raw.get("atomic_replace"), True),
        test_mode=test_mode,
    )

    merged_serialization = dict(tags_raw)
    merged_serialization.update(serialization_raw)
    serialization = SerializationConfig(
        mappings={str(k): str(v) for k, v in (merged_serialization.get("mappings") or {}).items()},
        max_overview_length=_as_int(merged_serialization.get("max_overview_length", 500), 500),
    )
    return Config(
        tmdb=tmdb,
        scan=scan,
        matching=matching,
        write=write,
        serialization=serialization,
    )


def load_config(path: Path | None) -> Config:
    """Load config data into a Config instance."""
    raw = _load_default_sections()
    if path is not None:
        raw = merge_sections(raw, _load_json(path))
    return config_from_dict(raw)
