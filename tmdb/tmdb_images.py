"""TMDb image configuration and download helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import requests

from tmdb.tmdb_client import tmdb_request


def tmdb_configuration(session: requests.Session, api_key: str) -> Dict[str, Any]:
    """Fetch TMDb image configuration.

    Args:
        session: Requests session.
        api_key: TMDb API key.

    Returns:
        Configuration payload.
    """
    return tmdb_request(session, api_key, "/configuration", {})


def select_image_size(available: List[str], preferred: str) -> str:
    """Select the best image size.

    Args:
        available: Available sizes from TMDb.
        preferred: Preferred size to use.

    Returns:
        Selected size.
    """
    if preferred in available:
        return preferred
    if "original" in available:
        return "original"
    if available:
        return available[-1]
    return preferred


def build_image_url(base_url: str, size: str, path: str) -> str:
    """Build a full image URL.

    Args:
        base_url: Base URL from TMDb config.
        size: Image size.
        path: Image path (e.g. /poster.jpg).

    Returns:
        Full URL string.
    """
    if not base_url or not size or not path:
        return ""
    base = base_url if base_url.endswith("/") else (base_url + "/")
    size_part = size[1:] if size.startswith("/") else size
    return f"{base}{size_part}{path}"


def download_cover_art(session: requests.Session, url: str, suffix: str) -> Path | None:
    """Download cover art to a temporary file.

    Args:
        session: Requests session.
        url: Image URL.
        suffix: File suffix for the temp file.

    Returns:
        Path to the downloaded file, or None on failure.
    """
    if not url:
        return None
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        fd, tmp_name = tempfile.mkstemp(prefix="cover.", suffix=suffix or ".jpg")
        os.close(fd)
        tmp_path = Path(tmp_name)
        tmp_path.write_bytes(resp.content)
        return tmp_path
    except requests.RequestException as e:
        print(f"  ❌ Failed to download cover art: {e}")
        return None
