"""Inspect movie files for missing metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from config import Config
from ffmpeg.backups import create_run_backup_dir
from ffmpeg.inspect import MediaInspector, resolve_ffprobe_path
from core.services.file_selection import select_files


@dataclass
class InspectReport:
    """Summary of an inspection run."""

    total_files: int
    files_with_missing: int
    total_missing_fields: int


def _required_keys(required: Iterable[str]) -> List[str]:
    return [str(key).lower() for key in required if str(key).strip()]


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
    print(f"Found {len(files)} file(s).")
    log_file = _resolve_log_path(log_path, cfg)
    required = list(cfg.serialization.mappings.keys())
    ffprobe_path = resolve_ffprobe_path(cfg.write.ffmpeg_path)
    inspector = MediaInspector(ffprobe_path)
    check_artwork = cfg.write.cover_art_enabled

    total_missing = 0
    files_with_missing = 0
    with log_file.open("w", encoding="utf-8") as handle:
        for movie_path in files:
            try:
                tags = inspector.read_format_tags(movie_path)
                missing = find_missing_tags(tags, required)
                if check_artwork and not inspector.has_attached_picture(movie_path):
                    if "artwork" not in missing:
                        missing.append("artwork")
            except Exception as exc:  # pragma: no cover - bubble up as log line
                line = f"ERROR reading metadata: {movie_path} ({exc})"
                print(line)
                handle.write(f"{line}\n")
                continue

            if missing:
                files_with_missing += 1
                total_missing += len(missing)
                line = f"Missing tags: {', '.join(missing)} — {movie_path}"
                print(line)
                handle.write(f"{line}\n")
            else:
                line = f"OK: {movie_path}"
                print(line)
                handle.write(f"{line}\n")

    print(f"Missing metadata in {files_with_missing} file(s).")
    print(f"Log written to: {log_file}")
    return InspectReport(
        total_files=len(files),
        files_with_missing=files_with_missing,
        total_missing_fields=total_missing,
    )
