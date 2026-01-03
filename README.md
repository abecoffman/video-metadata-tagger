# Movie Metadata Updater

Tag MP4/M4V movie and TV files using TMDb metadata, apply structured tags, and attach poster art. The tool supports safe runs, per-run logs, optional metadata backups, and an inspect mode to spot missing fields.

## What This Does

- Finds best TMDb matches using filename cleanup + RapidFuzz similarity
- Handles movies and TV series (TV always enabled)
- Writes metadata via AtomicParsley (default) or ffmpeg remux
- Downloads and embeds poster art by default
- Records run manifests + logs and supports restore from run metadata

## Quick Start

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Set your TMDb API key:

```bash
export TMDB_API_KEY="your_key_here"
```

Run against a directory:

```bash
python3 main.py --root /path/to/movies
```

Run a single file:

```bash
python3 main.py --file "/path/to/Top Gun (1986).m4v"
```

Inspect a single file:

```bash
python3 main.py inspect --file "/path/to/Top Gun (1986).m4v"
```

## How Matching Works

- Filenames are cleaned (remove noise tokens, normalize punctuation, preserve hyphens).
- Titles are normalized for fuzzy matching (RapidFuzz).
- Movie and TV results are both scored when TV fallback is enabled.
- If scores are close, higher popularity/votes win (helps prefer well-known TV shows).

## Configuration

Defaults come from module config files. You can override them with a single `config.json` via `--config`.

Default config files:

- `tmdb/config.json`
- `file_io/config.json`
- `core/matching_config.json`
- `ffmpeg/config.json`
- `core/serialization_config.json`
- `core/serialization_tv_config.json`

### tmdb (`tmdb/config.json`)
- `api_key_env` (default: `TMDB_API_KEY`)
- `api_key` (optional fallback)
- `language` (default: `en-US`)
- `include_adult` (default: `false`)
- `min_score` (default: `2.0`)
- `fallback_min_score` (default: `1.5`)
- `fallback_min_votes` (default: `10`)
- `request_delay_seconds` (default: `0.25`)
- `allow_tv_fallback` (default: `true`)

### scan (`file_io/config.json`)
- `extensions` (list of extensions to scan)
- `ignore_substrings` (skip files containing these substrings)
- `max_files` (0 = no limit)

### matching (`core/matching_config.json`)
- `strip_tokens` (tokens removed from filenames before searching)
- `prefer_year_from_filename` (default: `true`)

### write (`ffmpeg/config.json`)
- `enabled` (default: `true`)
- `dry_run` (default: `false`)
- `override_existing` (default: `false`)
- `backup_original` (default: `false`)
- `backup_dir` (default: `runs`)
- `backup_suffix` (default: `.bak`)
- `cover_art_enabled` (default: `true`)
- `cover_art_size` (default: `w500`)
- `ffmpeg_path` (default: `ffmpeg`)
- `atomicparsley_path` (default: `AtomicParsley`)
- `metadata_tool` (`ffmpeg` or `atomicparsley`, default: `atomicparsley`)
- `rdns_namespace` (default: `local.tmdb`, used for AtomicParsley freeform tags)
- `ffmpeg_analyzeduration` (default: `null`)
- `ffmpeg_probe_size` (default: `null`)
- `atomic_replace` (default: `true`)
- `test_mode` (`basic` or `verbose`)

When `metadata_tool=atomicparsley`, tags not supported by AtomicParsley flags are written as freeform rDNS atoms using `rdns_namespace`.

### serialization (`core/serialization_config.json`)
- `mappings` (key/value metadata mappings for movies)
- `max_overview_length` (default: `500`)

### serialization_tv (`core/serialization_tv_config.json`)
- `mappings` (key/value metadata mappings for TV)
- `max_overview_length` (default: `500`)

## Metadata Mapping

Arrays are serialized as comma-separated strings. `media_type` is `movie` or `tv`.

Movie mapping example:

```json
{
  "mappings": {
    "title": "{title}",
    "media_type": "{media_type}",
    "date": "{release_date}",
    "year": "{release_year}",
    "description": "{overview}",
    "comment": "{overview}",
    "genre": "{genres_joined}",
    "producer": "{production_companies_joined}",
    "country": "{origin_countries_joined}",
    "original_title": "{original_title}",
    "tagline": "{tagline}",
    "language": "{original_language}",
    "imdb_id": "{imdb_id}",
    "tmdb_id": "{tmdb_id}",
    "runtime": "{runtime}",
    "rating": "{vote_average}",
    "votes": "{vote_count}",
    "popularity": "{popularity}",
    "budget": "{budget}",
    "revenue": "{revenue}",
    "status": "{status}",
    "homepage": "{homepage}",
    "spoken_languages": "{spoken_languages_joined}",
    "production_countries": "{production_countries_joined}",
    "collection": "{collection_name}",
    "extras": "{extras}"
  }
}
```

TV mapping example:

```json
{
  "mappings": {
    "title": "{title}",
    "media_type": "{media_type}",
    "date": "{release_date}",
    "year": "{release_year}",
    "description": "{overview}",
    "comment": "{overview}",
    "genre": "{genres_joined}",
    "producer": "{production_companies_joined}",
    "country": "{origin_countries_joined}",
    "original_title": "{original_title}",
    "tagline": "{tagline}",
    "language": "{original_language}",
    "imdb_id": "{imdb_id}",
    "tmdb_id": "{tmdb_id}",
    "runtime": "{runtime}",
    "rating": "{vote_average}",
    "votes": "{vote_count}",
    "popularity": "{popularity}",
    "status": "{status}",
    "homepage": "{homepage}",
    "spoken_languages": "{spoken_languages_joined}",
    "production_countries": "{production_countries_joined}",
    "networks": "{networks_joined}",
    "episode_runtime": "{episode_runtime}",
    "seasons": "{number_of_seasons}",
    "episodes": "{number_of_episodes}",
    "extras": "{extras}"
  }
}
```

## Usage Examples

Only process M4V files:

```bash
python3 main.py --root /path/to/movies --only-ext m4v
```

Override existing metadata values:

```bash
python3 main.py --root /path/to/movies --override-existing
```

Restore metadata from a prior run:

```bash
python3 main.py --restore-backup runs/20250102-153000 --file "/path/to/movie.m4v"
```

Rerun failed files from a prior run:

```bash
python3 main.py --rerun-failed runs/20250102-153000
```

Inspect files and write a report:

```bash
python3 main.py inspect --root /path/to/movies --log /path/to/inspect.log
```

## Runs & Artifacts

Each run creates a directory under `runs/` (unless running in test mode). Previous runs are deleted before a new run starts.

Example:

```
runs/20250102-153000/
  run.jsonl
  run.log
  My Movie.m4v.ffmeta
```

Files created per run:
- `run.jsonl` per-file status, match details, and error reasons
- `run.log` full stderr output on failures
- `*.ffmeta` metadata snapshots for restore
- `*.bak` optional full-file backups (disabled by default)

## Inspect Mode

Inspect reads existing tags via ffprobe and reports missing fields. It recognizes:
- AtomicParsley rDNS atoms (`local.tmdb`)
- MP4/iTunes atom names (e.g., `©day`, `©nam`)

## Troubleshooting

- **AtomicParsley not found**: install it or set `write.atomicparsley_path`.
- **ffmpeg not found**: install it or set `write.ffmpeg_path`.
- **Resource busy**: try rerun; the script retries once automatically.
- **Missing metadata in inspect**: ensure mapping keys exist or check rDNS namespace.
- **Wrong match**: raise `tmdb.min_score` or adjust matching tokens.
- **Artwork not updating**: rerun with `--override-existing` to remove existing artwork before writing a new cover.

## Install Tools

Install ffmpeg:

- macOS (Homebrew): `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Fedora: `sudo dnf install ffmpeg`
- Windows (winget): `winget install Gyan.FFmpeg`

Install AtomicParsley:

- macOS (Homebrew): `brew install atomicparsley`
- Ubuntu/Debian: `sudo apt-get install atomicparsley`

## Project Layout

- `core/` main pipeline, matching, serialization
- `ffmpeg/` write tools, backups, inspect helpers
- `file_io/` scanning, prompt utilities
- `tmdb/` API client + helpers
- `config/` config loader and models
- `tests/` unit + integration tests

## Architecture

```
CLI (main.py/cli.py)
  -> config/loader
  -> core/run or core/inspect
       -> core/services (file_selection, write_pipeline)
       -> tmdb/* (client + helpers + service)
       -> ffmpeg/* (inspect + write + backups)
```

## Tests

Unit tests:

```bash
python3 -m pytest -q tests/unit
```

Integration tests (requires network + API key):

```bash
python3 -m pytest -q tests/integration
```
