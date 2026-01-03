"""AtomicParsley wrapper for writing metadata to MP4/M4V files."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict

import ffmpeg.inspect as inspect_module
from ffmpeg.writer import ResourceBusyError
from logger import get_logger

log = get_logger()


_TAG_MAP = {
    "title": "--title",
    "artist": "--artist",
    "album_artist": "--albumArtist",
    "album": "--album",
    "genre": "--genre",
    "year": "--year",
    "comment": "--comment",
    "description": "--description",
    "longdesc": "--longdesc",
}


def _decode_stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
    if isinstance(proc.stderr, (bytes, bytearray)):
        return proc.stderr.decode("utf-8", errors="replace")
    return str(proc.stderr or "")


def atomicparsley_write_metadata(
    atomicparsley_path: str,
    input_path: Path,
    tags: Dict[str, str],
    cover_art_path: Path | None,
    remove_existing_artwork: bool,
    rdns_namespace: str,
    log_path: Path | None,
    backup_original: bool,
    backup_path: Path | None,
    backup_suffix: str,
    atomic_replace: bool,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Write metadata using AtomicParsley."""
    if not tags and not cover_art_path:
        return True

    def append_log(message: str) -> None:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message)

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

    def run_atomicparsley(cmd: list[str], tmp_path: Path, action: str) -> bool:
        log.info(f"AtomicParsley: {action} for {input_path}")
        proc = subprocess.run(cmd, capture_output=True)
        stderr_text = _decode_stderr(proc)
        if proc.returncode != 0:
            log.info(f"AtomicParsley failed for: {input_path}")
            log.info(stderr_text.strip()[:2000])
            append_log(
                f"[atomicparsley] {input_path}\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stderr:\n{stderr_text}\n"
            )
            tmp_path.unlink(missing_ok=True)
            return False
        if not replace_with_retries(tmp_path, input_path, atomic_replace):
            raise ResourceBusyError(f"Resource busy: {tmp_path}")
        log.info(f"AtomicParsley: {action} complete for {input_path}")
        return True

    def remove_artwork() -> None:
        if not cover_art_path or not remove_existing_artwork:
            return
        if not has_artwork and not test_mode and not dry_run:
            log.info("  Existing artwork not detected; skipping removal")
            return
        if test_mode:
            log.info("TEST MODE would remove existing artwork")
            return
        if dry_run:
            log.info("DRY RUN would remove existing artwork")
            return
        attempts = [
            ["--artwork", "REMOVE_ALL"],
        ]
        for args in attempts:
            fd, tmp_name = tempfile.mkstemp(
                prefix=input_path.stem + ".tagtmp.", suffix=input_path.suffix, dir=str(input_path.parent)
            )
            os.close(fd)
            tmp_path = Path(tmp_name)
            cmd = [atomicparsley_path, str(input_path), "--output", str(tmp_path)] + args
            try:
                if run_atomicparsley(cmd, tmp_path, "remove artwork"):
                    log.info("  Removed existing artwork before writing new cover")
                    return
            except ResourceBusyError:
                append_log(f"[atomicparsley] {input_path}\nerror: resource busy while removing artwork\n")
                raise
        log.info("  ⚠️ Unable to remove existing artwork; proceeding to add new cover art")

    has_artwork = False
    if remove_existing_artwork and (test_mode or dry_run):
        has_artwork = True
    elif remove_existing_artwork:
        try:
            ffprobe_path = inspect_module.resolve_ffprobe_path(atomicparsley_path)
            has_artwork = inspect_module.has_attached_picture(ffprobe_path, input_path)
        except Exception:
            has_artwork = True
    remove_artwork()

    fd, tmp_name = tempfile.mkstemp(prefix=input_path.stem + ".tagtmp.", suffix=input_path.suffix, dir=str(input_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)

    cmd = [atomicparsley_path, str(input_path), "--output", str(tmp_path)]
    normalized_namespace = rdns_namespace.strip()
    for key, value in tags.items():
        flag = _TAG_MAP.get(key)
        if not flag or not value:
            continue
        cmd += [flag, str(value)]
    if normalized_namespace:
        for key, value in tags.items():
            if key in _TAG_MAP or not value:
                continue
            rdns_name = f"{normalized_namespace}:{key}"
            cmd += ["--rDNSatom", rdns_name, str(value), "1"]
    if cover_art_path:
        cmd += ["--artwork", str(cover_art_path)]

    if test_mode:
        log.info(f"TEST MODE AtomicParsley cmd: {' '.join(cmd)}")
        if backup_original and backup_path:
            log.info(f"TEST MODE would backup original to: {backup_path}")
        if atomic_replace:
            log.info("TEST MODE would atomically replace original with temp output")
        else:
            log.info("TEST MODE would move temp output over original")
        tmp_path.unlink(missing_ok=True)
        return True

    if dry_run:
        log.info(f"DRY RUN AtomicParsley cmd: {' '.join(cmd)}")
        tmp_path.unlink(missing_ok=True)
        return True

    try:
        if not run_atomicparsley(cmd, tmp_path, "write metadata"):
            return False

        if backup_original and backup_path:
            if backup_path.exists():
                backup_path = backup_path.with_name(backup_path.name + backup_suffix)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, backup_path)
        return True
    except ResourceBusyError:
        append_log(f"[atomicparsley] {input_path}\nerror: resource busy while replacing output\n")
        tmp_path.unlink(missing_ok=True)
        raise
    except FileNotFoundError:
        log.info(f"Could not find AtomicParsley at: {atomicparsley_path}")
        append_log(f"[atomicparsley] {input_path}\nerror: AtomicParsley not found at {atomicparsley_path}\n")
        tmp_path.unlink(missing_ok=True)
        return False
    except Exception as e:
        log.info(f"Error writing metadata for {input_path}: {e}")
        append_log(f"[atomicparsley] {input_path}\nerror: {e}\n")
        tmp_path.unlink(missing_ok=True)
        return False
