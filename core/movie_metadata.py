"""Model for normalized movie metadata derived from TMDb."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.metadata_base import BaseMetadata


@dataclass(frozen=True)
class MovieMetadata(BaseMetadata):
    """Normalized metadata used for movie tag rendering and logging."""

    budget: str
    revenue: str
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
        release_date = str(movie.get("release_date") or movie.get("first_air_date") or "").strip()
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
            media_type="movie",
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
            original_title=str(movie.get("original_title") or movie.get("original_name") or "").strip(),
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
        ctx = super().to_context()
        ctx.update(
            {
                "budget": self.budget,
                "revenue": self.revenue,
                "collection_name": self.collection_name,
            }
        )
        return ctx
