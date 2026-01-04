"""
transforms.py

Reference transform functions for a TMDb → iTunes/Apple MP4 tagging pipeline.

These are intentionally small, pure (where possible), and easy to unit test.

Notes
- Some transforms expect already-extracted values (e.g., lists of names).
- download_tmdb_image_to_file() performs I/O and requires `requests`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import plistlib
import re
import xml.etree.ElementTree as ET

from core.mapping.genres import normalize_genres
from core.models.mp4 import Mp4Metadata
try:
    import requests  # optional dependency for download_tmdb_image_to_file
except Exception:  # pragma: no cover
    requests = None  # type: ignore


# --- Small utility helpers ---

def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_truthy_text(s: Optional[str]) -> bool:
    return bool(s and s.strip())


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


@dataclass(frozen=True)
class ParsedTV:
    show: str
    season: int
    episode: int
    episode_title_hint: Optional[str] = None


_TV_PATTERNS = [
    re.compile(r"^(?P<show>.+?)\s+[Ss](?P<season>\d{1,2})\s*[Ee](?P<episode>\d{1,3}).*$"),
    re.compile(r"^(?P<show>.+?)\s+[Ss](?P<season>\d{1,2})\s+[Dd](?P<episode>\d{1,2}).*$"),
    re.compile(r"^(?P<show>.+?)\s+[Ss](?P<season>\d{1,2})\s*[Vv](?P<episode>\d{1,3}).*$"),
    re.compile(r"^(?P<show>.+?)\s+[Ss]eason\s+(?P<season>\d{1,2})\s+[Ee]pisode\s+(?P<episode>\d{1,3}).*$"),
]


def parse_tv_from_filename(path: Path) -> Optional[ParsedTV]:
    """Parse show/season/episode from filename stem."""
    stem = path.stem
    s = stem.replace("_", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()

    for pat in _TV_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        show = m.group("show").strip()
        season = int(m.group("season"))
        episode = int(m.group("episode"))

        show = _norm_space(show)

        hint = None
        if re.search(r"\b[dD]\d+\b", s):
            hint = f"Disc {episode}"
        elif re.search(r"\b[vV]\d+\b", s):
            hint = f"Volume {episode}"

        return ParsedTV(show=show, season=season, episode=episode, episode_title_hint=hint)

    return None


# --- Transforms ---

def year_from_date(release_date: Optional[str]) -> Optional[str]:
    """
    Extract YYYY from a TMDb date like '2008-08-15'. Returns None if unavailable.
    """
    year = Mp4Metadata.normalize_year(release_date)
    return year or None


def truncate(text: Optional[str], max_chars: int) -> Optional[str]:
    """
    Truncate text to max_chars with an ellipsis if needed.
    """
    if not _is_truthy_text(text):
        return None
    assert max_chars >= 1, "max_chars must be >= 1"
    t = text.strip()
    if len(t) <= max_chars:
        return t
    if max_chars == 1:
        return "…"
    return t[: max_chars - 1].rstrip() + "…"


def first_nonempty_then_truncate(*values: Optional[str], max_chars: int) -> Optional[str]:
    """Pick the first non-empty value, then truncate."""
    for value in values:
        if _is_truthy_text(value):
            return truncate(_norm_space(value or ""), max_chars=max_chars)
    return None


def limit_list(items: Optional[Sequence[str]], max_items: int = 0) -> list[str]:
    """Return a trimmed list of non-empty values."""
    if not items:
        return []
    cleaned = [_norm_space(x) for x in items if _is_truthy_text(x)]
    if not cleaned:
        return []
    if max_items and max_items > 0:
        cleaned = cleaned[:max_items]
    return cleaned


def pick_crew_names_by_job(
    crew: Any,
    job: str,
    max_items: int = 3,
) -> list[str]:
    """Pick crew names by job and return a de-duplicated list."""
    if not isinstance(crew, list):
        return []

    names: list[str] = []
    for person in crew:
        if not isinstance(person, dict):
            continue
        if person.get("job") == job and person.get("name"):
            names.append(_norm_space(str(person["name"])))

    names = _dedupe_preserve_order([n for n in names if _is_truthy_text(n)])

    if not names:
        return []
    if max_items and max_items > 0:
        return names[:max_items]
    return names


def pick_crew_names_by_jobs(
    crew: Any,
    jobs: Sequence[str],
    max_items: int = 3,
) -> list[str]:
    """Pick crew names by multiple jobs, preserving job order."""
    if not isinstance(crew, list):
        return []

    names: list[str] = []
    for job in jobs:
        job_names = pick_crew_names_by_job(crew, job, max_items=0)
        names.extend(job_names)

    names = _dedupe_preserve_order([n for n in names if _is_truthy_text(n)])
    if not names:
        return []
    if max_items and max_items > 0:
        return names[:max_items]
    return names


def pick_cast_names_by_order(
    cast: Any,
    max_items: int = 10,
) -> list[str]:
    """Pick top-billed cast names by order."""
    if not isinstance(cast, list):
        return []

    ordered = []
    for person in cast:
        if not isinstance(person, dict):
            continue
        order = person.get("order")
        try:
            order_value = int(order)
        except Exception:
            continue
        name = person.get("name")
        if name:
            ordered.append((order_value, _norm_space(str(name))))

    ordered.sort(key=lambda item: item[0])
    names = _dedupe_preserve_order([name for _, name in ordered if _is_truthy_text(name)])
    if not names:
        return []
    if max_items and max_items > 0:
        return names[:max_items]
    return names


def first(items: Optional[Sequence[str]]) -> Optional[str]:
    """
    Return first non-empty item from a list.
    """
    if not items:
        return None
    for x in items:
        if _is_truthy_text(x):
            return _norm_space(x)
    return None


def compose_comment(
    tagline: Optional[str],
    imdb_id: Optional[str],
    tmdb_id: Optional[int],
    *,
    include_ids: bool = True
) -> Optional[str]:
    """
    Combine tagline + IDs into a compact comment string.
    Example: "Love is complicated. | TMDb:123 | IMDb:tt0497465"
    """
    parts: list[str] = []
    if _is_truthy_text(tagline):
        parts.append(_norm_space(tagline or ""))
    if include_ids:
        if tmdb_id:
            parts.append(f"TMDb:{tmdb_id}")
        if _is_truthy_text(imdb_id):
            parts.append(f"IMDb:{_norm_space(imdb_id or '')}")
    return " | ".join(parts) if parts else None


def tmdb_genres_to_apple_genres(tmdb_genres: Sequence[str] | None, max_genres: int = 2) -> list[str]:
    """
    Map TMDb genre names to Apple iTunes canonical genres.

    - Drops unknown genres
    - Limits to max_genres (default 2)
    """
    if not tmdb_genres:
        return []
    return normalize_genres(tmdb_genres, max_genres=max_genres)


def to_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def compose_grouping(collection: Optional[str], language: Optional[str]) -> Optional[str]:
    """
    Compose a grouping field. Example: "The Matrix Collection | lang=en"
    """
    parts: list[str] = []
    if _is_truthy_text(collection):
        parts.append(_norm_space(collection or ""))
    if _is_truthy_text(language):
        parts.append(f"lang={_norm_space(language or '')}")
    return " | ".join(parts) if parts else None


def compose_copyright(companies: Sequence[str] | None, release_year: Optional[str]) -> Optional[str]:
    """
    Conservative copyright string, e.g.: "© 2008 Paramount Pictures"
    """
    if not companies or not _is_truthy_text(release_year):
        return None
    company = first(companies)
    if not company:
        return None
    year = _norm_space(release_year or "")
    if not (len(year) == 4 and year.isdigit()):
        return None
    return f"© {year} {company}"


def infer_hd_from_probe(width: Optional[int], height: Optional[int]) -> int:
    """
    Infer Apple's HD flag (0/1) from dimensions.
    Common heuristic: HD if max dimension >= 1280.
    """
    if not width or not height:
        return 0
    return 1 if max(int(width), int(height)) >= 1280 else 0


def build_itunmovi_payload(tags: dict[str, Any]) -> dict[str, Any]:
    """Build an iTunMOVI payload dict from existing tags."""
    def _collect_names(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            items = value
        else:
            items = [value]
        cleaned = [_norm_space(str(item)) for item in items if _is_truthy_text(str(item))]
        return _dedupe_preserve_order(cleaned)

    cast = _collect_names(tags.get("cast"))
    directors = _collect_names(tags.get("director"))
    producers = _collect_names(tags.get("producer"))
    screenwriters = _collect_names(tags.get("screenwriter"))
    studios = _collect_names(tags.get("studio"))

    payload: dict[str, Any] = {}
    if cast:
        payload["cast"] = [{"name": name} for name in cast]
    if directors:
        payload["directors"] = [{"name": name} for name in directors]
    if producers:
        payload["producers"] = [{"name": name} for name in producers]
    if screenwriters:
        payload["screenwriters"] = [{"name": name} for name in screenwriters]
    if studios:
        payload["studio"] = studios[0]
    return payload


def build_itunmovi_atom(tags: dict[str, Any]) -> Optional[str]:
    """Build an iTunMOVI plist XML payload from existing tags."""
    payload = build_itunmovi_payload(tags)
    if not payload:
        return None
    plist_bytes = plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False)
    return plist_bytes.decode("utf-8")


def extract_itunmovi_people(payload: str) -> dict[str, list[str]]:
    """Extract people lists from an iTunMOVI plist payload."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return {}

    def _parse_people(key: str) -> list[str]:
        items: list[str] = []
        for dict_el in root.findall(".//dict"):
            children = list(dict_el)
            i = 0
            while i < len(children) - 1:
                if children[i].tag == "key" and children[i].text == key:
                    value_el = children[i + 1]
                    if value_el.tag != "array":
                        i += 1
                        continue
                    for entry in value_el.findall("dict"):
                        entry_children = list(entry)
                        j = 0
                        while j < len(entry_children) - 1:
                            if entry_children[j].tag == "key" and entry_children[j].text == "name":
                                name_el = entry_children[j + 1]
                                if name_el.tag == "string" and name_el.text:
                                    items.append(name_el.text.strip())
                            j += 1
                    i += 1
                i += 1
        return _dedupe_preserve_order([n for n in items if _is_truthy_text(n)])

    return {
        "cast": _parse_people("cast"),
        "directors": _parse_people("directors"),
        "producers": _parse_people("producers"),
        "screenwriters": _parse_people("screenwriters"),
    }


@dataclass(frozen=True)
class TMDbImageDownloadConfig:
    """
    Configuration for downloading TMDb images.
    """
    base_url: str = "https://image.tmdb.org/t/p/original"
    timeout_seconds: int = 30


def download_tmdb_image_to_file(
    tmdb_path: str,
    out_path: Path,
    config: TMDbImageDownloadConfig = TMDbImageDownloadConfig(),
) -> Path:
    """
    Download a TMDb image (poster/backdrop) given its path (e.g., '/abc123.jpg')
    and write it to out_path. Returns out_path.

    Requires: pip install requests
    """
    if requests is None:  # pragma: no cover
        raise RuntimeError("requests is required for download_tmdb_image_to_file (pip install requests)")

    if not _is_truthy_text(tmdb_path):
        raise ValueError("tmdb_path is empty")

    # Ensure leading slash exactly once
    path = tmdb_path.strip()
    if not path.startswith("/"):
        path = "/" + path

    url = config.base_url.rstrip("/") + path
    out_path = out_path.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    r = requests.get(url, timeout=config.timeout_seconds)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return out_path
