"""TMDb session initialization."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from config import Config
from tmdb.tmdb_images import tmdb_configuration


@dataclass
class TmdbContext:
    """TMDb session and configuration context."""

    session: requests.Session | None
    api_key: str
    language: str
    include_adult: bool
    min_score: float
    delay: float
    image_base_url: str
    poster_sizes: list[str]
    cover_art_enabled: bool


def init_tmdb(
    cfg: Config,
    cover_art_enabled: bool,
    write_enabled: bool,
    test_mode_setting: str | None,
    restore_backup: bool,
) -> tuple[TmdbContext, str | None]:
    """Initialize TMDb session and image configuration."""
    if restore_backup:
        return (
            TmdbContext(
                session=None,
                api_key="",
                language="",
                include_adult=False,
                min_score=0.0,
                delay=0.0,
                image_base_url="",
                poster_sizes=[],
                cover_art_enabled=cover_art_enabled,
            ),
            None,
        )

    api_key_env = cfg.tmdb.api_key_env
    api_key = cfg.tmdb.api_key or os.environ.get(api_key_env, "")
    if not api_key:
        return (
            TmdbContext(
                session=None,
                api_key="",
                language="",
                include_adult=False,
                min_score=0.0,
                delay=0.0,
                image_base_url="",
                poster_sizes=[],
                cover_art_enabled=cover_art_enabled,
            ),
            f"TMDb API key missing. Set env var {api_key_env} or add tmdb.api_key to config.",
        )

    language = cfg.tmdb.language
    include_adult = bool(cfg.tmdb.include_adult)
    min_score = float(cfg.tmdb.min_score)
    delay = float(cfg.tmdb.request_delay_seconds)
    session = requests.Session()
    image_base_url = ""
    poster_sizes: list[str] = []

    if cover_art_enabled and (write_enabled or test_mode_setting == "verbose"):
        config_data = tmdb_configuration(session, api_key)
        images = config_data.get("images", {}) if isinstance(config_data, dict) else {}
        image_base_url = str(images.get("secure_base_url") or images.get("base_url") or "")
        poster_sizes = list(images.get("poster_sizes") or [])
        if not image_base_url or not poster_sizes:
            print("Cover art disabled: TMDb image configuration missing.")
            cover_art_enabled = False

    return (
        TmdbContext(
            session=session,
            api_key=api_key,
            language=language,
            include_adult=include_adult,
            min_score=min_score,
            delay=delay,
            image_base_url=image_base_url,
            poster_sizes=poster_sizes,
            cover_art_enabled=cover_art_enabled,
        ),
        None,
    )
