"""Mapping plans and transforms."""

from pathlib import Path

from core.mapping import genres, transforms

BASE_DIR = Path(__file__).parent
MOVIE_PLAN_PATH = BASE_DIR / "movies" / "tmdb_itunes_movie_plan.json"
TV_PLAN_PATH = BASE_DIR / "tv" / "tmdb_itunes_tv_plan.json"

__all__ = ["genres", "transforms", "MOVIE_PLAN_PATH", "TV_PLAN_PATH"]
