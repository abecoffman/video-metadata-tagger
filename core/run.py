"""Main execution pipeline for tagging movie files."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import requests

from ffmpeg.backups import (
    backup_metadata_path,
    backup_original_path,
    create_run_backup_dir,
    ffmpeg_backup_metadata,
    ffmpeg_restore_metadata,
)
from cli import RunOptions
from config import Config
from core.matching import clean_filename_for_search
from core.movie_metadata import MovieMetadata
from file_io.scanner import find_movie_files, normalize_extensions
from core.serialization import render_tag_value
from tmdb.tmdb_client import tmdb_movie_details, tmdb_search_best_match
from tmdb.tmdb_images import build_image_url, download_cover_art, select_image_size, tmdb_configuration
from ffmpeg.writer import ffmpeg_write_metadata


def resolve_test_mode(options: RunOptions, cfg: Config) -> str | None:
    """Resolve the effective test mode.

    Args:
        options: Parsed run options.
        cfg: Loaded configuration.

    Returns:
        Test mode string or None.
    """
    if options.test_mode:
        return options.test_mode
    return cfg.write.test_mode


@dataclass
class RunDirs:
    """Paths for run artifacts."""

    run_backup_dir: Path | None
    run_manifest_path: Path | None
    run_log_path: Path | None


@dataclass
class TmdbContext:
    """TMDb session and configuration context."""

    session: requests.Session | None
    api_key: str
    language: str
    include_adult: bool
    min_score: float
    delay: float
    image_base_url: str
    poster_sizes: list[str]
    cover_art_enabled: bool


def _manifest_path_for_rerun(rerun_failed: Path) -> Path:
    """Resolve the manifest path for a rerun option.

    Args:
        rerun_failed: Path to a run directory or manifest file.

    Returns:
        Path to the JSONL manifest.
    """
    if rerun_failed.is_dir():
        return rerun_failed / "run.jsonl"
    return rerun_failed


def _load_failed_from_manifest(path: Path) -> list[Path]:
    """Load failed file paths from a run manifest.

    Args:
        path: Path to the JSONL manifest.

    Returns:
        List of failed file paths.
    """
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


def _write_manifest_record(path: Path, record: Dict[str, object]) -> None:
    """Append a record to the run manifest.

    Args:
        path: Manifest path.
        record: Record payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _append_run_log(log_path: Path | None, message: str) -> None:
    """Append a line to the run log.

    Args:
        log_path: Log path, or None to disable logging.
        message: Message to append.
    """
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(message)


def _select_files(
    options: RunOptions,
    exts: list[str],
    ignore_substrings: list[str],
    max_files: int,
) -> list[Path] | None:
    """Select files based on CLI options and scan rules.

    Args:
        options: Parsed run options.
        exts: Normalized extensions.
        ignore_substrings: Substrings to ignore.
        max_files: Max files to return.

    Returns:
        List of files, empty list, or None on configuration error.
    """
    if options.rerun_failed:
        manifest_path = _manifest_path_for_rerun(options.rerun_failed)
        files = _load_failed_from_manifest(manifest_path)
        if not files:
            print("No failed files found in manifest.")
            return []
    elif options.file:
        files = [options.file]
    else:
        if not options.root:
            print("No root directory configured.")
            return None
        files = find_movie_files(options.root, exts, ignore_substrings, max_files)

    if options.only_exts:
        files = [path for path in files if path.suffix.lower() in options.only_exts]
    return files


def _setup_run_dirs(options: RunOptions, backup_dir: Path, test_mode: bool) -> RunDirs | None:
    """Initialize run directories for logs and manifests.

    Args:
        options: Parsed run options.
        backup_dir: Base directory for run artifacts.
        test_mode: Whether test mode is active.

    Returns:
        RunDirs or None if configuration is invalid.
    """
    if options.restore_backup:
        if not options.restore_backup.exists() or not options.restore_backup.is_dir():
            print(f"Backup directory not found: {options.restore_backup}")
            return None
        return RunDirs(None, None, None)

    if test_mode:
        return RunDirs(None, None, None)

    run_backup_dir = create_run_backup_dir(backup_dir)
    return RunDirs(run_backup_dir, run_backup_dir / "run.jsonl", run_backup_dir / "run.log")


def _init_tmdb(
    cfg: Config,
    cover_art_enabled: bool,
    write_enabled: bool,
    test_mode_setting: str | None,
    restore_backup: bool,
) -> tuple[TmdbContext, str | None]:
    """Initialize TMDb session and image configuration.

    Args:
        cfg: Loaded config.
        cover_art_enabled: Whether cover art is enabled.
        write_enabled: Whether write mode is enabled.
        test_mode_setting: Current test mode.
        restore_backup: Whether restore mode is active.

    Returns:
        Tuple of (TmdbContext, error_message).
    """
    if restore_backup:
        return (
            TmdbContext(
                session=None,
                api_key="",
                language="",
                include_adult=False,
                min_score=0.0,
                delay=0.0,
                image_base_url="",
                poster_sizes=[],
                cover_art_enabled=cover_art_enabled,
            ),
            None,
        )

    api_key_env = cfg.tmdb.api_key_env
    api_key = cfg.tmdb.api_key or os.environ.get(api_key_env, "")
    if not api_key:
        return (
            TmdbContext(
                session=None,
                api_key="",
                language="",
                include_adult=False,
                min_score=0.0,
                delay=0.0,
                image_base_url="",
                poster_sizes=[],
                cover_art_enabled=cover_art_enabled,
            ),
            f"TMDb API key missing. Set env var {api_key_env} or add tmdb.api_key to config.",
        )

    language = cfg.tmdb.language
    include_adult = bool(cfg.tmdb.include_adult)
    min_score = float(cfg.tmdb.min_score)
    delay = float(cfg.tmdb.request_delay_seconds)
    session = requests.Session()
    image_base_url = ""
    poster_sizes: list[str] = []

    if cover_art_enabled and (write_enabled or test_mode_setting == "verbose"):
        config_data = tmdb_configuration(session, api_key)
        images = config_data.get("images", {}) if isinstance(config_data, dict) else {}
        image_base_url = str(images.get("secure_base_url") or images.get("base_url") or "")
        poster_sizes = list(images.get("poster_sizes") or [])
        if not image_base_url or not poster_sizes:
            print("Cover art disabled: TMDb image configuration missing.")
            cover_art_enabled = False

    return (
        TmdbContext(
            session=session,
            api_key=api_key,
            language=language,
            include_adult=include_adult,
            min_score=min_score,
            delay=delay,
            image_base_url=image_base_url,
            poster_sizes=poster_sizes,
            cover_art_enabled=cover_art_enabled,
        ),
        None,
    )


def run(options: RunOptions, cfg: Config) -> int:
    """Execute the tagging run based on options and config.

    Args:
        options: Parsed run options.
        cfg: Loaded configuration.

    Returns:
        Process exit code.
    """
    exts = normalize_extensions(cfg.scan.extensions)
    ignore_substrings = list(cfg.scan.ignore_substrings)
    max_files = int(cfg.scan.max_files or 0)

    strip_tokens = list(cfg.matching.strip_tokens)
    prefer_year = bool(cfg.matching.prefer_year_from_filename)

    write_cfg = cfg.write
    write_enabled = bool(write_cfg.enabled)
    dry_run = bool(write_cfg.dry_run)
    backup_original = bool(write_cfg.backup_original)
    backup_suffix = str(write_cfg.backup_suffix)
    backup_dir = Path(write_cfg.backup_dir).expanduser()
    cover_art_enabled = bool(write_cfg.cover_art_enabled)
    cover_art_size = str(write_cfg.cover_art_size)
    ffmpeg_path = str(write_cfg.ffmpeg_path)
    ffmpeg_analyzeduration = write_cfg.ffmpeg_analyzeduration
    ffmpeg_probe_size = write_cfg.ffmpeg_probe_size
    atomic_replace = bool(write_cfg.atomic_replace)
    test_mode_setting = resolve_test_mode(options, cfg)
    test_mode = bool(test_mode_setting)
    full_log = test_mode_setting != "basic"

    if test_mode:
        print(f"TEST MODE enabled ({test_mode_setting}): no files will be modified.\n")

    if not exts:
        print("No file extensions configured. Add scan.extensions in config.")
        return 2
    if options.file and options.file.suffix.lower() not in exts:
        print(f"File extension not configured for scan: {options.file.suffix}")
        return 2

    if not test_mode:
        backup_dir.mkdir(parents=True, exist_ok=True)

    files = _select_files(options, exts, ignore_substrings, max_files)
    if files is None:
        return 2
    if not files:
        print("No movie files found.")
        return 0

    print(f"Found {len(files)} file(s).")
    if not write_enabled:
        print("NOTE: write.enabled is false; will only fetch & print metadata.\n")

    run_dirs = _setup_run_dirs(options, backup_dir, test_mode)
    if run_dirs is None:
        return 2

    tmdb_ctx, tmdb_error = _init_tmdb(
        cfg,
        cover_art_enabled,
        write_enabled,
        test_mode_setting,
        bool(options.restore_backup),
    )
    if tmdb_error:
        print(tmdb_error)
        return 2

    run_backup_dir = run_dirs.run_backup_dir
    run_manifest_path = run_dirs.run_manifest_path
    run_log_path = run_dirs.run_log_path

    cover_art_enabled = tmdb_ctx.cover_art_enabled

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for idx, path in enumerate(files, 1):
        stat = None
        try:
            stat = path.stat()
        except FileNotFoundError:
            print(f"\n[{idx}/{len(files)}] {path}")
            print("  ❌ File missing (skipping).")
            fail_count += 1
            if run_manifest_path:
                _write_manifest_record(
                    run_manifest_path,
                    {
                        "path": str(path),
                        "status": "failed",
                        "reason": "missing_file",
                        "mtime": None,
                        "size": None,
                    },
                )
            continue
        stem = path.stem
        title_guess, year_guess = clean_filename_for_search(stem, strip_tokens)
        if not prefer_year:
            year_guess = None

        print(f"\n[{idx}/{len(files)}] {path}")
        if options.restore_backup:
            print("  Restore: using backup metadata")
        else:
            if full_log:
                print(f"  Guess: title='{title_guess}' year={year_guess}")

        try:
            if options.restore_backup:
                metadata_path = backup_metadata_path(options.restore_backup, path, options.root)
                restored = ffmpeg_restore_metadata(
                    ffmpeg_path=ffmpeg_path,
                    input_path=path,
                    metadata_path=metadata_path,
                    atomic_replace=atomic_replace,
                    dry_run=dry_run,
                    test_mode=test_mode,
                )
                if restored:
                    print("  ✅ Restored metadata from backup")
                    ok_count += 1
                    status = "ok"
                    reason = "restored"
                else:
                    print("  ❌ Failed to restore metadata")
                    fail_count += 1
                    status = "failed"
                    reason = "restore_failed"
                    _append_run_log(run_log_path, f"[restore] {path}\nerror: failed to restore\n")
                if run_manifest_path:
                    _write_manifest_record(
                        run_manifest_path,
                        {
                            "path": str(path),
                            "status": status,
                            "reason": reason,
                            "tmdb_id": None,
                            "title": None,
                            "mtime": stat.st_mtime if stat else None,
                            "size": stat.st_size if stat else None,
                        },
                    )
                continue

            best = tmdb_search_best_match(
                session=tmdb_ctx.session,
                api_key=tmdb_ctx.api_key,
                title=title_guess,
                year=year_guess,
                language=tmdb_ctx.language,
                include_adult=tmdb_ctx.include_adult,
                min_score=tmdb_ctx.min_score,
            )
            time.sleep(tmdb_ctx.delay)

            if not best:
                print("  TMDb: no confident match found (skipping).")
                skip_count += 1
                if run_manifest_path:
                    _write_manifest_record(
                        run_manifest_path,
                        {
                            "path": str(path),
                            "status": "skipped",
                            "reason": "no_match",
                            "tmdb_id": None,
                            "title": None,
                            "mtime": stat.st_mtime if stat else None,
                            "size": stat.st_size if stat else None,
                        },
                    )
                continue

            movie_id = int(best["id"])
            details = tmdb_movie_details(tmdb_ctx.session, tmdb_ctx.api_key, movie_id, tmdb_ctx.language)
            time.sleep(tmdb_ctx.delay)

            metadata = MovieMetadata.from_tmdb(details, cfg.serialization.max_overview_length)
            ctx = metadata.to_context()
            if not full_log:
                print(f"  Movie: {metadata.title} ({metadata.release_year})")
            else:
                print(f"  TMDb: matched '{metadata.title}' ({metadata.release_year}) id={metadata.tmdb_id}")
            if full_log:
                print("  TMDb metadata:")
                print(json.dumps(details, indent=2, sort_keys=True))

            tags_to_write: Dict[str, str] = {}
            for ffkey, template in cfg.serialization.mappings.items():
                val = render_tag_value(str(template), ctx)
                if val:
                    tags_to_write[str(ffkey)] = val

            if not tags_to_write:
                print("  No tags produced from config mappings (skipping write).")
                skip_count += 1
                if run_manifest_path:
                    _write_manifest_record(
                        run_manifest_path,
                        {
                            "path": str(path),
                            "status": "skipped",
                            "reason": "no_tags",
                            "tmdb_id": metadata.tmdb_id,
                            "title": metadata.title,
                            "mtime": stat.st_mtime if stat else None,
                            "size": stat.st_size if stat else None,
                        },
                    )
                continue

            if full_log:
                print("  Tags:")
                for k, v in tags_to_write.items():
                    preview = v if len(v) <= 120 else (v[:117] + "...")
                    print(f"    - {k}: {preview}")

            cover_art_path = None
            cover_url = ""
            if cover_art_enabled:
                poster_path = str(details.get("poster_path") or "")
                if poster_path and tmdb_ctx.image_base_url:
                    size = select_image_size(tmdb_ctx.poster_sizes, cover_art_size)
                    cover_url = build_image_url(tmdb_ctx.image_base_url, size, poster_path)
                if full_log:
                    if cover_url:
                        print(f"  Cover art: {cover_url}")
                    else:
                        print("  Cover art: none")

            if write_enabled:
                original_backup_path = None
                if backup_original and run_backup_dir:
                    original_backup_path = backup_original_path(
                        run_backup_dir,
                        path,
                        options.root,
                        backup_suffix,
                    )
                if cover_art_enabled and cover_url and not test_mode:
                    cover_art_path = download_cover_art(
                        session=tmdb_ctx.session,
                        url=cover_url,
                        suffix=Path(cover_url).suffix or ".jpg",
                    )
                if run_backup_dir:
                    backup_path = ffmpeg_backup_metadata(
                        ffmpeg_path=ffmpeg_path,
                        input_path=path,
                        backup_dir=run_backup_dir,
                        root=options.root,
                        dry_run=dry_run,
                        test_mode=test_mode,
                    )
                    if backup_path:
                        print(f"  Backup: metadata saved to {backup_path}")
                wrote = ffmpeg_write_metadata(
                    ffmpeg_path=ffmpeg_path,
                    input_path=path,
                    tags=tags_to_write,
                    cover_art_path=cover_art_path,
                    ffmpeg_analyzeduration=ffmpeg_analyzeduration,
                    ffmpeg_probe_size=ffmpeg_probe_size,
                    log_path=run_log_path,
                    backup_original=backup_original,
                    backup_path=original_backup_path,
                    backup_suffix=backup_suffix,
                    atomic_replace=atomic_replace,
                    dry_run=dry_run,
                    test_mode=test_mode,
                )
                if cover_art_path:
                    cover_art_path.unlink(missing_ok=True)
                if wrote:
                    print("  ✅ Updated metadata")
                    ok_count += 1
                    status = "ok"
                    reason = "updated"
                else:
                    print("  ❌ Failed to update metadata")
                    fail_count += 1
                    status = "failed"
                    reason = "ffmpeg_failed"
                if run_manifest_path:
                    _write_manifest_record(
                        run_manifest_path,
                        {
                            "path": str(path),
                            "status": status,
                            "reason": reason,
                            "tmdb_id": metadata.tmdb_id,
                            "title": metadata.title,
                            "mtime": stat.st_mtime if stat else None,
                            "size": stat.st_size if stat else None,
                        },
                    )
            else:
                ok_count += 1
                if run_manifest_path:
                    _write_manifest_record(
                        run_manifest_path,
                        {
                            "path": str(path),
                            "status": "ok",
                            "reason": "write_disabled",
                            "tmdb_id": metadata.tmdb_id,
                            "title": metadata.title,
                            "mtime": stat.st_mtime if stat else None,
                            "size": stat.st_size if stat else None,
                        },
                    )

        except requests.HTTPError as e:
            print(f"  ❌ TMDb HTTP error: {e}")
            fail_count += 1
            _append_run_log(run_log_path, f"[tmdb] {path}\nerror: {e}\n")
            if run_manifest_path:
                _write_manifest_record(
                    run_manifest_path,
                    {
                        "path": str(path),
                        "status": "failed",
                        "reason": f"tmdb_http_error: {e}",
                        "tmdb_id": None,
                        "title": None,
                        "mtime": stat.st_mtime if stat else None,
                        "size": stat.st_size if stat else None,
                    },
                )
        except Exception as e:
            print(f"  ❌ Error: {e}")
            fail_count += 1
            _append_run_log(run_log_path, f"[error] {path}\nerror: {e}\n")
            if run_manifest_path:
                _write_manifest_record(
                    run_manifest_path,
                    {
                        "path": str(path),
                        "status": "failed",
                        "reason": f"error: {e}",
                        "tmdb_id": None,
                        "title": None,
                        "mtime": stat.st_mtime if stat else None,
                        "size": stat.st_size if stat else None,
                    },
                )

    print("\nDone.")
    print(f"  Updated/Processed: {ok_count}")
    print(f"  Skipped:           {skip_count}")
    print(f"  Failed:            {fail_count}")
    if dry_run:
        print("  (dry_run=true — no files were modified)")
    if test_mode:
        print(f"  (test_mode={test_mode_setting} — no files were modified)")
    return 0 if fail_count == 0 else 1
