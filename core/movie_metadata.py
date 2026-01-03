"""Model for normalized movie metadata derived from TMDb."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class MovieMetadata:
    """Normalized metadata used for tag rendering and logging."""

    tmdb_id: str
    title: str
    release_date: str
    release_year: str
    overview: str
    genres_joined: str
    production_companies_joined: str
    original_title: str
    original_language: str
    runtime: str
    poster_path: str

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

        genres = movie.get("genres") or []
        genres_joined = ", ".join(g.get("name", "") for g in genres if g.get("name"))

        companies = movie.get("production_companies") or []
        production_companies_joined = ", ".join(c.get("name", "") for c in companies if c.get("name"))

        return cls(
            tmdb_id=str(movie.get("id", "")),
            title=title,
            release_date=release_date,
            release_year=release_year,
            overview=overview,
            genres_joined=genres_joined,
            production_companies_joined=production_companies_joined,
            original_title=str(movie.get("original_title") or "").strip(),
            original_language=str(movie.get("original_language") or "").strip(),
            runtime=str(movie.get("runtime") or ""),
            poster_path=str(movie.get("poster_path") or ""),
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
            "genres_joined": self.genres_joined,
            "production_companies_joined": self.production_companies_joined,
            "tmdb_id": self.tmdb_id,
            "original_title": self.original_title,
            "original_language": self.original_language,
            "runtime": self.runtime,
        }
