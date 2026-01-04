"""Configuration dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TmdbConfig:
    """TMDb configuration settings."""

    api_key_env: str = "TMDB_API_KEY"
    api_key: str = ""
    language: str = "en-US"
    include_adult: bool = False
    min_score: float = 2.0
    fallback_min_score: float = 1.5
    fallback_min_votes: int = 10
    request_delay_seconds: float = 0.25
    allow_tv_fallback: bool = True


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
    override_existing: bool = False
    backup_original: bool = False
    backup_dir: str = "logs"
    max_logs: int = 20
    backup_suffix: str = ".bak"
    cover_art_enabled: bool = True
    cover_art_size: str = "w500"
    ffmpeg_path: str = "ffmpeg"
    mp4tags_path: str = "mp4tags"
    metadata_tool: str = "mp4tags"
    rdns_namespace: str = "local.tmdb"
    ffmpeg_analyzeduration: str | int | None = None
    ffmpeg_probe_size: str | int | None = None
    atomic_replace: bool = True
    test_mode: str | None = None


@dataclass
class Config:
    """Top-level configuration container."""

    tmdb: TmdbConfig
    scan: ScanConfig
    matching: MatchingConfig
    write: WriteConfig
