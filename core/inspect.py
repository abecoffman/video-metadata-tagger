"""Inspect movie files for missing metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
import re

from config import Config
from ffmpeg.backups import create_run_backup_dir
from ffmpeg.inspect import MediaInspector, resolve_ffprobe_path
from core.services.file_selection import select_files
from logger import get_logger


@dataclass
class InspectReport:
    """Summary of an inspection run."""

    total_files: int
    files_with_missing: int
    total_missing_fields: int


def _required_keys(required: Iterable[str]) -> List[str]:
    return [str(key).lower() for key in required if str(key).strip()]


_ITUNES_TAG_ALIASES = {
    "\u00a9nam": "title",
    "\u00a9day": "date",
    "\u00a9gen": "genre",
    "\u00a9cmt": "comment",
    "desc": "description",
    "ldes": "description",
    "\u00a9alb": "album",
    "\u00a9art": "artist",
    "aart": "album_artist",
}


def _normalize_format_tags(tags: Dict[str, str]) -> Dict[str, str]:
    normalized = dict(tags)
    for raw_key, value in tags.items():
        key = str(raw_key).lower()
        mapped = _ITUNES_TAG_ALIASES.get(key)
        if not mapped:
            continue
        if mapped in normalized and str(normalized.get(mapped, "")).strip():
            continue
        normalized[mapped] = str(value)

    if not str(normalized.get("year", "")).strip():
        date_value = str(normalized.get("date") or "").strip()
        if date_value:
            match = re.search(r"(\d{4})", date_value)
            if match:
                normalized["year"] = match.group(1)

    return normalized


def _extract_rdns_key(tag_key: str, namespace: str) -> str | None:
    key = tag_key.lower()
    ns = namespace.lower().strip()
    if not ns or ns not in key:
        return None
    parts = key.split(":")
    if ns in parts:
        idx = parts.index(ns)
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if f"{ns}:" in key:
        return key.split(f"{ns}:", 1)[1] or None
    return None


def _apply_rdns_tags(
    tags: Dict[str, str], namespace: str, required: Iterable[str]
) -> tuple[Dict[str, str], list[str]]:
    if not namespace:
        return tags, []
    required_keys = set(_required_keys(required))
    if not required_keys:
        return tags, []
    enriched = dict(tags)
    rdns_keys: list[str] = []
    for raw_key, value in tags.items():
        mapped_key = _extract_rdns_key(str(raw_key), namespace)
        if not mapped_key or mapped_key not in required_keys:
            continue
        if mapped_key in enriched and str(enriched.get(mapped_key, "")).strip():
            continue
        enriched[mapped_key] = str(value)
        rdns_keys.append(mapped_key)
    return enriched, rdns_keys


def find_missing_tags(tags: Dict[str, str], required: Iterable[str]) -> List[str]:
    """Return missing tag keys given existing tags."""
    missing: List[str] = []
    required_keys = _required_keys(required)
    for key in required_keys:
        value = tags.get(key)
        if value is None or not str(value).strip():
            missing.append(key)
    return missing


def _resolve_log_path(log_path: Path | None, cfg: Config) -> Path:
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path
    run_dir = create_run_backup_dir(Path(cfg.write.backup_dir))
    return run_dir / "inspect.log"


def inspect(root: Path, file_path: Path | None, cfg: Config, only_exts: list[str], log_path: Path | None) -> InspectReport:
    """Inspect files for missing metadata and write a log report."""
    exts = only_exts or cfg.scan.extensions
    files = select_files(
        rerun_failed=None,
        file_path=file_path,
        root=root,
        exts=exts,
        ignore_substrings=cfg.scan.ignore_substrings,
        max_files=cfg.scan.max_files,
        only_exts=only_exts,
    )
    if files is None:
        return InspectReport(total_files=0, files_with_missing=0, total_missing_fields=0)
    log.info(f"Found {len(files)} file(s).")
    log_file = _resolve_log_path(log_path, cfg)
    required = list(cfg.serialization.mappings.keys())
    if cfg.serialization_tv.mappings:
        required += list(cfg.serialization_tv.mappings.keys())
    ffprobe_path = resolve_ffprobe_path(cfg.write.ffmpeg_path)
    inspector = MediaInspector(ffprobe_path)
    check_artwork = cfg.write.cover_art_enabled
    rdns_namespace = cfg.write.rdns_namespace

    total_missing = 0
    files_with_missing = 0
    with log_file.open("w", encoding="utf-8") as handle:
        for movie_path in files:
            try:
                raw_tags = inspector.read_format_tags(movie_path)
                normalized_tags = _normalize_format_tags(raw_tags)
                missing_before = set(find_missing_tags(normalized_tags, required))
                tags, rdns_keys = _apply_rdns_tags(normalized_tags, rdns_namespace, required)
                missing = find_missing_tags(tags, required)
                if check_artwork:
                    has_artwork = inspector.has_attached_picture(movie_path) or inspector.has_artwork_tag(movie_path)
                    if not has_artwork and "artwork" not in missing:
                        missing.append("artwork")
            except Exception as exc:  # pragma: no cover - bubble up as log line
                line = f"[ERROR] {movie_path} | {exc}"
                log.info(line)
                handle.write(f"{line}\n")
                continue

            rdns_note = ""
            rdns_used = sorted({key for key in rdns_keys if key in missing_before})
            if rdns_used:
                rdns_note = f" (rDNS: {', '.join(rdns_used)})"
            if missing:
                files_with_missing += 1
                total_missing += len(missing)
                missing_list = ", ".join(sorted(missing))
                line = f"[MISSING] {movie_path} | {missing_list}{rdns_note}"
                log.info(line)
                handle.write(f"{line}\n")
            else:
                line = f"[OK] {movie_path}{rdns_note}"
                log.info(line)
                handle.write(f"{line}\n")

    log.info(f"Missing metadata in {files_with_missing} file(s).")
    log.info(f"Log written to: {log_file}")
    return InspectReport(
        total_files=len(files),
        files_with_missing=files_with_missing,
        total_missing_fields=total_missing,
    )
log = get_logger()
