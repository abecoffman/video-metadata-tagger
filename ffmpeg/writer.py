"""ffmpeg wrapper for writing metadata to media files."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict


def ffmpeg_write_metadata(
    ffmpeg_path: str,
    input_path: Path,
    tags: Dict[str, str],
    cover_art_path: Path | None,
    ffmpeg_analyzeduration: str | int | None,
    ffmpeg_probe_size: str | int | None,
    log_path: Path | None,
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
        backup_original: Whether to save a backup of the original file.
        backup_path: Path where the backup should be stored.
        backup_suffix: Suffix appended to backup files.
        atomic_replace: Whether to atomically replace the original file.
        dry_run: Whether to avoid writing output.
        test_mode: Whether to avoid executing ffmpeg.

    Returns:
        True if metadata write succeeds, otherwise False.
    """
    if not tags:
        return True

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

    for k, v in tags.items():
        if v == "":
            continue
        cmd += ["-metadata", f"{k}={v}"]

    if test_mode:
        tmp_path = input_path.with_name(f"{input_path.stem}.tagtmp{input_path.suffix}")
        cmd += [str(tmp_path)]
        print("TEST MODE ffmpeg cmd:", " ".join(cmd))
        if backup_original and backup_path:
            print(f"TEST MODE would backup original to: {backup_path}")
        if atomic_replace:
            print("TEST MODE would atomically replace original with temp output")
        else:
            print("TEST MODE would move temp output over original")
        return True

    tmp_dir = str(input_path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=input_path.stem + ".tagtmp.", suffix=input_path.suffix, dir=tmp_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)

    cmd += [str(tmp_path)]

    if dry_run:
        print("DRY RUN ffmpeg cmd:", " ".join(cmd))
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return True

    def append_log(message: str) -> None:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message)

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
            print(f"ffmpeg failed for: {input_path}")
            print(stderr_text.strip()[:2000])
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
                    print(f"ffmpeg failed for: {input_path}")
                    print(stderr_text.strip()[:2000])
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

        if backup_original and backup_path:
            if backup_path.exists():
                backup_path = backup_path.with_name(backup_path.name + backup_suffix)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, backup_path)

        if atomic_replace:
            tmp_path.replace(input_path)
        else:
            shutil.move(str(tmp_path), str(input_path))

        return True
    except FileNotFoundError:
        print(f"Could not find ffmpeg at: {ffmpeg_path}")
        append_log(f"[ffmpeg] {input_path}\nerror: ffmpeg not found at {ffmpeg_path}\n")
        tmp_path.unlink(missing_ok=True)
        return False
    except Exception as e:
        print(f"Error writing metadata for {input_path}: {e}")
        append_log(f"[ffmpeg] {input_path}\nerror: {e}\n")
        tmp_path.unlink(missing_ok=True)
        return False
