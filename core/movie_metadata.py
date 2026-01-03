"""Model for normalized movie metadata derived from TMDb."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class MovieMetadata:
    """Normalized metadata used for tag rendering and logging."""

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
    budget: str
    revenue: str
    status: str
    homepage: str
    collection_name: str

    @classmethod
    def from_tmdb(cls, movie: Dict[str, Any], max_overview_len: int) -> "MovieMetadata":
        """Create a MovieMetadata instance from a TMDb payload.

        Args:
            movie: Raw TMDb movie payload.
            max_overview_len: Maximum length for the overview field.

        Returns:
            Normalized MovieMetadata instance.
        """
        title = str(movie.get("title") or movie.get("name") or "").strip()
        release_date = str(movie.get("release_date") or "").strip()
        release_year = release_date[:4] if len(release_date) >= 4 else ""

        overview = str(movie.get("overview") or "").strip()
        if max_overview_len and len(overview) > max_overview_len:
            overview = overview[: max_overview_len - 3].rstrip() + "..."

        tagline = str(movie.get("tagline") or "").strip()

        genres = movie.get("genres") or []
        genres_joined = ", ".join(g.get("name", "") for g in genres if g.get("name"))

        companies = movie.get("production_companies") or []
        production_companies_joined = ", ".join(c.get("name", "") for c in companies if c.get("name"))

        origin_countries = movie.get("origin_country") or []
        origin_countries_joined = ", ".join(str(c) for c in origin_countries if c)

        production_countries = movie.get("production_countries") or []
        production_countries_joined = ", ".join(
            c.get("name", "") for c in production_countries if c.get("name")
        )

        spoken_languages = movie.get("spoken_languages") or []
        spoken_languages_joined = ", ".join(
            lang.get("english_name", "") for lang in spoken_languages if lang.get("english_name")
        )

        collection = movie.get("belongs_to_collection") or {}
        collection_name = ""
        if isinstance(collection, dict):
            collection_name = str(collection.get("name") or "").strip()

        return cls(
            tmdb_id=str(movie.get("id", "")),
            imdb_id=str(movie.get("imdb_id") or ""),
            title=title,
            release_date=release_date,
            release_year=release_year,
            overview=overview,
            tagline=tagline,
            genres_joined=genres_joined,
            production_companies_joined=production_companies_joined,
            origin_countries_joined=origin_countries_joined,
            production_countries_joined=production_countries_joined,
            spoken_languages_joined=spoken_languages_joined,
            original_title=str(movie.get("original_title") or "").strip(),
            original_language=str(movie.get("original_language") or "").strip(),
            runtime=str(movie.get("runtime") or ""),
            poster_path=str(movie.get("poster_path") or ""),
            popularity=str(movie.get("popularity") or ""),
            vote_average=str(movie.get("vote_average") or ""),
            vote_count=str(movie.get("vote_count") or ""),
            budget=str(movie.get("budget") or ""),
            revenue=str(movie.get("revenue") or ""),
            status=str(movie.get("status") or "").strip(),
            homepage=str(movie.get("homepage") or "").strip(),
            collection_name=collection_name,
        )

    def to_context(self) -> Dict[str, str]:
        """Convert the metadata into a template context mapping.

        Returns:
            Dictionary of string values suitable for tag templates.
        """
        return {
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
            "budget": self.budget,
            "revenue": self.revenue,
            "status": self.status,
            "homepage": self.homepage,
            "collection_name": self.collection_name,
        }
