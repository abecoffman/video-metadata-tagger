"""Model for normalized TV metadata derived from TMDb."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.metadata_base import BaseMetadata


@dataclass(frozen=True)
class TvMetadata(BaseMetadata):
    """Normalized TV metadata used for tag rendering and logging."""

    networks_joined: str
    number_of_seasons: str
    number_of_episodes: str
    episode_runtime: str

    @classmethod
    def from_tmdb(cls, show: Dict[str, Any], max_overview_len: int) -> "TvMetadata":
        """Create a TvMetadata instance from a TMDb payload.

        Args:
            show: Raw TMDb TV payload.
            max_overview_len: Maximum length for the overview field.

        Returns:
            Normalized TvMetadata instance.
        """
        title = str(show.get("name") or show.get("title") or "").strip()
        release_date = str(show.get("first_air_date") or "").strip()
        release_year = release_date[:4] if len(release_date) >= 4 else ""

        overview = str(show.get("overview") or "").strip()
        if max_overview_len and len(overview) > max_overview_len:
            overview = overview[: max_overview_len - 3].rstrip() + "..."

        tagline = str(show.get("tagline") or "").strip()

        genres = show.get("genres") or []
        genres_joined = ", ".join(g.get("name", "") for g in genres if g.get("name"))

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
            episode_runtime_value = str(episode_runtime[0])
            runtime = episode_runtime_value

        networks = show.get("networks") or []
        networks_joined = ", ".join(n.get("name", "") for n in networks if n.get("name"))

        return cls(
            media_type="tv",
            tmdb_id=str(show.get("id", "")),
            imdb_id=str(show.get("imdb_id") or ""),
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
            original_title=str(show.get("original_name") or show.get("original_title") or "").strip(),
            original_language=str(show.get("original_language") or "").strip(),
            runtime=runtime,
            poster_path=str(show.get("poster_path") or ""),
            popularity=str(show.get("popularity") or ""),
            vote_average=str(show.get("vote_average") or ""),
            vote_count=str(show.get("vote_count") or ""),
            status=str(show.get("status") or "").strip(),
            homepage=str(show.get("homepage") or "").strip(),
            networks_joined=networks_joined,
            number_of_seasons=str(show.get("number_of_seasons") or ""),
            number_of_episodes=str(show.get("number_of_episodes") or ""),
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
