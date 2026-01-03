"""Run artifact helpers (logs, manifests, backup dirs)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from ffmpeg.backups import create_run_backup_dir


@dataclass
class RunDirs:
    """Paths for run artifacts."""

    run_backup_dir: Path | None
    run_manifest_path: Path | None
    run_log_path: Path | None


def manifest_path_for_rerun(rerun_failed: Path) -> Path:
    """Resolve the manifest path for a rerun option."""
    if rerun_failed.is_dir():
        return rerun_failed / "run.jsonl"
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
    with log_path.open("a", encoding="utf-8") as f:
        f.write(message)


def setup_run_dirs(restore_backup: Path | None, backup_dir: Path, test_mode: bool) -> RunDirs | None:
    """Initialize run directories for logs and manifests."""
    if restore_backup:
        if not restore_backup.exists() or not restore_backup.is_dir():
            print(f"Backup directory not found: {restore_backup}")
            return None
        return RunDirs(None, None, None)

    if test_mode:
        return RunDirs(None, None, None)

    run_backup_dir = create_run_backup_dir(backup_dir)
    return RunDirs(run_backup_dir, run_backup_dir / "run.jsonl", run_backup_dir / "run.log")
