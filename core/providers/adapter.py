"""Provider adapter interfaces for mapping."""

from __future__ import annotations

from typing import Any, Dict, Protocol, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from core.mapping_engine import MappingContext


class MappingProvider(Protocol):
    """Provider adapter for mapping engine interactions."""

    name: str

    def fetch_payloads(
        self,
        plan: Dict[str, Any],
        ctx: "MappingContext",
        base_payload: Dict[str, Any],
        base_endpoint: str,
    ) -> Dict[str, Any]:
        """Return payloads for endpoints referenced by the plan."""

    def download_artwork(self, ctx: "MappingContext", path: str) -> Path | None:
        """Download a single artwork path to a local file."""

    def choose_and_download_artwork(self, ctx: "MappingContext", values: list[Any]) -> Path | None:
        """Choose from multiple artwork candidates and download one."""
