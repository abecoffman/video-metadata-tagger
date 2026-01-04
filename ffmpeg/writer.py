"""ffmpeg wrapper for writing metadata to media files."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Sequence, Union

from logger import get_logger


log = get_logger()


class ResourceBusyError(RuntimeError):
    """Raised when output replacement fails due to a busy file."""


def ffmpeg_write_metadata(
    ffmpeg_path: str,
    input_path: Path,
    tags: Dict[str, Union[str, List[str]]],
    cover_art_path: Path | None,
    ffmpeg_analyzeduration: str | int | None,
    ffmpeg_probe_size: str | int | None,
    log_path: Path | None,
    clear_metadata: bool,
    clear_tags: Sequence[str] | None,
    backup_original: bool,
    backup_path: Path | None,
    backup_suffix: str,
    atomic_replace: bool,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Remux a file and write metadata tags.

    Args:
        ffmpeg_path: Path to ffmpeg binary.
        input_path: Input media file.
        tags: Metadata tags to write.
        cover_art_path: Optional cover art file.
        ffmpeg_analyzeduration: Optional ffmpeg analyzeduration value.
        ffmpeg_probe_size: Optional ffmpeg probesize value.
        log_path: Optional log file for full stderr output.
        clear_metadata: Whether to clear existing metadata before writing.
        clear_tags: Optional metadata keys to blank out even without full clear.
        backup_original: Whether to save a backup of the original file.
        backup_path: Path where the backup should be stored.
        backup_suffix: Suffix appended to backup files.
        atomic_replace: Whether to atomically replace the original file.
        dry_run: Whether to avoid writing output.
        test_mode: Whether to avoid executing ffmpeg.

    Returns:
        True if metadata write succeeds, otherwise False.
    """
    if not tags and not cover_art_path:
        return True

    def split_multi_value(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    def append_log(message: str) -> None:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message)

    def cleanup_stale_tagtmp() -> None:
        pattern = f"{input_path.stem}.tagtmp.*{input_path.suffix}"
        for path in input_path.parent.glob(pattern):
            try:
                path.unlink()
                log.info(f"Removed stale temp file: {path}")
            except OSError as exc:
                log.info(f"Failed to remove stale temp file: {path}: {exc}")
                append_log(f"[ffmpeg] {input_path}\nerror: cleanup failed for {path}: {exc}\n")

    def build_cmd(cover_path: Path | None) -> list[str]:
        cmd = [ffmpeg_path]
        if ffmpeg_analyzeduration is not None:
            cmd += ["-analyzeduration", str(ffmpeg_analyzeduration)]
        if ffmpeg_probe_size is not None:
            cmd += ["-probesize", str(ffmpeg_probe_size)]
        cmd += ["-y", "-i", str(input_path)]
        if cover_path:
            cmd += ["-i", str(cover_path)]
        cmd += ["-map", "0:v:0", "-map", "0:a", "-map", "0:s?"]
        if clear_metadata:
            cmd += ["-map_metadata", "-1", "-map_chapters", "-1"]
        if clear_tags:
            for key in clear_tags:
                cmd += ["-metadata", f"{key}="]
        if cover_path:
            cmd += [
                "-map",
                "1",
                "-disposition:v:1",
                "attached_pic",
                "-metadata:s:v:1",
                "title=cover",
                "-metadata:s:v:1",
                "comment=Cover",
            ]
        cmd += ["-c", "copy"]
        return cmd

    cmd = build_cmd(cover_art_path)
    if clear_tags:
        log.info(f"Clearing metadata fields: {', '.join(clear_tags)}")
        append_log(f"[ffmpeg] {input_path}\nclear_tags: {', '.join(clear_tags)}\n")

    for k, v in tags.items():
        if v == "" or v is None:
            continue
        values: list[str]
        if isinstance(v, list):
            values = [str(item).strip() for item in v if str(item).strip()]
        else:
            values = [str(v).strip()]
        if not values:
            continue
        for item in values:
            if k == "genre":
                for genre in split_multi_value(item):
                    cmd += ["-metadata", f"{k}={genre}"]
                continue
            cmd += ["-metadata", f"{k}={item}"]

    if test_mode:
        tmp_path = input_path.with_name(f"{input_path.stem}.tagtmp{input_path.suffix}")
        cmd += [str(tmp_path)]
        log.info(f"TEST MODE ffmpeg cmd: {' '.join(cmd)}")
        if clear_metadata:
            log.info("TEST MODE would clear existing metadata")
        if backup_original and backup_path:
            log.info(f"TEST MODE would backup original to: {backup_path}")
        if atomic_replace:
            log.info("TEST MODE would atomically replace original with temp output")
        else:
            log.info("TEST MODE would move temp output over original")
        return True

    cleanup_stale_tagtmp()
    tmp_dir = str(input_path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=input_path.stem + ".tagtmp.", suffix=input_path.suffix, dir=tmp_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)

    cmd += [str(tmp_path)]

    if dry_run:
        log.info(f"DRY RUN ffmpeg cmd: {' '.join(cmd)}")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return True

    def should_retry_without_cover_art(stderr: str) -> bool:
        lowered = stderr.lower()
        return "codec mjpeg" in lowered or "attached pic" in lowered

    def decode_stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
        if isinstance(proc.stderr, (bytes, bytearray)):
            return proc.stderr.decode("utf-8", errors="replace")
        return str(proc.stderr or "")

    try:
        proc = subprocess.run(cmd, capture_output=True)
        stderr_text = decode_stderr(proc)
        if proc.returncode != 0:
            log.info(f"ffmpeg failed for: {input_path}")
            log.info(stderr_text.strip()[:2000])
            append_log(
                f"[ffmpeg] {input_path}\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stderr:\n{stderr_text}\n"
            )
            tmp_path.unlink(missing_ok=True)
            if cover_art_path and should_retry_without_cover_art(stderr_text):
                retry_cmd = build_cmd(None)
                retry_cmd += [str(tmp_path)]
                append_log(f"[ffmpeg] retry without cover art for {input_path}\n")
                proc = subprocess.run(retry_cmd, capture_output=True)
                stderr_text = decode_stderr(proc)
                if proc.returncode != 0:
                    log.info(f"ffmpeg failed for: {input_path}")
                    log.info(stderr_text.strip()[:2000])
                    append_log(
                        f"[ffmpeg] {input_path}\n"
                        f"cmd: {' '.join(retry_cmd)}\n"
                        f"stderr:\n{stderr_text}\n"
                    )
                    tmp_path.unlink(missing_ok=True)
                    return False
                cmd = retry_cmd
            else:
                return False

        if tmp_path.exists() and tmp_path.stat().st_size == 0:
            log.info(f"ffmpeg produced empty output for: {input_path}")
            append_log(f"[ffmpeg] {input_path}\nerror: output file is empty\n")
            tmp_path.unlink(missing_ok=True)
            return False

        if backup_original and backup_path:
            if backup_path.exists():
                backup_path = backup_path.with_name(backup_path.name + backup_suffix)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, backup_path)

        def replace_with_retries(src: Path, dest: Path, use_atomic: bool) -> bool:
            for attempt in range(3):
                try:
                    if use_atomic:
                        src.replace(dest)
                    else:
                        shutil.move(str(src), str(dest))
                    return True
                except OSError as exc:
                    if getattr(exc, "errno", None) != 16:
                        raise
                    time.sleep(0.5 * (attempt + 1))
            return False

        try:
            if not replace_with_retries(tmp_path, input_path, atomic_replace):
                raise ResourceBusyError(f"Resource busy: {tmp_path}")
        except ResourceBusyError as exc:
            log.info(f"Error replacing output for {input_path}: {exc}")
            append_log(f"[ffmpeg] {input_path}\nerror: replace failed: {exc}\n")
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                append_log(f"[ffmpeg] {input_path}\nerror: cleanup failed: {cleanup_exc}\n")
            raise
        except OSError as exc:
            log.info(f"Error replacing output for {input_path}: {exc}")
            append_log(f"[ffmpeg] {input_path}\nerror: replace failed: {exc}\n")
            tmp_path.unlink(missing_ok=True)
            return False

        return True
    except FileNotFoundError:
        log.info(f"Could not find ffmpeg at: {ffmpeg_path}")
        append_log(f"[ffmpeg] {input_path}\nerror: ffmpeg not found at {ffmpeg_path}\n")
        tmp_path.unlink(missing_ok=True)
        return False
    except ResourceBusyError:
        raise
    except Exception as e:
        log.info(f"Error writing metadata for {input_path}: {e}")
        append_log(f"[ffmpeg] {input_path}\nerror: {e}\n")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as exc:
            append_log(f"[ffmpeg] {input_path}\nerror: cleanup failed: {exc}\n")
        return False
