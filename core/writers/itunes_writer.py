"""iTunes-specific metadata writer helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

from core.writers.mp4tags import mp4tags_write_metadata
from core.writers.mutagen_itunmovi import write_itunmovi_atom
from logger import get_logger

log = get_logger()


def write_itunes_metadata(
    *,
    mp4tags_path: str,
    input_path: Path,
    tags: Dict[str, Union[str, List[str]]],
    itunmovi_payload: dict | None,
    log_path: Path | None,
    clear_metadata: bool,
    run_dir: Path | None,
    dry_run: bool,
    test_mode: bool,
) -> bool:
    """Write iTunes-specific metadata using mutagen + mp4tags."""
    wrote = True
    if itunmovi_payload:
        wrote = (
            wrote
            and write_itunmovi_atom(
                input_path=input_path,
                payload=itunmovi_payload,
                run_dir=run_dir,
                log_path=log_path,
                dry_run=dry_run,
                test_mode=test_mode,
            )
        )
    if tags:
        tags = dict(tags)
        tags.pop("iTunMOVI", None)
        wrote = (
            wrote
            and mp4tags_write_metadata(
                mp4tags_path=mp4tags_path,
                input_path=input_path,
                tags=tags,
                log_path=log_path,
                clear_metadata=clear_metadata,
                dry_run=dry_run,
                test_mode=test_mode,
            )
        )
    if not wrote:
        log.info("  ⚠️ Failed writing iTunes-specific metadata")
    return wrote
