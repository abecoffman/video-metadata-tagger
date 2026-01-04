"""Mapping plan support for provider-driven tagging."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Union

from core.mapping import transforms
from logger import get_logger
from core.providers.adapter import MappingProvider

log = get_logger()


@dataclass(frozen=True)
class MappingContext:
    """Context for applying a mapping plan."""

    content_id: int
    language: str
    include_adult: bool
    session: object | None
    api_key: str
    request_delay: float
    tv_season: int | None
    tv_episode: int | None
    image_base_url: str
    poster_sizes: list[str]
    cover_art_size: str
    run_dir: Path | None
    inspector: object | None
    input_path: Path
    dry_run: bool
    test_mode: bool
    allow_artwork_download: bool


@dataclass(frozen=True)
class PlanResult:
    """Resolved tags and optional cover art path."""

    tags: Dict[str, Union[str, List[str]]]
    cover_art_path: Path | None


def load_plan(path: Path) -> Dict[str, Any]:
    """Load a JSON mapping plan from disk."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)



def _apply_part(value: Any, part: str) -> Any:
    if "[" not in part:
        if isinstance(value, list):
            return [item.get(part) for item in value if isinstance(item, dict) and part in item]
        if isinstance(value, dict):
            return value.get(part)
        return None

    match = re.match(r"^(?P<key>[^\[]+)\[(?P<select>.*)\]$", part)
    if not match:
        return None
    key = match.group("key")
    selector = match.group("select")

    if isinstance(value, dict):
        value = value.get(key)
    elif key:
        return None

    if not isinstance(value, list):
        return []

    if selector == "*":
        return value
    if selector.isdigit():
        idx = int(selector)
        return value[idx] if 0 <= idx < len(value) else None

    filter_match = re.match(r"^\?\(@\.(?P<field>[^=]+)==['\"](?P<target>.+?)['\"]\)$", selector)
    if filter_match:
        field = filter_match.group("field")
        target = filter_match.group("target")
        return [item for item in value if isinstance(item, dict) and str(item.get(field)) == target]
    return []


def extract_jsonpath(payload: Any, jsonpath: str) -> Any:
    """Extract a value from a payload using a minimal JSONPath subset."""
    if not jsonpath.startswith("$."):
        return None
    parts: list[str] = []
    buffer = []
    bracket_depth = 0
    for ch in jsonpath[2:]:
        if ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        if ch == "." and bracket_depth == 0:
            parts.append("".join(buffer))
            buffer = []
            continue
        buffer.append(ch)
    if buffer:
        parts.append("".join(buffer))
    current: Any = payload
    for part in parts:
        current = _apply_part(current, part)
        if current is None:
            return None
    return current


def _resolve_values(payloads: Dict[str, Any], sources: list[Dict[str, Any]]) -> list[Any]:
    values: list[Any] = []
    for source in sources:
        endpoint = str(source.get("endpoint") or "")
        jsonpath = str(source.get("jsonpath") or "")
        payload = payloads.get(endpoint, {})
        values.append(extract_jsonpath(payload, jsonpath))
    return values


def _normalize_value(value: Any) -> str | list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        return cleaned if cleaned else None
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).strip()
    return text if text else None


def _apply_transform(
    name: str | None,
    values: list[Any],
    params: Dict[str, Any] | None,
    ctx: MappingContext,
    transform_modules: list[object],
    provider: MappingProvider,
) -> Any:
    if not name:
        for value in values:
            if value not in (None, "", [], {}):
                return value
        return None

    params = params or {}
    if name == "infer_hd_from_probe":
        if not ctx.inspector:
            return 0
        width, height = ctx.inspector.get_video_dimensions(ctx.input_path)
        return transforms.infer_hd_from_probe(width, height)

    if name == "download_tmdb_image_to_file":
        tmdb_path = values[0] if values else None
        if not tmdb_path:
            return None
        return provider.download_artwork(ctx, str(tmdb_path))

    if name == "choose_and_download_artwork":
        return provider.choose_and_download_artwork(ctx, values)

    func: Callable[..., Any] | None = None
    for module in transform_modules:
        func = getattr(module, name, None)
        if func:
            break
    if not func:
        log.info(f"  ⚠️ Unknown transform: {name}")
        return None

    try:
        if len(values) <= 1:
            return func(values[0] if values else None, **params)
        return func(*values, **params)
    except Exception as exc:
        log.info(f"  ⚠️ Transform '{name}' failed: {exc}")
        return None


def build_tags_from_plan(
    plan: Dict[str, Any],
    ctx: MappingContext,
    base_payload: Dict[str, Any],
    base_endpoint: str,
    transform_modules: list[object],
    allowed_writers: Set[str],
    provider: MappingProvider,
) -> PlanResult:
    payloads = provider.fetch_payloads(plan, ctx, base_payload, base_endpoint)
    tags: Dict[str, Union[str, List[str]]] = {}
    cover_art_path: Path | None = None

    for rule in plan.get("rules", []):
        itunes_key = str(rule.get("itunes_key") or "").strip()
        if not itunes_key:
            continue
        writer = str(rule.get("writer") or "either").strip().lower()
        if writer and writer not in allowed_writers and writer != "either":
            continue
        sources = rule.get("tmdb_sources") or []
        values = _resolve_values(payloads, sources)
        result = _apply_transform(
            rule.get("transform"),
            values,
            rule.get("params") or {},
            ctx,
            transform_modules,
            provider,
        )
        if result in (None, "", [], {}):
            result = rule.get("fallback")
        if result in (None, "", [], {}):
            if itunes_key == "director":
                log.info("  ⚠️ Director not found in credits payload.")
            continue
        if itunes_key == "artwork":
            if isinstance(result, Path):
                cover_art_path = result
            continue
        normalized = _normalize_value(result)
        if normalized:
            tags[itunes_key] = normalized

    return PlanResult(tags=tags, cover_art_path=cover_art_path)
