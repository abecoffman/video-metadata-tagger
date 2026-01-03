"""Backup helpers for metadata snapshots and file restoration."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def create_run_backup_dir(base_dir: Path, now: datetime | None = None) -> Path:
    """Create a timestamped run directory.

    Args:
        base_dir: Base directory for run artifacts.
        now: Optional datetime override for deterministic tests.

    Returns:
        Path to the created run directory.
    """
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    run_dir = base_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def backup_metadata_path(backup_dir: Path, input_path: Path, root: Path | None) -> Path:
    """Build a metadata backup path for a given file.

    Args:
        backup_dir: Directory to store backups.
        input_path: Original movie file path.
        root: Optional root used to compute a relative path.

    Returns:
        Path for the .ffmeta snapshot.
    """
    if root:
        try:
            rel = input_path.relative_to(root)
        except ValueError:
            rel = input_path.name
    else:
        rel = input_path.name
    rel_str = str(rel)
    safe = rel_str.replace(os.sep, "__")
    return backup_dir / f"{safe}.ffmeta"


def backup_original_path(backup_dir: Path, input_path: Path, root: Path | None, suffix: str) -> Path:
    """Build a backup path for an original media file.

    Args:
        backup_dir: Directory to store backups.
        input_path: Original movie file path.
        root: Optional root used to compute a relative path.
        suffix: Backup suffix to append.

    Returns:
        Path for the backup file.
    """
    if root:
        try:
            rel = input_path.relative_to(root)
        except ValueError:
            rel = input_path.name
    else:
        rel = input_path.name
    rel_str = str(rel)
    safe = rel_str.replace(os.sep, "__")
    return backup_dir / f"{safe}{suffix}"


def ffmpeg_backup_metadata(
    ffmpeg_path: str,
    input_path: Path,
    backup_dir: Path,
    root: Path | None,
    dry_run: bool,
    test_mode: bool,
) -> Path | None:
    """Save a .ffmeta snapshot of the input file.

    Args:
        ffmpeg_path: Path to ffmpeg binary.
        input_path: Movie file path.
        backup_dir: Directory to store backups.
        root: Optional root for relative pathing.
        dry_run: Whether to avoid writing output.
        test_mode: Whether to avoid executing ffmpeg.

    Returns:
        Path to the created .ffmeta file, or None on failure.
    """
    backup_path = backup_metadata_path(backup_dir, input_path, root)
    backup_dir.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg_path, "-y", "-i", str(input_path), "-f", "ffmetadata", str(backup_path)]
    if test_mode:
        print("TEST MODE ffmpeg cmd:", " ".join(cmd))
        print(f"TEST MODE would backup metadata to: {backup_path}")
        return backup_path
    if dry_run:
        print("DRY RUN ffmpeg cmd:", " ".join(cmd))
        return backup_path

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"ffmpeg metadata backup failed for: {input_path}")
            print(proc.stderr.strip()[:2000])
            return None
        return backup_path
    except FileNotFoundError:
        print(f"Could not find ffmpeg at: {ffmpeg_path}")
        return None
    except Exception as e:
        print(f"Error backing up metadata for {input_path}: {e}")
        return None


def ffmpeg_restore_metadata(
    ffmpeg_path: str,
    input_path: Path,
    metadata_path: Path,
    atomic_replace: bool,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Restore metadata from a .ffmeta file.

    Args:
        ffmpeg_path: Path to ffmpeg binary.
        input_path: Movie file path.
        metadata_path: .ffmeta snapshot.
        atomic_replace: Whether to atomically replace the original file.
        dry_run: Whether to avoid writing output.
        test_mode: Whether to avoid executing ffmpeg.

    Returns:
        True on success, False otherwise.
    """
    if not metadata_path.exists():
        print(f"Metadata backup not found: {metadata_path}")
        return False

    tmp_dir = str(input_path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=input_path.stem + ".restore.", suffix=input_path.suffix, dir=tmp_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)

    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-i",
        str(metadata_path),
        "-map_metadata",
        "1",
        "-c",
        "copy",
        str(tmp_path),
    ]
    if test_mode:
        print("TEST MODE ffmpeg cmd:", " ".join(cmd))
        print("TEST MODE would restore metadata from backup")
        tmp_path.unlink(missing_ok=True)
        return True
    if dry_run:
        print("DRY RUN ffmpeg cmd:", " ".join(cmd))
        tmp_path.unlink(missing_ok=True)
        return True

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"ffmpeg restore failed for: {input_path}")
            print(proc.stderr.strip()[:2000])
            tmp_path.unlink(missing_ok=True)
            return False
        if atomic_replace:
            tmp_path.replace(input_path)
        else:
            shutil.move(str(tmp_path), str(input_path))
        return True
    except FileNotFoundError:
        print(f"Could not find ffmpeg at: {ffmpeg_path}")
        tmp_path.unlink(missing_ok=True)
        return False
    except Exception as e:
        print(f"Error restoring metadata for {input_path}: {e}")
        tmp_path.unlink(missing_ok=True)
        return False
