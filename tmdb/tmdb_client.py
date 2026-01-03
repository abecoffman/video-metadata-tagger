"""TMDb API client and title matching helpers."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any, Dict

import requests


TMDB_BASE = "https://api.themoviedb.org/3"


def tmdb_request(session: requests.Session, api_key: str, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a TMDb API request.

    Args:
        session: Requests session.
        api_key: TMDb API key.
        endpoint: API endpoint path.
        params: Query parameters.

    Returns:
        Parsed JSON response.
    """
    url = f"{TMDB_BASE}{endpoint}"
    params = dict(params)
    params["api_key"] = api_key
    resp = session.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching.

    Args:
        title: Title to normalize.

    Returns:
        Normalized title string.
    """
    lowered = title.lower()
    lowered = lowered.replace("&", "and")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def title_similarity(left: str, right: str) -> float:
    """Compute a fuzzy similarity score between two titles.

    Args:
        left: First title.
        right: Second title.

    Returns:
        Similarity score in [0, 1].
    """
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def tmdb_search_best_match(
    session: requests.Session,
    api_key: str,
    title: str,
    year: int | None,
    language: str,
    include_adult: bool,
    min_score: float,
) -> Dict[str, Any] | None:
    """Find the best TMDb match for a title.

    Args:
        session: Requests session.
        api_key: TMDb API key.
        title: Movie title to search.
        year: Optional release year.
        language: Language code.
        include_adult: Whether to include adult titles.
        min_score: Minimum similarity score threshold.

    Returns:
        Best matching result dict, or None if below threshold.
    """
    if not title:
        return None

    params: Dict[str, Any] = {"query": title, "language": language, "include_adult": include_adult}
    if year:
        params["year"] = year

    data = tmdb_request(session, api_key, "/search/movie", params)
    results = data.get("results", []) or []
    if not results:
        return None

    def score(r: Dict[str, Any]) -> float:
        result_title = str(r.get("title") or r.get("original_title") or "")
        return title_similarity(title, result_title) * 10.0

    best = max(results, key=score)
    if score(best) < min_score:
        return None
    return best


def tmdb_movie_details(session: requests.Session, api_key: str, movie_id: int, language: str) -> Dict[str, Any]:
    """Fetch full TMDb details for a movie.

    Args:
        session: Requests session.
        api_key: TMDb API key.
        movie_id: TMDb movie ID.
        language: Language code.

    Returns:
        Movie details payload.
    """
    return tmdb_request(session, api_key, f"/movie/{movie_id}", {"language": language})
