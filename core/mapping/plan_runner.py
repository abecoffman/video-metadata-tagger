"""Plan execution helper for tagging plans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.mapping import transforms
from core.mapping_engine import MappingContext, PlanResult, build_tags_from_plan, load_plan
from core.providers.adapter import MappingProvider
from core.mapping import MOVIE_PLAN_PATH, TV_PLAN_PATH
from logger import get_logger

log = get_logger()


@dataclass(frozen=True)
class PlanSelection:
    plan: Dict[str, object] | None
    base_endpoint: str
    transform_modules: List[object]


def load_movie_plan() -> Dict[str, object] | None:
    if MOVIE_PLAN_PATH.exists():
        try:
            return load_plan(MOVIE_PLAN_PATH)
        except Exception as exc:
            log.info(f"  ⚠️ Could not load movie tagging plan: {exc}")
    return None


def load_tv_plan() -> Dict[str, object] | None:
    if TV_PLAN_PATH.exists():
        try:
            return load_plan(TV_PLAN_PATH)
        except Exception as exc:
            log.info(f"  ⚠️ Could not load TV tagging plan: {exc}")
    return None


def select_plan(media_type: str, movie_plan: Dict[str, object] | None, tv_plan: Dict[str, object] | None) -> PlanSelection:
    if media_type == "tv":
        return PlanSelection(
            plan=tv_plan,
            base_endpoint="/tv/{id}",
            transform_modules=[transforms],
        )
    return PlanSelection(
        plan=movie_plan,
        base_endpoint="/movie/{id}",
        transform_modules=[transforms],
    )


def _allowed_writers(metadata_tool: str) -> Set[str]:
    if metadata_tool == "mp4tags":
        return {"mp4tags", "either"}
    return {"ffmpeg", "either"}


def apply_plan_for_file(
    *,
    plan_selection: PlanSelection,
    content_id: int,
    language: str,
    include_adult: bool,
    session: object | None,
    api_key: str,
    request_delay: float,
    tv_season: int | None,
    tv_episode: int | None,
    image_base_url: str,
    poster_sizes: list[str],
    cover_art_size: str,
    run_dir: Path | None,
    inspector: object | None,
    input_path: Path,
    dry_run: bool,
    test_mode: bool,
    allow_artwork_download: bool,
    metadata_tool: str,
    provider: MappingProvider,
    allowed_writers: Set[str] | None = None,
    details: Dict[str, object],
) -> PlanResult | None:
    if not plan_selection.plan:
        return None
    ctx = MappingContext(
        content_id=content_id,
        language=language,
        include_adult=include_adult,
        session=session,
        api_key=api_key,
        request_delay=request_delay,
        tv_season=tv_season,
        tv_episode=tv_episode,
        image_base_url=image_base_url,
        poster_sizes=poster_sizes,
        cover_art_size=cover_art_size,
        run_dir=run_dir,
        inspector=inspector,
        input_path=input_path,
        dry_run=dry_run,
        test_mode=test_mode,
        allow_artwork_download=allow_artwork_download,
    )
    if allowed_writers is None:
        allowed_writers = _allowed_writers(metadata_tool)
    return build_tags_from_plan(
        plan_selection.plan,
        ctx,
        details,
        plan_selection.base_endpoint,
        plan_selection.transform_modules,
        allowed_writers,
        provider,
    )
