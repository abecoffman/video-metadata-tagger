"""TMDb-specific view models derived from API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.mapping.genres import normalize_genres
from core.models.mp4 import Mp4Metadata


@dataclass(frozen=True)
class BaseTmdbMetadata:
    """Shared metadata fields derived from TMDb payloads."""

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
        """Convert the metadata into a template context mapping."""
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


@dataclass(frozen=True)
class TmdbMovieMetadata(BaseTmdbMetadata):
    """Normalized movie metadata derived from TMDb."""

    budget: str
    revenue: str
    collection_name: str

    @classmethod
    def from_tmdb(cls, movie: Dict[str, Any], max_overview_len: int) -> "TmdbMovieMetadata":
        """Create a TmdbMovieMetadata instance from a TMDb payload."""
        title = Mp4Metadata.normalize_text(movie.get("title") or movie.get("name"))
        release_date = Mp4Metadata.normalize_text(movie.get("release_date") or movie.get("first_air_date"))
        release_year = Mp4Metadata.normalize_year(release_date)

        overview = Mp4Metadata.normalize_text(movie.get("overview"), max_overview_len or None)

        tagline = Mp4Metadata.normalize_text(movie.get("tagline"))

        genres = movie.get("genres") or []
        genres_joined = ", ".join(normalize_genres(g.get("name", "") for g in genres if g.get("name")))

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
            collection_name = Mp4Metadata.normalize_text(collection.get("name"))

        return cls(
            media_type="movie",
            tmdb_id=Mp4Metadata.normalize_text(movie.get("id")),
            imdb_id=Mp4Metadata.normalize_text(movie.get("imdb_id")),
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
            original_title=Mp4Metadata.normalize_text(movie.get("original_title") or movie.get("original_name")),
            original_language=Mp4Metadata.normalize_text(movie.get("original_language")),
            runtime=Mp4Metadata.normalize_text(movie.get("runtime")),
            poster_path=Mp4Metadata.normalize_text(movie.get("poster_path")),
            popularity=Mp4Metadata.normalize_text(movie.get("popularity")),
            vote_average=Mp4Metadata.normalize_text(movie.get("vote_average")),
            vote_count=Mp4Metadata.normalize_text(movie.get("vote_count")),
            budget=Mp4Metadata.normalize_text(movie.get("budget")),
            revenue=Mp4Metadata.normalize_text(movie.get("revenue")),
            status=Mp4Metadata.normalize_text(movie.get("status")),
            homepage=Mp4Metadata.normalize_text(movie.get("homepage")),
            collection_name=collection_name,
        )

    def to_context(self) -> Dict[str, str]:
        """Convert the metadata into a template context mapping."""
        ctx = super().to_context()
        ctx.update(
            {
                "budget": self.budget,
                "revenue": self.revenue,
                "collection_name": self.collection_name,
            }
        )
        return ctx


@dataclass(frozen=True)
class TmdbTvMetadata(BaseTmdbMetadata):
    """Normalized TV metadata derived from TMDb."""

    networks_joined: str
    number_of_seasons: str
    number_of_episodes: str
    episode_runtime: str

    @classmethod
    def from_tmdb(cls, show: Dict[str, Any], max_overview_len: int) -> "TmdbTvMetadata":
        """Create a TmdbTvMetadata instance from a TMDb payload."""
        title = Mp4Metadata.normalize_text(show.get("name") or show.get("title"))
        release_date = Mp4Metadata.normalize_text(show.get("first_air_date"))
        release_year = Mp4Metadata.normalize_year(release_date)

        overview = Mp4Metadata.normalize_text(show.get("overview"), max_overview_len or None)

        tagline = Mp4Metadata.normalize_text(show.get("tagline"))

        genres = show.get("genres") or []
        genres_joined = ", ".join(normalize_genres(g.get("name", "") for g in genres if g.get("name")))

        companies = show.get("production_companies") or []
        production_companies_joined = ", ".join(c.get("name", "") for c in companies if c.get("name"))
        if not production_companies_joined:
            networks = show.get("networks") or []
            production_companies_joined = ", ".join(n.get("name", "") for n in networks if n.get("name"))

        origin_countries = show.get("origin_country") or []
        origin_countries_joined = ", ".join(str(c) for c in origin_countries if c)

        production_countries = show.get("production_countries") or []
        production_countries_joined = ", ".join(
            c.get("name", "") for c in production_countries if c.get("name")
        )

        spoken_languages = show.get("spoken_languages") or []
        spoken_languages_joined = ", ".join(
            lang.get("english_name", "") for lang in spoken_languages if lang.get("english_name")
        )

        runtime = ""
        episode_runtime_value = ""
        episode_runtime = show.get("episode_run_time") or []
        if isinstance(episode_runtime, list) and episode_runtime:
            episode_runtime_value = Mp4Metadata.normalize_text(episode_runtime[0])
            runtime = episode_runtime_value

        networks = show.get("networks") or []
        networks_joined = ", ".join(n.get("name", "") for n in networks if n.get("name"))

        return cls(
            media_type="tv",
            tmdb_id=Mp4Metadata.normalize_text(show.get("id")),
            imdb_id=Mp4Metadata.normalize_text(show.get("imdb_id")),
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
            original_title=Mp4Metadata.normalize_text(show.get("original_name") or show.get("original_title")),
            original_language=Mp4Metadata.normalize_text(show.get("original_language")),
            runtime=runtime,
            poster_path=Mp4Metadata.normalize_text(show.get("poster_path")),
            popularity=Mp4Metadata.normalize_text(show.get("popularity")),
            vote_average=Mp4Metadata.normalize_text(show.get("vote_average")),
            vote_count=Mp4Metadata.normalize_text(show.get("vote_count")),
            status=Mp4Metadata.normalize_text(show.get("status")),
            homepage=Mp4Metadata.normalize_text(show.get("homepage")),
            networks_joined=networks_joined,
            number_of_seasons=Mp4Metadata.normalize_text(show.get("number_of_seasons")),
            number_of_episodes=Mp4Metadata.normalize_text(show.get("number_of_episodes")),
            episode_runtime=episode_runtime_value,
        )

    def to_context(self) -> Dict[str, str]:
        """Convert the metadata into a template context mapping."""
        ctx = super().to_context()
        ctx.update(
            {
                "networks_joined": self.networks_joined,
                "number_of_seasons": self.number_of_seasons,
                "number_of_episodes": self.number_of_episodes,
                "episode_runtime": self.episode_runtime,
            }
        )
        return ctx
