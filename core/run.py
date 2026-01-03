"""Main execution pipeline for tagging movie files."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

from ffmpeg.backups import backup_metadata_path, backup_original_path, ffmpeg_backup_metadata, ffmpeg_restore_metadata
from cli import RunOptions
from config import Config
from core.matching import clean_filename_for_search
from core.movie_metadata import MovieMetadata
from core.serialization import render_tag_value
from core.services.file_selection import select_files
from core.services.run_artifacts import append_run_log, setup_run_dirs, write_manifest_record
from core.services.tmdb_resolver import init_tmdb
from core.services.write_pipeline import filter_existing_tags, has_sufficient_backup_space
from file_io.scanner import normalize_extensions
from tmdb.tmdb_client import tmdb_movie_details, tmdb_search_best_match
from tmdb.tmdb_images import build_image_url, download_cover_art, select_image_size
from ffmpeg.inspect import MediaInspector, resolve_ffprobe_path
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
    override_existing = bool(write_cfg.override_existing)
    test_mode_setting = resolve_test_mode(options, cfg)
    test_mode = bool(test_mode_setting)
    full_log = test_mode_setting != "basic"
    ffprobe_path = resolve_ffprobe_path(ffmpeg_path)
    inspector = MediaInspector(ffprobe_path)

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

    files = select_files(
        options.rerun_failed,
        options.file,
        options.root,
        exts,
        ignore_substrings,
        max_files,
        options.only_exts,
    )
    if files is None:
        return 2
    if not files:
        print("No movie files found.")
        return 0

    print(f"Found {len(files)} file(s).")
    if not write_enabled:
        print("NOTE: write.enabled is false; will only fetch & print metadata.\n")

    run_dirs = setup_run_dirs(options.restore_backup, backup_dir, test_mode)
    if run_dirs is None:
        return 2

    tmdb_ctx, tmdb_error = init_tmdb(
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
                write_manifest_record(
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
                    append_run_log(run_log_path, f"[restore] {path}\nerror: failed to restore\n")
                if run_manifest_path:
                    write_manifest_record(
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

            if write_enabled and not test_mode:
                try:
                    if inspector.has_drm_stream(path):
                        print("  DRM-protected media detected (skipping).")
                        skip_count += 1
                        append_run_log(run_log_path, f"[drm] {path}\n")
                        if run_manifest_path:
                            write_manifest_record(
                                run_manifest_path,
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
                        continue
                except Exception as exc:
                    print(f"  ⚠️ Could not inspect DRM status: {exc}")

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
                    write_manifest_record(
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
            tags_to_write: Dict[str, str] = {}
            for ffkey, template in cfg.serialization.mappings.items():
                val = render_tag_value(str(template), ctx)
                if val:
                    tags_to_write[str(ffkey)] = val

            if not tags_to_write:
                print("  No tags produced from config mappings (skipping write).")
                skip_count += 1
                if run_manifest_path:
                    write_manifest_record(
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

            if not override_existing:
                existing_tags: Dict[str, str] = {}
                try:
                    existing_tags = inspector.read_format_tags(path)
                except Exception as exc:
                    print(f"  ⚠️ Could not read existing tags: {exc}")
                if existing_tags:
                    tags_to_write, skipped = filter_existing_tags(tags_to_write, existing_tags)
                    if skipped:
                        print(f"  Skipping existing tags: {', '.join(skipped)}")
                    if not tags_to_write:
                        print("  All configured tags already exist (skipping write).")
                        skip_count += 1
                        if run_manifest_path:
                            write_manifest_record(
                                run_manifest_path,
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
                        continue

            if full_log:
                print("  Serialized metadata:")
                for k, v in tags_to_write.items():
                    preview = v if len(v) <= 120 else (v[:117] + "...")
                    print(f"    - {k}: {preview}")
                if test_mode_setting == "verbose":
                    print("  TMDb metadata:")
                    print(json.dumps(details, indent=2, sort_keys=True))

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
                if backup_original and run_backup_dir and not test_mode:
                    required_bytes = stat.st_size if stat else 0
                    if required_bytes and not has_sufficient_backup_space(run_backup_dir, required_bytes):
                        print("  ❌ Not enough space for backup (skipping).")
                        skip_count += 1
                        append_run_log(
                            run_log_path,
                            f"[backup] {path}\nerror: insufficient space for backup\n",
                        )
                        if run_manifest_path:
                            write_manifest_record(
                                run_manifest_path,
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
                        continue
                original_backup_path = None
                if backup_original and run_backup_dir:
                    original_backup_path = backup_original_path(
                        run_backup_dir,
                        path,
                        options.root,
                        backup_suffix,
                    )
                if cover_art_enabled and cover_url and not test_mode:
                    if not override_existing:
                        try:
                            if inspector.has_attached_picture(path):
                                if full_log:
                                    print("  Cover art already present; skipping download")
                                cover_url = ""
                        except Exception as exc:
                            print(f"  ⚠️ Could not inspect existing artwork: {exc}")
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
                    write_manifest_record(
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
                    write_manifest_record(
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
            append_run_log(run_log_path, f"[tmdb] {path}\nerror: {e}\n")
            if run_manifest_path:
                write_manifest_record(
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
            append_run_log(run_log_path, f"[error] {path}\nerror: {e}\n")
            if run_manifest_path:
                write_manifest_record(
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
