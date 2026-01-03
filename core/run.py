"""Main execution pipeline for tagging movie files."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import requests

from cli import RunOptions
from config import Config
from core.matching import build_search_candidates, clean_filename_for_search, is_extras_title
from core.movie_metadata import MovieMetadata
from core.serialization import render_tag_value
from core.tv_metadata import TvMetadata
from core.services.file_selection import select_files
from core.services.run_artifacts import RunDirs, append_run_log, setup_run_dirs, write_manifest_record
from tmdb.service import init_tmdb
from core.services.write_pipeline import filter_existing_tags, has_sufficient_backup_space
from ffmpeg.backups import backup_metadata_path, backup_original_path, ffmpeg_backup_metadata, ffmpeg_restore_metadata
import ffmpeg.inspect as inspect_module
from ffmpeg.inspect import MediaInspector, resolve_ffprobe_path
from ffmpeg.atomicparsley import atomicparsley_write_metadata
from ffmpeg.writer import ResourceBusyError, ffmpeg_write_metadata
from file_io.scanner import normalize_extensions
from logger import get_logger
from tmdb.helpers import download_cover_art
from tmdb.client import (
    choose_preferred_match,
    tmdb_movie_details,
    tmdb_search_best_match_with_candidates,
    tmdb_search_best_match_with_candidates_scored,
    tmdb_search_best_tv_match_with_candidates,
    tmdb_search_best_tv_match_with_candidates_scored,
    tmdb_tv_details,
)
from tmdb.service import build_cover_url

log = get_logger()


@dataclass
class RunContext:
    """Resolved configuration and helpers for a run."""

    cfg: Config
    exts: list[str]
    ignore_substrings: list[str]
    max_files: int
    strip_tokens: list[str]
    prefer_year: bool
    write_enabled: bool
    dry_run: bool
    backup_original: bool
    backup_suffix: str
    backup_dir: Path
    cover_art_enabled: bool
    cover_art_size: str
    ffmpeg_path: str
    atomicparsley_path: str
    metadata_tool: str
    rdns_namespace: str
    ffmpeg_analyzeduration: str | int | None
    ffmpeg_probe_size: str | int | None
    atomic_replace: bool
    override_existing: bool
    test_mode_setting: str | None
    test_mode: bool
    full_log: bool
    ffprobe_path: str
    inspector: MediaInspector
    tmdb_ctx: object


@dataclass
class ProcessResult:
    """Per-file processing result."""

    status: str


@dataclass
class RunSummary:
    """Aggregate results for a run."""

    ok_count: int
    skip_count: int
    fail_count: int


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


def prepare_run_context(options: RunOptions, cfg: Config) -> RunContext | None:
    """Resolve configuration and helpers for a run."""
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
    atomicparsley_path = str(write_cfg.atomicparsley_path)
    metadata_tool = str(write_cfg.metadata_tool or "ffmpeg").lower()
    rdns_namespace = str(write_cfg.rdns_namespace or "local.tmdb")
    ffmpeg_analyzeduration = write_cfg.ffmpeg_analyzeduration
    ffmpeg_probe_size = write_cfg.ffmpeg_probe_size
    atomic_replace = bool(write_cfg.atomic_replace)
    override_existing = bool(write_cfg.override_existing)
    test_mode_setting = resolve_test_mode(options, cfg)
    test_mode = bool(test_mode_setting)
    full_log = test_mode_setting != "basic"

    if test_mode:
        log.info(f"TEST MODE enabled ({test_mode_setting}): no files will be modified.\n")

    if not exts:
        log.info("No file extensions configured. Add scan.extensions in config.")
        return None
    if options.file and options.file.suffix.lower() not in exts:
        log.info(f"File extension not configured for scan: {options.file.suffix}")
        return None

    if not test_mode:
        backup_dir.mkdir(parents=True, exist_ok=True)

    tmdb_ctx, tmdb_error = init_tmdb(
        cfg,
        cover_art_enabled,
        write_enabled,
        test_mode_setting,
        bool(options.restore_backup),
    )
    if tmdb_error:
        log.info(tmdb_error)
        return None

    ffprobe_path = resolve_ffprobe_path(ffmpeg_path)
    inspector = MediaInspector(ffprobe_path)

    return RunContext(
        cfg=cfg,
        exts=exts,
        ignore_substrings=ignore_substrings,
        max_files=max_files,
        strip_tokens=strip_tokens,
        prefer_year=prefer_year,
        write_enabled=write_enabled,
        dry_run=dry_run,
        backup_original=backup_original,
        backup_suffix=backup_suffix,
        backup_dir=backup_dir,
        cover_art_enabled=tmdb_ctx.cover_art_enabled,
        cover_art_size=cover_art_size,
        ffmpeg_path=ffmpeg_path,
        atomicparsley_path=atomicparsley_path,
        metadata_tool=metadata_tool,
        rdns_namespace=rdns_namespace,
        ffmpeg_analyzeduration=ffmpeg_analyzeduration,
        ffmpeg_probe_size=ffmpeg_probe_size,
        atomic_replace=atomic_replace,
        override_existing=override_existing,
        test_mode_setting=test_mode_setting,
        test_mode=test_mode,
        full_log=full_log,
        ffprobe_path=ffprobe_path,
        inspector=inspector,
        tmdb_ctx=tmdb_ctx,
    )


def select_run_files(options: RunOptions, ctx: RunContext) -> list[Path] | None:
    """Resolve files to process for the run."""
    files = select_files(
        options.rerun_failed,
        options.file,
        options.root,
        ctx.exts,
        ctx.ignore_substrings,
        ctx.max_files,
        options.only_exts,
    )
    if files is None:
        return None
    if not files:
        log.info("No movie files found.")
        return []
    return files


def process_one_file(
    path: Path,
    idx: int,
    total: int,
    options: RunOptions,
    ctx: RunContext,
    run_dirs: RunDirs,
    is_retry: bool,
) -> ProcessResult:
    """Process a single file."""
    stat = None
    try:
        stat = path.stat()
    except FileNotFoundError:
        log.info(f"\n[{idx}/{total}] {path}")
        log.info("  ❌ File missing (skipping).")
        if run_dirs.run_manifest_path:
            write_manifest_record(
                run_dirs.run_manifest_path,
                {
                    "path": str(path),
                    "status": "failed",
                    "reason": "missing_file",
                    "mtime": None,
                    "size": None,
                },
            )
        return ProcessResult(status="failed")

    stem = path.stem
    title_guess, year_guess = clean_filename_for_search(stem, ctx.strip_tokens)
    if not ctx.prefer_year:
        year_guess = None

    if is_extras_title(title_guess):
        log.info(f"\n[{idx}/{total}] {path}")
        log.info("  ⚠️ Extras/bonus content detected; writing title only and removing artwork.")
        tags_to_write: Dict[str, str] = {}
        if title_guess:
            tags_to_write["title"] = title_guess
        tags_to_write["extras"] = "true"

        if not ctx.write_enabled:
            log.info("  Write disabled; skipping extras update.")
            if run_dirs.run_manifest_path:
                write_manifest_record(
                    run_dirs.run_manifest_path,
                    {
                        "path": str(path),
                        "status": "skipped",
                        "reason": "extras_write_disabled",
                        "tmdb_id": None,
                        "title": title_guess,
                        "mtime": stat.st_mtime if stat else None,
                        "size": stat.st_size if stat else None,
                    },
                )
            return ProcessResult(status="skipped")

        backup_path = None
        if run_dirs.run_backup_dir:
            backup_path = ffmpeg_backup_metadata(
                ffmpeg_path=ctx.ffmpeg_path,
                input_path=path,
                backup_dir=run_dirs.run_backup_dir,
                root=options.root,
                dry_run=ctx.dry_run,
                test_mode=ctx.test_mode,
            )
            if backup_path:
                log.info(f"  Backup: metadata saved to {backup_path}")

        if ctx.metadata_tool == "atomicparsley":
            wrote = atomicparsley_write_metadata(
                atomicparsley_path=ctx.atomicparsley_path,
                input_path=path,
                tags=tags_to_write,
                cover_art_path=None,
                remove_existing_artwork=True,
                rdns_namespace=ctx.rdns_namespace,
                log_path=run_dirs.run_log_path,
                backup_original=ctx.backup_original,
                backup_path=backup_original_path(run_dirs.run_backup_dir, path, options.root, ctx.backup_suffix),
                backup_suffix=ctx.backup_suffix,
                atomic_replace=ctx.atomic_replace,
                dry_run=ctx.dry_run,
                test_mode=ctx.test_mode,
            )
        else:
            log.info("  ⚠️ ffmpeg writer cannot remove existing artwork; continuing with title update.")
            wrote = ffmpeg_write_metadata(
                ffmpeg_path=ctx.ffmpeg_path,
                input_path=path,
                tags=tags_to_write,
                cover_art_path=None,
                ffmpeg_analyzeduration=ctx.ffmpeg_analyzeduration,
                ffmpeg_probe_size=ctx.ffmpeg_probe_size,
                log_path=run_dirs.run_log_path,
                backup_original=ctx.backup_original,
                backup_path=backup_original_path(run_dirs.run_backup_dir, path, options.root, ctx.backup_suffix),
                backup_suffix=ctx.backup_suffix,
                atomic_replace=ctx.atomic_replace,
                dry_run=ctx.dry_run,
                test_mode=ctx.test_mode,
            )

        if wrote:
            log.info("  ✅ Updated extras metadata")
            status = "ok"
            reason = "extras_updated"
        else:
            log.info("  ❌ Failed to update extras metadata")
            status = "failed"
            reason = "extras_failed"

        if run_dirs.run_manifest_path:
            write_manifest_record(
                run_dirs.run_manifest_path,
                {
                    "path": str(path),
                    "status": status,
                    "reason": reason,
                    "tmdb_id": None,
                    "title": title_guess,
                    "mtime": stat.st_mtime if stat else None,
                    "size": stat.st_size if stat else None,
                },
            )
        return ProcessResult(status=status)

    log.info(f"\n[{idx}/{total}] {path}")
    if options.restore_backup:
        log.info("  Restore: using backup metadata")
    else:
        if ctx.full_log:
            log.info(f"  Guess: title='{title_guess}' year={year_guess}")

    try:
        if options.restore_backup:
            metadata_path = backup_metadata_path(options.restore_backup, path, options.root)
            restored = ffmpeg_restore_metadata(
                ffmpeg_path=ctx.ffmpeg_path,
                input_path=path,
                metadata_path=metadata_path,
                atomic_replace=ctx.atomic_replace,
                dry_run=ctx.dry_run,
                test_mode=ctx.test_mode,
            )
            if restored:
                log.info("  ✅ Restored metadata from backup")
                status = "ok"
                reason = "restored"
            else:
                log.info("  ❌ Failed to restore metadata")
                status = "failed"
                reason = "restore_failed"
                append_run_log(run_dirs.run_log_path, f"[restore] {path}\nerror: failed to restore\n")
            if run_dirs.run_manifest_path:
                write_manifest_record(
                    run_dirs.run_manifest_path,
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
            return ProcessResult(status=status)

        if ctx.write_enabled and not ctx.test_mode:
            try:
                if ctx.inspector.has_drm_stream(path):
                    log.info("  DRM-protected media detected (skipping).")
                    append_run_log(run_dirs.run_log_path, f"[drm] {path}\n")
                    if run_dirs.run_manifest_path:
                        write_manifest_record(
                            run_dirs.run_manifest_path,
                            {
                                "path": str(path),
                                "status": "skipped",
                                "reason": "drm_protected",
                                "tmdb_id": None,
                                "title": None,
                                "mtime": stat.st_mtime if stat else None,
                                "size": stat.st_size if stat else None,
                            },
                        )
                    return ProcessResult(status="skipped")
            except Exception as exc:
                log.info(f"  ⚠️ Could not inspect DRM status: {exc}")

        candidates = build_search_candidates(title_guess)
        if ctx.cfg.tmdb.allow_tv_fallback:
            movie_candidate = tmdb_search_best_match_with_candidates_scored(
                session=ctx.tmdb_ctx.session,
                api_key=ctx.tmdb_ctx.api_key,
                titles=candidates,
                year=year_guess,
                language=ctx.tmdb_ctx.language,
                include_adult=ctx.tmdb_ctx.include_adult,
                min_score=ctx.tmdb_ctx.min_score,
                fallback_min_score=ctx.cfg.tmdb.fallback_min_score,
                fallback_min_votes=ctx.cfg.tmdb.fallback_min_votes,
            )
            tv_candidate = tmdb_search_best_tv_match_with_candidates_scored(
                session=ctx.tmdb_ctx.session,
                api_key=ctx.tmdb_ctx.api_key,
                titles=candidates,
                year=year_guess,
                language=ctx.tmdb_ctx.language,
                include_adult=ctx.tmdb_ctx.include_adult,
                min_score=ctx.tmdb_ctx.min_score,
                fallback_min_score=ctx.cfg.tmdb.fallback_min_score,
                fallback_min_votes=ctx.cfg.tmdb.fallback_min_votes,
            )
            chosen = choose_preferred_match(movie_candidate, tv_candidate)
            best = chosen.result if chosen else None
            media_type = chosen.media_type if chosen else "movie"
        else:
            best = tmdb_search_best_match_with_candidates(
                session=ctx.tmdb_ctx.session,
                api_key=ctx.tmdb_ctx.api_key,
                titles=candidates,
                year=year_guess,
                language=ctx.tmdb_ctx.language,
                include_adult=ctx.tmdb_ctx.include_adult,
                min_score=ctx.tmdb_ctx.min_score,
                fallback_min_score=ctx.cfg.tmdb.fallback_min_score,
                fallback_min_votes=ctx.cfg.tmdb.fallback_min_votes,
            )
            media_type = "movie"
        time.sleep(ctx.tmdb_ctx.delay)

        if not best:
            log.info("  TMDb: no confident match found (skipping).")
            if run_dirs.run_manifest_path:
                write_manifest_record(
                    run_dirs.run_manifest_path,
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
            return ProcessResult(status="skipped")

        movie_id = int(best["id"])
        if media_type == "tv":
            details = tmdb_tv_details(ctx.tmdb_ctx.session, ctx.tmdb_ctx.api_key, movie_id, ctx.tmdb_ctx.language)
        else:
            details = tmdb_movie_details(ctx.tmdb_ctx.session, ctx.tmdb_ctx.api_key, movie_id, ctx.tmdb_ctx.language)
        time.sleep(ctx.tmdb_ctx.delay)

        if media_type == "tv" and ctx.cfg.serialization_tv.mappings:
            serialization_cfg = ctx.cfg.serialization_tv
        else:
            serialization_cfg = ctx.cfg.serialization

        if media_type == "tv":
            metadata = TvMetadata.from_tmdb(details, serialization_cfg.max_overview_length)
        else:
            metadata = MovieMetadata.from_tmdb(details, serialization_cfg.max_overview_length)
        ctx_map = metadata.to_context()
        if not ctx.full_log:
            label = "Show" if media_type == "tv" else "Movie"
            log.info(f"  {label}: {metadata.title} ({metadata.release_year})")
        else:
            prefix = "TMDb TV" if media_type == "tv" else "TMDb"
            log.info(f"  {prefix}: matched '{metadata.title}' ({metadata.release_year}) id={metadata.tmdb_id}")
        tags_to_write: Dict[str, str] = {}
        for ffkey, template in serialization_cfg.mappings.items():
            val = render_tag_value(str(template), ctx_map)
            if val:
                tags_to_write[str(ffkey)] = val

        if not tags_to_write:
            log.info("  No tags produced from config mappings (skipping write).")
            if run_dirs.run_manifest_path:
                write_manifest_record(
                    run_dirs.run_manifest_path,
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
            return ProcessResult(status="skipped")

        if not ctx.override_existing:
            existing_tags: Dict[str, str] = {}
            try:
                existing_tags = ctx.inspector.read_format_tags(path)
            except Exception as exc:
                log.info(f"  ⚠️ Could not read existing tags: {exc}")
            if existing_tags:
                tags_to_write, skipped = filter_existing_tags(tags_to_write, existing_tags)
                if skipped:
                    log.info(f"  Skipping existing tags: {', '.join(skipped)}")
                if not tags_to_write:
                    log.info("  All configured tags already exist (skipping write).")
                    if run_dirs.run_manifest_path:
                        write_manifest_record(
                            run_dirs.run_manifest_path,
                            {
                                "path": str(path),
                                "status": "skipped",
                                "reason": "existing_tags",
                                "tmdb_id": metadata.tmdb_id,
                                "title": metadata.title,
                                "mtime": stat.st_mtime if stat else None,
                                "size": stat.st_size if stat else None,
                            },
                        )
                    return ProcessResult(status="skipped")

        if ctx.full_log:
            log.info("  Serialized metadata:")
            for k, v in tags_to_write.items():
                preview = v if len(v) <= 120 else (v[:117] + "...")
                log.info(f"    - {k}: {preview}")
            if ctx.test_mode_setting == "verbose":
                log.info("  TMDb metadata:")
                log.info(json.dumps(details, indent=2, sort_keys=True))

        cover_art_path = None
        cover_url = ""
        if ctx.cover_art_enabled:
            poster_path = str(details.get("poster_path") or "")
            cover_url = build_cover_url(ctx.tmdb_ctx, poster_path, ctx.cover_art_size)
            if ctx.full_log:
                if cover_url:
                    log.info(f"  Cover art: {cover_url}")
                else:
                    log.info("  Cover art: none")

        if ctx.write_enabled:
            if ctx.backup_original and run_dirs.run_backup_dir and not ctx.test_mode:
                required_bytes = stat.st_size if stat else 0
                if required_bytes and not has_sufficient_backup_space(run_dirs.run_backup_dir, required_bytes):
                    log.info("  ❌ Not enough space for backup (skipping).")
                    append_run_log(
                        run_dirs.run_log_path,
                        f"[backup] {path}\nerror: insufficient space for backup\n",
                    )
                    if run_dirs.run_manifest_path:
                        write_manifest_record(
                            run_dirs.run_manifest_path,
                            {
                                "path": str(path),
                                "status": "skipped",
                                "reason": "insufficient_backup_space",
                                "tmdb_id": metadata.tmdb_id,
                                "title": metadata.title,
                                "mtime": stat.st_mtime if stat else None,
                                "size": stat.st_size if stat else None,
                            },
                        )
                    return ProcessResult(status="skipped")
            original_backup_path = None
            if ctx.backup_original and run_dirs.run_backup_dir:
                original_backup_path = backup_original_path(
                    run_dirs.run_backup_dir,
                    path,
                    options.root,
                    ctx.backup_suffix,
                )
            if ctx.cover_art_enabled and cover_url and not ctx.test_mode:
                if not ctx.override_existing:
                    try:
                        if ctx.inspector.has_attached_picture(path):
                            if ctx.full_log:
                                log.info("  Cover art already present; skipping download")
                            cover_url = ""
                    except Exception as exc:
                        log.info(f"  ⚠️ Could not inspect existing artwork: {exc}")
                cover_art_path = download_cover_art(
                    session=ctx.tmdb_ctx.session,
                    url=cover_url,
                    suffix=Path(cover_url).suffix or ".jpg",
                )
                if cover_url and not cover_art_path:
                    log.info("  ⚠️ Cover art download failed; continuing without artwork")
                elif cover_art_path and ctx.full_log:
                    try:
                        size = cover_art_path.stat().st_size
                        log.info(f"  Cover art downloaded ({size} bytes)")
                    except OSError:
                        log.info("  Cover art downloaded")
            if run_dirs.run_backup_dir:
                backup_path = ffmpeg_backup_metadata(
                    ffmpeg_path=ctx.ffmpeg_path,
                    input_path=path,
                    backup_dir=run_dirs.run_backup_dir,
                    root=options.root,
                    dry_run=ctx.dry_run,
                    test_mode=ctx.test_mode,
                )
                if backup_path:
                    log.info(f"  Backup: metadata saved to {backup_path}")
            if ctx.metadata_tool == "atomicparsley":
                wrote = atomicparsley_write_metadata(
                    atomicparsley_path=ctx.atomicparsley_path,
                    input_path=path,
                    tags=tags_to_write,
                    cover_art_path=cover_art_path,
                    remove_existing_artwork=ctx.override_existing,
                    rdns_namespace=ctx.rdns_namespace,
                    log_path=run_dirs.run_log_path,
                    backup_original=ctx.backup_original,
                    backup_path=original_backup_path,
                    backup_suffix=ctx.backup_suffix,
                    atomic_replace=ctx.atomic_replace,
                    dry_run=ctx.dry_run,
                    test_mode=ctx.test_mode,
                )
            else:
                wrote = ffmpeg_write_metadata(
                    ffmpeg_path=ctx.ffmpeg_path,
                    input_path=path,
                    tags=tags_to_write,
                    cover_art_path=cover_art_path,
                    ffmpeg_analyzeduration=ctx.ffmpeg_analyzeduration,
                    ffmpeg_probe_size=ctx.ffmpeg_probe_size,
                    log_path=run_dirs.run_log_path,
                    backup_original=ctx.backup_original,
                    backup_path=original_backup_path,
                    backup_suffix=ctx.backup_suffix,
                    atomic_replace=ctx.atomic_replace,
                    dry_run=ctx.dry_run,
                    test_mode=ctx.test_mode,
                )
            if cover_art_path:
                cover_art_path.unlink(missing_ok=True)
            if wrote:
                log.info("  ✅ Updated metadata")
                if (
                    cover_art_path
                    and ctx.cover_art_enabled
                    and not ctx.test_mode
                    and not ctx.dry_run
                    and ctx.full_log
                ):
                    try:
                        has_artwork = inspect_module.has_attached_picture(ctx.ffprobe_path, path) or inspect_module.has_artwork_tag(
                            ctx.ffprobe_path, path
                        )
                        if not has_artwork:
                            log.info("  ⚠️ Cover art not detected after write")
                    except Exception as exc:
                        log.info(f"  ⚠️ Could not verify artwork after write: {exc}")
                status = "ok"
                reason = "updated"
            else:
                log.info("  ❌ Failed to update metadata")
                status = "failed"
                reason = "ffmpeg_failed"
            if run_dirs.run_manifest_path:
                write_manifest_record(
                    run_dirs.run_manifest_path,
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
            return ProcessResult(status=status)

        if run_dirs.run_manifest_path:
            write_manifest_record(
                run_dirs.run_manifest_path,
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
        return ProcessResult(status="ok")

    except ResourceBusyError:
        if is_retry:
            log.info("  ❌ Resource busy; failed after retry")
            append_run_log(run_dirs.run_log_path, f"[ffmpeg] {path}\nerror: resource busy after retry\n")
            if run_dirs.run_manifest_path:
                write_manifest_record(
                    run_dirs.run_manifest_path,
                    {
                        "path": str(path),
                        "status": "failed",
                        "reason": "resource_busy",
                        "tmdb_id": None,
                        "title": None,
                        "mtime": stat.st_mtime if stat else None,
                        "size": stat.st_size if stat else None,
                    },
                )
            return ProcessResult(status="failed")
        log.info("  ⚠️ Resource busy; will retry at end of run")
        append_run_log(run_dirs.run_log_path, f"[ffmpeg] {path}\nretry: resource busy\n")
        return ProcessResult(status="deferred")
    except requests.HTTPError as e:
        log.info(f"  ❌ TMDb HTTP error: {e}")
        append_run_log(run_dirs.run_log_path, f"[tmdb] {path}\nerror: {e}\n")
        if run_dirs.run_manifest_path:
            write_manifest_record(
                run_dirs.run_manifest_path,
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
        return ProcessResult(status="failed")
    except Exception as e:
        log.info(f"  ❌ Error: {e}")
        append_run_log(run_dirs.run_log_path, f"[error] {path}\nerror: {e}\n")
        if run_dirs.run_manifest_path:
            write_manifest_record(
                run_dirs.run_manifest_path,
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
        return ProcessResult(status="failed")


def run_files(
    files: list[Path],
    options: RunOptions,
    ctx: RunContext,
    run_dirs: RunDirs,
) -> RunSummary:
    """Process the list of files, retrying busy files once."""
    deferred: list[Path] = []
    ok_count = 0
    skip_count = 0
    fail_count = 0

    for idx, path in enumerate(files, 1):
        result = process_one_file(path, idx, len(files), options, ctx, run_dirs, is_retry=False)
        if result.status == "deferred":
            deferred.append(path)
        elif result.status == "ok":
            ok_count += 1
        elif result.status == "skipped":
            skip_count += 1
        else:
            fail_count += 1

    if deferred:
        log.info(f"\nRetrying {len(deferred)} file(s) due to resource busy...")
        for idx, path in enumerate(deferred, 1):
            result = process_one_file(path, idx, len(deferred), options, ctx, run_dirs, is_retry=True)
            if result.status == "ok":
                ok_count += 1
            elif result.status == "skipped":
                skip_count += 1
            else:
                fail_count += 1

    return RunSummary(ok_count=ok_count, skip_count=skip_count, fail_count=fail_count)


def finalize_run(summary: RunSummary, ctx: RunContext) -> int:
    """Log final summary and return exit code."""
    log.info("\nDone.")
    log.info(f"  Updated/Processed: {summary.ok_count}")
    log.info(f"  Skipped:           {summary.skip_count}")
    log.info(f"  Failed:            {summary.fail_count}")
    if ctx.dry_run:
        log.info("  (dry_run=true — no files were modified)")
    if ctx.test_mode:
        log.info(f"  (test_mode={ctx.test_mode_setting} — no files were modified)")
    return 0 if summary.fail_count == 0 else 1


def run(options: RunOptions, cfg: Config) -> int:
    """Execute the tagging run based on options and config.

    Args:
        options: Parsed run options.
        cfg: Loaded configuration.

    Returns:
        Process exit code.
    """
    ctx = prepare_run_context(options, cfg)
    if ctx is None:
        return 2

    files = select_run_files(options, ctx)
    if files is None:
        return 2
    if not files:
        return 0

    log.info(f"Found {len(files)} file(s).")
    if not ctx.write_enabled:
        log.info("NOTE: write.enabled is false; will only fetch & print metadata.\n")

    run_dirs = setup_run_dirs(options.restore_backup, ctx.backup_dir, ctx.test_mode)
    if run_dirs is None:
        return 2

    summary = run_files(files, options, ctx, run_dirs)
    return finalize_run(summary, ctx)
