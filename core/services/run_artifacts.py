"""Run artifact helpers (logs, manifests, backup dirs)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from ffmpeg.backups import create_run_backup_dir


def cleanup_run_dirs(base_dir: Path, max_logs: int) -> None:
    """Delete old log directories beyond the retention limit."""
    if max_logs <= 0 or not base_dir.exists():
        return
    dirs = [entry for entry in base_dir.iterdir() if entry.is_dir()]
    dirs.sort(key=lambda entry: entry.name)
    excess = len(dirs) - max_logs
    if excess <= 0:
        return
    for entry in dirs[:excess]:
        shutil.rmtree(entry, ignore_errors=True)


@dataclass
class RunDirs:
    """Paths for run artifacts."""

    run_backup_dir: Path | None
    run_manifest_path: Path | None
    run_log_path: Path | None


def manifest_path_for_rerun(rerun_failed: Path) -> Path:
    """Resolve the manifest path for a rerun option."""
    if rerun_failed.is_dir():
        return rerun_failed / "manifest.jsonl"
    return rerun_failed


def load_failed_from_manifest(path: Path) -> list[Path]:
    """Load failed file paths from a run manifest."""
    if not path.exists():
        print(f"Run manifest not found: {path}")
        return []
    failed: list[Path] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("status") != "failed":
            continue
        value = record.get("path")
        if not value:
            continue
        failed.append(Path(value))
    return failed


def write_manifest_record(path: Path, record: Dict[str, object]) -> None:
    """Append a record to the run manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def append_run_log(log_path: Path | None, message: str) -> None:
    """Append a line to the run log."""
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line for line in message.splitlines() if line.strip()]
    if not lines:
        return
    with log_path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(f"- {line}\n")


def write_log_header(log_path: Path, run_dir: Path) -> None:
    """Write a header for a new log file."""
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        f.write("Video Metadata Tagger Log\n")
        f.write(f"Started: {started}\n")
        f.write(f"Run Directory: {run_dir}\n")
        f.write("\nSummary\n")


def write_log_summary(log_path: Path | None, ok: int, skipped: int, failed: int, notes: list[str]) -> None:
    """Append a summary section to the log."""
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"Updated/Processed: {ok}\n")
        f.write(f"Skipped:           {skipped}\n")
        f.write(f"Failed:            {failed}\n")
        if notes:
            f.write("\nNotes\n")
            for note in notes:
                f.write(f"- {note}\n")


def setup_run_dirs(
    restore_backup: Path | None,
    backup_dir: Path,
    test_mode: bool,
    max_logs: int,
) -> RunDirs | None:
    """Initialize run directories for logs and manifests."""
    if restore_backup:
        if not restore_backup.exists() or not restore_backup.is_dir():
            print(f"Backup directory not found: {restore_backup}")
            return None
        return RunDirs(None, None, None)

    if test_mode:
        return RunDirs(None, None, None)

    run_backup_dir = create_run_backup_dir(backup_dir)
    log_path = run_backup_dir / f"{run_backup_dir.name}.log"
    write_log_header(log_path, run_backup_dir)
    cleanup_run_dirs(backup_dir, max_logs)
    return RunDirs(run_backup_dir, run_backup_dir / "manifest.jsonl", log_path)
