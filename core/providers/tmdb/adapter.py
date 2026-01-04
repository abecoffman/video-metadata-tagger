"""TMDb mapping provider adapter."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from core.mapping import transforms
from core.mapping.transforms import TMDbImageDownloadConfig
from core.providers.adapter import MappingProvider
from core.providers.tmdb.client import tmdb_request
from core.providers.tmdb.helpers import select_image_size
from logger import get_logger

if TYPE_CHECKING:
    from core.mapping_engine import MappingContext

log = get_logger()


class TmdbMappingProvider(MappingProvider):
    """Mapping provider implementation for TMDb."""

    name = "tmdb"

    def fetch_payloads(
        self,
        plan: Dict[str, Any],
        ctx: "MappingContext",
        base_payload: Dict[str, Any],
        base_endpoint: str,
    ) -> Dict[str, Any]:
        payloads: Dict[str, Any] = {base_endpoint: base_payload}
        if not ctx.session or not ctx.api_key:
            return payloads

        endpoints: set[str] = set()
        for rule in plan.get("rules", []):
            for source in rule.get("tmdb_sources", []):
                endpoint = str(source.get("endpoint") or "")
                if endpoint and endpoint != base_endpoint:
                    endpoints.add(endpoint)

        for endpoint in sorted(endpoints):
            if "{s}" in endpoint and ctx.tv_season is None:
                log.info(f"  ⚠️ TV season missing; skipping TMDb endpoint {endpoint}")
                payloads[endpoint] = {}
                continue
            if "{e}" in endpoint and ctx.tv_episode is None:
                log.info(f"  ⚠️ TV episode missing; skipping TMDb endpoint {endpoint}")
                payloads[endpoint] = {}
                continue
            resolved = (
                endpoint.replace("{id}", str(ctx.content_id))
                .replace("{s}", str(ctx.tv_season or ""))
                .replace("{e}", str(ctx.tv_episode or ""))
            )
            params: Dict[str, Any] = {"language": ctx.language, "include_adult": ctx.include_adult}
            try:
                payloads[endpoint] = tmdb_request(ctx.session, ctx.api_key, resolved, params)
                if ctx.request_delay:
                    time.sleep(ctx.request_delay)
            except Exception as exc:
                log.info(f"  ⚠️ TMDb fetch failed for {resolved}: {exc}")
                payloads[endpoint] = {}
        return payloads

    def download_artwork(self, ctx: "MappingContext", path: str) -> Path | None:
        if ctx.test_mode or ctx.dry_run:
            return None
        if not ctx.allow_artwork_download:
            return None
        if not ctx.run_dir:
            return None
        image_dir = ctx.run_dir / "artwork"
        image_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(str(path)).suffix or ".jpg"
        out_path = image_dir / f"{ctx.content_id}{suffix}"
        size = select_image_size(ctx.poster_sizes, ctx.cover_art_size) if ctx.poster_sizes else "original"
        base_url = ctx.image_base_url.rstrip("/") + "/" + size
        config = TMDbImageDownloadConfig(base_url=base_url)
        try:
            return transforms.download_tmdb_image_to_file(str(path), out_path, config=config)
        except Exception as exc:
            log.info(f"  ⚠️ Cover art download failed: {exc}")
            return None

    def choose_and_download_artwork(self, ctx: "MappingContext", values: list[Any]) -> Path | None:
        if ctx.test_mode or ctx.dry_run:
            return None
        if not ctx.allow_artwork_download:
            return None
        if not ctx.run_dir:
            return None
        candidates: list[str] = []
        for value in values:
            if isinstance(value, list):
                candidates.extend([str(v) for v in value if v])
            elif value:
                candidates.append(str(value))
        tmdb_path = next((c for c in candidates if c), None)
        if not tmdb_path:
            return None
        image_dir = ctx.run_dir / "artwork"
        image_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(tmdb_path).suffix or ".jpg"
        out_path = image_dir / f"{ctx.content_id}{suffix}"
        size = select_image_size(ctx.poster_sizes, ctx.cover_art_size) if ctx.poster_sizes else "original"
        base_url = ctx.image_base_url.rstrip("/") + "/" + size
        config = TMDbImageDownloadConfig(base_url=base_url)
        try:
            return transforms.download_tmdb_image_to_file(str(tmdb_path), out_path, config=config)
        except Exception as exc:
            log.info(f"  ⚠️ Cover art download failed: {exc}")
            return None
