"""FFprobe helpers for reading existing metadata."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict


def resolve_ffprobe_path(ffmpeg_path: str) -> str:
    """Resolve an ffprobe path from an ffmpeg path."""
    ffmpeg_candidate = Path(ffmpeg_path)
    if ffmpeg_candidate.name == "ffmpeg":
        return str(ffmpeg_candidate.with_name("ffprobe"))
    return "ffprobe"


def read_format_tags(ffprobe_path: str, input_path: Path) -> Dict[str, str]:
    """Read format tags from a media file using ffprobe."""
    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_entries",
        "format_tags",
        str(input_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    data = json.loads(proc.stdout or "{}")
    tags = data.get("format", {}).get("tags", {}) or {}
    normalized: Dict[str, str] = {}
    for key, value in tags.items():
        normalized[str(key).lower()] = str(value)
    return normalized
