"""Genre normalization helpers."""

from __future__ import annotations

import re
from typing import Iterable, List


_CANONICAL_GENRES = [
    "Action",
    "Adventure",
    "Animation",
    "Biography",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "History",
    "Horror",
    "Kids",
    "Music",
    "Musical",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Sport",
    "Thriller",
    "War",
    "Western",
]


def _normalize_key(value: str) -> str:
    lowered = value.strip().lower()
    lowered = lowered.replace("&", "and")
    lowered = lowered.replace("-", " ")
    lowered = re.sub(r"[/_]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


_CANONICAL_LOOKUP = {_normalize_key(name): name for name in _CANONICAL_GENRES}

TMDB_TO_ITUNES = {
    "Action": "Action",
    "Adventure": "Adventure",
    "Action & Adventure": "Action",
    "Animation": "Animation",
    "Comedy": "Comedy",
    "Crime": "Crime",
    "Documentary": "Documentary",
    "Drama": "Drama",
    "Family": "Family",
    "Fantasy": "Fantasy",
    "History": "History",
    "Horror": "Horror",
    "Music": "Music",
    "Musical": "Musical",
    "Mystery": "Mystery",
    "Romance": "Romance",
    "Science Fiction": "Sci-Fi",
    "Sci-Fi & Fantasy": "Sci-Fi",
    "Thriller": "Thriller",
    "War": "War",
    "War & Politics": "War",
    "Western": "Western",
    "Kids": "Kids",
    "Sport": "Sport",
    "TV Movie": "Drama",
    "Reality": "Documentary",
    "News": "Documentary",
    "Talk": "Documentary",
    "Soap": "Drama",
}

_TMDB_LOOKUP = {_normalize_key(key): value for key, value in TMDB_TO_ITUNES.items()}

_PRIORITY_ORDER = [
    "Documentary",
    "Animation",
    "Action",
    "Adventure",
    "Comedy",
    "Drama",
    "Thriller",
    "Sci-Fi",
    "Horror",
    "Romance",
    "Crime",
    "Fantasy",
    "Family",
    "War",
    "Western",
]
_PRIORITY_INDEX = {name: idx for idx, name in enumerate(_PRIORITY_ORDER)}


def normalize_genres(genres: Iterable[str], max_genres: int = 2) -> List[str]:
    """Normalize genre names to the canonical list while preserving order."""
    normalized: List[str] = []
    seen = set()
    compound_present = False
    max_genres = max(1, int(max_genres))
    for raw in genres:
        if not raw:
            continue
        raw_text = str(raw)
        if "&" in raw_text:
            compound_present = True
        key = _normalize_key(raw_text)
        mapped = _TMDB_LOOKUP.get(key) or _CANONICAL_LOOKUP.get(key)
        if not mapped or mapped in seen or mapped not in _CANONICAL_GENRES:
            continue
        normalized.append(mapped)
        seen.add(mapped)
    if not normalized:
        return []
    normalized.sort(key=lambda name: _PRIORITY_INDEX.get(name, len(_PRIORITY_ORDER)))
    if compound_present or max_genres == 1:
        return normalized[:1]
    return normalized[:max_genres]
