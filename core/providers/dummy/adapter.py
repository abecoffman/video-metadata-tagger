"""Dummy provider adapter for tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from core.providers.adapter import MappingProvider

if TYPE_CHECKING:
    from core.mapping_engine import MappingContext


class DummyMappingProvider(MappingProvider):
    """No-op provider adapter that only returns the base payload."""

    name = "dummy"

    def fetch_payloads(
        self,
        plan: Dict[str, Any],
        ctx: "MappingContext",
        base_payload: Dict[str, Any],
        base_endpoint: str,
    ) -> Dict[str, Any]:
        payloads: Dict[str, Any] = {base_endpoint: base_payload}
        for rule in plan.get("rules", []):
            for source in rule.get("tmdb_sources", []):
                endpoint = str(source.get("endpoint") or "")
                if endpoint and endpoint not in payloads:
                    payloads[endpoint] = {}
        return payloads

    def download_artwork(self, ctx: "MappingContext", path: str) -> Path | None:
        return None

    def choose_and_download_artwork(self, ctx: "MappingContext", values: list[Any]) -> Path | None:
        return None
