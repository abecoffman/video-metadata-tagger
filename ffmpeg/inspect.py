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


def has_attached_picture(ffprobe_path: str, input_path: Path) -> bool:
    """Return True if the media file has an attached picture stream."""
    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        str(input_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", []) or []
    for stream in streams:
        disposition = stream.get("disposition", {}) or {}
        if disposition.get("attached_pic") == 1:
            return True
    return False


def has_drm_stream(ffprobe_path: str, input_path: Path) -> bool:
    """Return True if the media file appears to use DRM-protected codecs."""
    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        str(input_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", []) or []
    for stream in streams:
        codec_name = str(stream.get("codec_name") or "").lower()
        codec_tag = str(stream.get("codec_tag_string") or "").lower()
        if codec_name in {"drmi", "drms"} or codec_tag in {"drmi", "drms"}:
            return True
    return False


class MediaInspector:
    """Cache-backed ffprobe inspector for a single run."""

    def __init__(self, ffprobe_path: str) -> None:
        self._ffprobe_path = ffprobe_path
        self._format_tags_cache: Dict[Path, Dict[str, str]] = {}
        self._streams_cache: Dict[Path, list[dict]] = {}

    def read_format_tags(self, input_path: Path) -> Dict[str, str]:
        if input_path not in self._format_tags_cache:
            self._format_tags_cache[input_path] = read_format_tags(self._ffprobe_path, input_path)
        return self._format_tags_cache[input_path]

    def _load_streams(self, input_path: Path) -> list[dict]:
        if input_path in self._streams_cache:
            return self._streams_cache[input_path]
        cmd = [
            self._ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(input_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams", []) or []
        self._streams_cache[input_path] = streams
        return streams

    def has_attached_picture(self, input_path: Path) -> bool:
        streams = self._load_streams(input_path)
        for stream in streams:
            disposition = stream.get("disposition", {}) or {}
            if disposition.get("attached_pic") == 1:
                return True
        return False

    def has_drm_stream(self, input_path: Path) -> bool:
        streams = self._load_streams(input_path)
        for stream in streams:
            codec_name = str(stream.get("codec_name") or "").lower()
            codec_tag = str(stream.get("codec_tag_string") or "").lower()
            if codec_name in {"drmi", "drms"} or codec_tag in {"drmi", "drms"}:
                return True
        return False
