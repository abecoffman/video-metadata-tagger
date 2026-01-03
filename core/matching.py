"""Filename normalization helpers for matching movie titles."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple


def clean_filename_for_search(stem: str, strip_tokens: List[str]) -> Tuple[str, int | None]:
    """Extract a movie title and year guess from a filename stem.

    Args:
        stem: Filename stem (no extension).
        strip_tokens: Tokens to strip from the filename before searching.

    Returns:
        Tuple of (title, year) where year may be None.
    """
    s = stem.replace("_", " ").replace(".", " ")
    s = re.sub(r"(?<=\w)-(?=\w)", "__HYPHEN__", s)
    s = s.replace("-", " ").replace("__HYPHEN__", "-")
    year = None
    m = re.search(r"\b(19\d{2}|20\d{2})\b", s)
    if m:
        year = int(m.group(1))
        s = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", s)
    # Remove bracketed edition notes like [WS] or (Unrated)
    s = re.sub(r"[\[(].*?[\])]", " ", s)
    # Remove common season/disc/volume bundles like S1V1
    s = re.sub(r"\b[sS]\d+[vV]\d+\b", " ", s)
    # Normalize disc/cd markers like "Disc 1" or "CD2"
    s = re.sub(r"\b(?:disc|cd)\s*\d+\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()

    acronym_map = {
        "lotr": "Lord of the Rings",
    }
    expanded_parts = []
    for part in s.split():
        replacement = acronym_map.get(part.lower())
        if replacement:
            expanded_parts.extend(replacement.split())
        else:
            expanded_parts.append(part)

    tokens = set(t.lower() for t in strip_tokens)
    extra_tokens = {
        "ext",
        "extended",
        "unrated",
        "ws",
        "se",
        "dc",
        "special",
        "edition",
        "remastered",
        "ultimate",
        "cut",
    }
    parts = []
    for part in expanded_parts:
        if part.lower() in tokens:
            continue
        if part.lower() in extra_tokens:
            continue
        if re.fullmatch(r"v\d{1,2}", part, flags=re.IGNORECASE):
            parts.append("Vol")
            parts.append(part[1:])
            continue
        if re.fullmatch(r"[sd]\d{1,2}", part, flags=re.IGNORECASE):
            continue
        parts.append(part)

    title = " ".join(parts).strip()
    title = re.sub(r"\s+", " ", title)
    return title, year


_EXTRAS_TOKENS = {
    "appendix",
    "appendices",
    "bonus",
    "commentary",
    "deleted",
    "extra",
    "extras",
    "featurette",
    "featurettes",
    "outtakes",
    "trailer",
    "trailers",
}


def _tokenize_title(title: str) -> List[str]:
    normalized = unicodedata.normalize("NFKD", title)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", normalized.lower())


def is_extras_title(title: str) -> bool:
    """Return True if the title appears to be bonus/extras content."""
    tokens = set(_tokenize_title(title))
    return bool(tokens.intersection(_EXTRAS_TOKENS))


def build_search_candidates(title: str) -> List[str]:
    """Build search candidate titles from a cleaned title."""
    candidates: List[str] = []
    if title:
        candidates.append(title)

    for part in re.split(r"\s*[-:]\s*", title):
        part = part.strip()
        if part and part != title:
            candidates.append(part)

    tokens = [t for t in title.split() if t]
    if len(tokens) >= 3:
        candidates.append(" ".join(tokens[-3:]))
    if len(tokens) >= 2:
        candidates.append(" ".join(tokens[-2:]))
    if len(tokens) == 1:
        candidates.append(tokens[-1])

    def strip_diacritics(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    unique: List[str] = []
    for candidate in candidates:
        cleaned = re.sub(r"\s+", " ", candidate).strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
        deaccented = strip_diacritics(cleaned)
        if deaccented and deaccented not in unique:
            unique.append(deaccented)
    return unique
