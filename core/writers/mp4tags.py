"""mp4tags wrapper for writing iTunes-style metadata to MP4/M4V files."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Union

from logger import get_logger

log = get_logger()

_TAG_MAP = {
    "title": "-s",
    "comment": "-c",
    "year": "-y",
    "description": "-l",
    "shortdesc": "-m",
    "media_type": "-i",
    "composer": "-w",
}

_SKIP_TAGS = {
    "genre",  # keep genres in ffmpeg for repeated atoms
    "keywords",
    "grouping",
    "director",
    "producer",
    "screenwriter",
    "cast",
    "directors",
    "producers",
    "screenwriters",
    "iTunMOVI",
}


def mp4tags_write_metadata(
    mp4tags_path: str,
    input_path: Path,
    tags: Dict[str, Union[str, List[str]]],
    log_path: Path | None,
    clear_metadata: bool,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Write metadata using mp4tags."""
    if not tags:
        return True

    def append_log(message: str) -> None:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message)

    cmd: list[str] = [mp4tags_path]

    for key, value in tags.items():
        if value is None:
            continue
        if key in _SKIP_TAGS:
            continue
        flag = _TAG_MAP.get(key)
        if not flag:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not str(item).strip():
                continue
            if key == "media_type":
                normalized = str(item).strip().lower().replace(" ", "")
                cmd += [flag, normalized]
                continue
            cmd += [flag, str(item)]

    if clear_metadata:
        log.info("mp4tags: clear_metadata requested (no direct clear flag; relying on ffmpeg pass)")
        append_log(f"[mp4tags] {input_path}\nclear_metadata: requested\n")

    cmd += [str(input_path)]

    if test_mode:
        log.info(f"TEST MODE mp4tags cmd: {' '.join(cmd)}")
        return True
    if dry_run:
        log.info(f"DRY RUN mp4tags cmd: {' '.join(cmd)}")
        return True

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            log.info(f"mp4tags failed for: {input_path}")
            log.info(proc.stderr.strip()[:2000])
            append_log(
                f"[mp4tags] {input_path}\n"
                f"cmd: {' '.join(cmd)}\n"
                f"stderr:\n{proc.stderr}\n"
            )
            return False
        return True
    except FileNotFoundError:
        log.info(f"Could not find mp4tags at: {mp4tags_path}")
        append_log(f"[mp4tags] {input_path}\nerror: mp4tags not found at {mp4tags_path}\n")
        return False
    except Exception as exc:
        log.info(f"Error writing metadata for {input_path}: {exc}")
        append_log(f"[mp4tags] {input_path}\nerror: {exc}\n")
        return False
    finally:
        pass
