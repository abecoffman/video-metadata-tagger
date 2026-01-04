"""Mutagen helper for writing iTunMOVI atoms."""

from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

from mutagen.mp4 import MP4, MP4FreeForm

from logger import get_logger

log = get_logger()


def write_itunmovi_atom(
    input_path: Path,
    payload: dict[str, Any],
    run_dir: Path | None,
    log_path: Path | None,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Write iTunMOVI payload using mutagen."""
    if not payload:
        return True

    def append_log(message: str) -> None:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message)

    plist_bytes = plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False)
    if run_dir:
        out_dir = run_dir / "itunmovi"
        out_dir.mkdir(parents=True, exist_ok=True)
        plist_path = out_dir / f"{input_path.stem}.itunmovi.plist"
        plist_path.write_bytes(plist_bytes)
        log.info(f"iTunMOVI plist written to {plist_path}")
        append_log(f"[itunmovi] {input_path}\nplist: {plist_path}\n")

    if test_mode:
        log.info("TEST MODE would write iTunMOVI atom via mutagen")
        return True
    if dry_run:
        log.info("DRY RUN would write iTunMOVI atom via mutagen")
        return True

    try:
        mp4 = MP4(str(input_path))
        key = "----:com.apple.iTunes:iTunMOVI"
        mp4.tags[key] = [MP4FreeForm(plist_bytes)]
        mp4.save()
        return True
    except Exception as exc:
        log.info(f"mutagen failed writing iTunMOVI for {input_path}: {exc}")
        append_log(f"[itunmovi] {input_path}\nerror: {exc}\n")
        return False


def write_standard_director(
    input_path: Path,
    director: str | list[str] | None,
    log_path: Path | None,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Write the standard MP4 director atom using mutagen."""
    if not director:
        return True

    def append_log(message: str) -> None:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message)

    if isinstance(director, list):
        value = next((item for item in director if str(item).strip()), "")
    else:
        value = str(director).strip()
    if not value:
        return True

    if test_mode:
        log.info("TEST MODE would write director atom via mutagen")
        return True
    if dry_run:
        log.info("DRY RUN would write director atom via mutagen")
        return True

    try:
        mp4 = MP4(str(input_path))
        mp4.tags["\xa9dir"] = [value]
        mp4.save()
        return True
    except Exception as exc:
        log.info(f"mutagen failed writing director for {input_path}: {exc}")
        append_log(f"[director] {input_path}\nerror: {exc}\n")
        return False
