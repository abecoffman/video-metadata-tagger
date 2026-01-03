"""Inspect movie files for missing metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from config import Config
from ffmpeg.backups import create_run_backup_dir
from ffmpeg.inspect import read_format_tags, resolve_ffprobe_path
from file_io.scanner import find_movie_files, normalize_extensions


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


def _select_files(
    root: Path,
    single_file: Path | None,
    extensions: list[str],
    ignore_substrings: list[str],
    max_files: int,
) -> list[Path]:
    if single_file:
        return [single_file]
    allowed_exts = normalize_extensions(extensions)
    return find_movie_files(root, allowed_exts, ignore_substrings, max_files)


def inspect(root: Path, file_path: Path | None, cfg: Config, only_exts: list[str], log_path: Path | None) -> InspectReport:
    """Inspect files for missing metadata and write a log report."""
    exts = only_exts or cfg.scan.extensions
    files = _select_files(
        root,
        file_path,
        exts,
        cfg.scan.ignore_substrings,
        cfg.scan.max_files,
    )
    print(f"Found {len(files)} file(s).")
    log_file = _resolve_log_path(log_path, cfg)
    required = list(cfg.serialization.mappings.keys())
    ffprobe_path = resolve_ffprobe_path(cfg.write.ffmpeg_path)

    total_missing = 0
    files_with_missing = 0
    with log_file.open("w", encoding="utf-8") as handle:
        for movie_path in files:
            try:
                tags = read_format_tags(ffprobe_path, movie_path)
                missing = find_missing_tags(tags, required)
            except Exception as exc:  # pragma: no cover - bubble up as log line
                handle.write(f"ERROR reading metadata: {movie_path} ({exc})\n")
                continue

            if missing:
                files_with_missing += 1
                total_missing += len(missing)
                handle.write(f"Missing tags: {', '.join(missing)} — {movie_path}\n")
            else:
                handle.write(f"OK: {movie_path}\n")

    print(f"Missing metadata in {files_with_missing} file(s).")
    print(f"Log written to: {log_file}")
    return InspectReport(
        total_files=len(files),
        files_with_missing=files_with_missing,
        total_missing_fields=total_missing,
    )
