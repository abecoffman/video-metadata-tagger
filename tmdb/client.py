"""TMDb API client and title matching helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable

import requests
from rapidfuzz import fuzz


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


def tmdb_configuration(session: requests.Session, api_key: str) -> Dict[str, Any]:
    """Fetch the TMDb configuration payload."""
    return tmdb_request(session, api_key, "/configuration", {})


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching.

    Args:
        title: Title to normalize.

    Returns:
        Normalized title string.
    """
    lowered = title.lower()
    lowered = unicodedata.normalize("NFKD", lowered)
    lowered = "".join(ch for ch in lowered if not unicodedata.combining(ch))
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
    return fuzz.QRatio(normalize_title(left), normalize_title(right)) / 100.0


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


def tmdb_search_best_match_with_candidates(
    session: requests.Session,
    api_key: str,
    titles: Iterable[str],
    year: int | None,
    language: str,
    include_adult: bool,
    min_score: float,
    fallback_min_score: float,
    fallback_min_votes: int,
) -> Dict[str, Any] | None:
    """Find the best TMDb match for any of the candidate titles."""
    candidate = tmdb_search_best_match_with_candidates_scored(
        session=session,
        api_key=api_key,
        titles=titles,
        year=year,
        language=language,
        include_adult=include_adult,
        min_score=min_score,
        fallback_min_score=fallback_min_score,
        fallback_min_votes=fallback_min_votes,
    )
    if not candidate:
        return None
    return candidate.result


@dataclass(frozen=True)
class MatchCandidate:
    """Scored TMDb candidate match."""

    result: Dict[str, Any]
    score: float
    votes: int
    popularity: float
    media_type: str


def _best_match_with_candidates(
    session: requests.Session,
    api_key: str,
    titles: Iterable[str],
    year: int | None,
    language: str,
    include_adult: bool,
    min_score: float,
    fallback_min_score: float,
    fallback_min_votes: int,
    endpoint: str,
    title_keys: tuple[str, str],
    year_param: str,
    media_type: str,
) -> MatchCandidate | None:
    best: Dict[str, Any] | None = None
    best_score = -1.0
    best_votes = 0
    best_popularity = 0.0
    for title in titles:
        if not title:
            continue
        params: Dict[str, Any] = {"query": title, "language": language, "include_adult": include_adult}
        if year:
            params[year_param] = year
        data = tmdb_request(session, api_key, endpoint, params)
        results = data.get("results", []) or []
        if not results:
            continue

        def score(r: Dict[str, Any]) -> float:
            result_title = str(r.get(title_keys[0]) or r.get(title_keys[1]) or "")
            return title_similarity(title, result_title) * 10.0

        candidate_best = max(results, key=score)
        candidate_score = score(candidate_best)
        candidate_votes = int(candidate_best.get("vote_count") or 0)
        candidate_popularity = float(candidate_best.get("popularity") or 0.0)
        if candidate_score > best_score:
            best = candidate_best
            best_score = candidate_score
            best_votes = candidate_votes
            best_popularity = candidate_popularity

    if not best:
        return None
    if best_score >= min_score or (best_score >= fallback_min_score and best_votes >= fallback_min_votes):
        return MatchCandidate(
            result=best,
            score=best_score,
            votes=best_votes,
            popularity=best_popularity,
            media_type=media_type,
        )
    return None


def tmdb_search_best_match_with_candidates_scored(
    session: requests.Session,
    api_key: str,
    titles: Iterable[str],
    year: int | None,
    language: str,
    include_adult: bool,
    min_score: float,
    fallback_min_score: float,
    fallback_min_votes: int,
) -> MatchCandidate | None:
    """Find the best TMDb movie match with scoring metadata."""
    return _best_match_with_candidates(
        session=session,
        api_key=api_key,
        titles=titles,
        year=year,
        language=language,
        include_adult=include_adult,
        min_score=min_score,
        fallback_min_score=fallback_min_score,
        fallback_min_votes=fallback_min_votes,
        endpoint="/search/movie",
        title_keys=("title", "original_title"),
        year_param="year",
        media_type="movie",
    )


def tmdb_search_best_tv_match_with_candidates(
    session: requests.Session,
    api_key: str,
    titles: Iterable[str],
    year: int | None,
    language: str,
    include_adult: bool,
    min_score: float,
    fallback_min_score: float,
    fallback_min_votes: int,
) -> Dict[str, Any] | None:
    """Find the best TMDb TV match for any of the candidate titles."""
    candidate = tmdb_search_best_tv_match_with_candidates_scored(
        session=session,
        api_key=api_key,
        titles=titles,
        year=year,
        language=language,
        include_adult=include_adult,
        min_score=min_score,
        fallback_min_score=fallback_min_score,
        fallback_min_votes=fallback_min_votes,
    )
    if not candidate:
        return None
    return candidate.result


def tmdb_search_best_tv_match_with_candidates_scored(
    session: requests.Session,
    api_key: str,
    titles: Iterable[str],
    year: int | None,
    language: str,
    include_adult: bool,
    min_score: float,
    fallback_min_score: float,
    fallback_min_votes: int,
) -> MatchCandidate | None:
    """Find the best TMDb TV match with scoring metadata."""
    return _best_match_with_candidates(
        session=session,
        api_key=api_key,
        titles=titles,
        year=year,
        language=language,
        include_adult=include_adult,
        min_score=min_score,
        fallback_min_score=fallback_min_score,
        fallback_min_votes=fallback_min_votes,
        endpoint="/search/tv",
        title_keys=("name", "original_name"),
        year_param="first_air_date_year",
        media_type="tv",
    )


def choose_preferred_match(
    movie_candidate: MatchCandidate | None, tv_candidate: MatchCandidate | None
) -> MatchCandidate | None:
    """Choose the preferred match between a movie and TV candidate."""
    if movie_candidate and not tv_candidate:
        return movie_candidate
    if tv_candidate and not movie_candidate:
        return tv_candidate
    if not movie_candidate or not tv_candidate:
        return None

    score_diff = abs(movie_candidate.score - tv_candidate.score)
    if score_diff >= 0.5:
        return movie_candidate if movie_candidate.score > tv_candidate.score else tv_candidate
    if tv_candidate.popularity != movie_candidate.popularity:
        return tv_candidate if tv_candidate.popularity > movie_candidate.popularity else movie_candidate
    if tv_candidate.votes != movie_candidate.votes:
        return tv_candidate if tv_candidate.votes > movie_candidate.votes else movie_candidate
    return movie_candidate


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


def tmdb_tv_details(session: requests.Session, api_key: str, show_id: int, language: str) -> Dict[str, Any]:
    """Fetch full TMDb details for a TV show."""
    return tmdb_request(session, api_key, f"/tv/{show_id}", {"language": language})
