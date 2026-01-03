"""Shared metadata model used by movie and TV metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class BaseMetadata:
    """Shared metadata fields for movie and TV content."""

    media_type: str
    tmdb_id: str
    imdb_id: str
    title: str
    release_date: str
    release_year: str
    overview: str
    tagline: str
    genres_joined: str
    production_companies_joined: str
    origin_countries_joined: str
    production_countries_joined: str
    spoken_languages_joined: str
    original_title: str
    original_language: str
    runtime: str
    poster_path: str
    popularity: str
    vote_average: str
    vote_count: str
    status: str
    homepage: str

    def to_context(self) -> Dict[str, str]:
        """Convert the shared metadata into a template context mapping."""
        return {
            "media_type": self.media_type,
            "title": self.title,
            "release_date": self.release_date,
            "release_year": self.release_year,
            "overview": self.overview,
            "tagline": self.tagline,
            "genres_joined": self.genres_joined,
            "production_companies_joined": self.production_companies_joined,
            "origin_countries_joined": self.origin_countries_joined,
            "production_countries_joined": self.production_countries_joined,
            "spoken_languages_joined": self.spoken_languages_joined,
            "tmdb_id": self.tmdb_id,
            "imdb_id": self.imdb_id,
            "original_title": self.original_title,
            "original_language": self.original_language,
            "runtime": self.runtime,
            "popularity": self.popularity,
            "vote_average": self.vote_average,
            "vote_count": self.vote_count,
            "status": self.status,
            "homepage": self.homepage,
        }
