"""Configuration loading and normalized dataclasses."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class TmdbConfig:
    """TMDb configuration settings."""

    api_key_env: str = "TMDB_API_KEY"
    api_key: str = ""
    language: str = "en-US"
    include_adult: bool = False
    min_score: float = 2.0
    request_delay_seconds: float = 0.25


@dataclass
class ScanConfig:
    """File scanning configuration settings."""

    extensions: List[str] = field(default_factory=list)
    ignore_substrings: List[str] = field(default_factory=list)
    max_files: int = 0


@dataclass
class MatchingConfig:
    """Filename matching configuration settings."""

    strip_tokens: List[str] = field(default_factory=list)
    prefer_year_from_filename: bool = True


@dataclass
class WriteConfig:
    """Metadata writing configuration settings."""

    enabled: bool = True
    dry_run: bool = False
    backup_original: bool = True
    backup_dir: str = "runs"
    backup_suffix: str = ".bak"
    cover_art_enabled: bool = False
    cover_art_size: str = "w500"
    ffmpeg_path: str = "ffmpeg"
    ffmpeg_analyzeduration: str | int | None = None
    ffmpeg_probe_size: str | int | None = None
    atomic_replace: bool = True
    test_mode: str | None = None


@dataclass
class SerializationConfig:
    """Serialization template configuration settings."""

    mappings: Dict[str, str] = field(default_factory=dict)
    max_overview_length: int = 500


@dataclass
class Config:
    """Top-level configuration container."""

    tmdb: TmdbConfig
    scan: ScanConfig
    matching: MatchingConfig
    write: WriteConfig
    serialization: SerializationConfig


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


def config_from_dict(raw: Dict[str, Any]) -> Config:
    """Build a Config instance from a raw dictionary.

    Args:
        raw: Raw config dictionary.

    Returns:
        Normalized Config instance.
    """
    tmdb_raw = raw.get("tmdb", {}) or {}
    scan_raw = raw.get("scan", {}) or {}
    matching_raw = raw.get("matching", {}) or {}
    write_raw = raw.get("write", {}) or {}
    tags_raw = raw.get("tags", {}) or {}
    serialization_raw = raw.get("serialization", {}) or {}

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


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _default_section_files() -> Dict[str, Path]:
    base = Path(__file__).resolve().parent
    return {
        "tmdb": base / "tmdb" / "config.json",
        "scan": base / "file_io" / "config.json",
        "matching": base / "core" / "matching_config.json",
        "write": base / "ffmpeg" / "config.json",
        "serialization": base / "core" / "serialization_config.json",
    }


def _load_default_sections() -> Dict[str, Any]:
    raw: Dict[str, Any] = {}
    for section, file_path in _default_section_files().items():
        if file_path.exists():
            raw[section] = _load_json(file_path)
    return raw


def _merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_sections(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for section, values in overrides.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = _merge_dicts(merged[section], values)
        else:
            merged[section] = values
    return merged


def load_config(path: Path | None) -> Config:
    """Load config data into a Config instance.

    Args:
        path: Optional path to a JSON config file containing overrides.

    Returns:
        Parsed Config instance.
    """
    raw = _load_default_sections()
    if path is not None:
        raw = _merge_sections(raw, _load_json(path))
    return config_from_dict(raw)
