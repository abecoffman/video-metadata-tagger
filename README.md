# Movie Metadata Updater

Tag movie files using TMDb metadata and write tags via ffmpeg remux. The script scans your library (or a single file), looks up a best match on TMDb, and applies the configured tags. It can also attach poster art, back up metadata, and restore from runs.

## Features

- TMDb lookup with filename cleanup and fuzzy title matching
- Configurable tag mappings
- Optional cover art attachment (poster image)
- Per-run metadata backups + restore
- Rerun only failed files from a prior run
- Test mode (basic/verbose) for safe previews

## Requirements

- Python 3.9+
- `ffmpeg` installed and on PATH (or set `write.ffmpeg_path`)
- TMDb API key (`TMDB_API_KEY`)

### Install ffmpeg

- macOS (Homebrew): `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- Fedora: `sudo dnf install ffmpeg`
- Windows (winget): `winget install Gyan.FFmpeg`

## Installation

```bash
python3 -m pip install -r requirements.txt
```

Set your API key:

```bash
export TMDB_API_KEY="your_key_here"
```

## Quick Start

Scan a directory:

```bash
python3 main.py --root /path/to/movies
```

Run is the default command (you can also use `run` explicitly):

```bash
python3 main.py run --root /path/to/movies
```

Single file:

```bash
python3 main.py --file "/path/to/Top Gun (1986).m4v"
```

Test mode (basic):

```bash
python3 main.py --root /path/to/movies --test
```

Verbose test mode:

```bash
python3 main.py --root /path/to/movies --test verbose
```

## Configuration

The script loads module-aligned config files by default. You can still pass a single `config.json` with `--config` to override any section (it can be empty if you don't need overrides).

Default config locations:

- `tmdb/config.json`
- `file_io/config.json`
- `core/matching_config.json`
- `ffmpeg/config.json`
- `core/serialization_config.json`

### tmdb (`tmdb/config.json`)
- `api_key_env` (default: `TMDB_API_KEY`)
- `api_key` (optional fallback)
- `language` (default: `en-US`)
- `include_adult` (default: `false`)
- `min_score` (default: `2.0`)
- `request_delay_seconds` (default: `0.25`)

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
- `backup_original` (default: `true`)
- `backup_dir` (default: `runs`)
- `backup_suffix` (default: `.bak`)
- `cover_art_enabled` (default: `false`)
- `cover_art_size` (default: `w500`)
- `ffmpeg_path` (default: `ffmpeg`)
- `ffmpeg_analyzeduration` (default: `null`)
- `ffmpeg_probe_size` (default: `null`)
- `atomic_replace` (default: `true`)
- `test_mode` (`basic` or `verbose`)

### serialization (`core/serialization_config.json`)
- `mappings` (key/value metadata mappings)
- `max_overview_length` (default: `500`)

Example mapping (TMDb JSON fields → tag keys). Arrays are serialized as comma-separated strings:

```json
{
  "mappings": {
    "title": "{title}",
    "date": "{release_date}",
    "year": "{release_date}",
    "description": "{overview}",
    "comment": "{overview}",
    "genre": "{genres[].name}",
    "producer": "{production_companies[].name}",
    "country": "{origin_country[]}",
    "original_title": "{original_title}",
    "tagline": "{tagline}",
    "language": "{original_language}",
    "imdb_id": "{imdb_id}",
    "tmdb_id": "{id}",
    "runtime": "{runtime}",
    "rating": "{vote_average}",
    "votes": "{vote_count}",
    "popularity": "{popularity}",
    "budget": "{budget}",
    "revenue": "{revenue}",
    "status": "{status}",
    "homepage": "{homepage}",
    "spoken_languages": "{spoken_languages[].english_name}",
    "production_countries": "{production_countries[].name}",
    "collection": "{belongs_to_collection.name}"
  }
}
```

## Usage Examples

Only process M4V files:

```bash
python3 main.py --root /path/to/movies --only-ext m4v
```

Restore metadata from a backup run:

```bash
python3 main.py --restore-backup runs/20250102-153000 --file "/path/to/movie.m4v"
```

Rerun only failed files from a prior run:

```bash
python3 main.py --rerun-failed runs/20250102-153000
```

Override existing metadata values:

```bash
python3 main.py --root /path/to/movies --override-existing
```

Inspect files and report missing metadata:

```bash
python3 main.py inspect --root /path/to/movies
```

Write the inspect report to a specific log file:

```bash
python3 main.py inspect --root /path/to/movies --log /path/to/inspect.log
```

## Project Structure

- `core/` main run flow, matching, and serialization config.
- `ffmpeg/` metadata writing, backups, and write config.
- `file_io/` scanning, prompt utilities, and scan config.
- `tmdb/` TMDb API client, image helpers, and config.
- `tests/` unit and integration tests.

## Architecture

```
CLI (main.py/cli.py)
  -> config/loader
  -> core/run or core/inspect
       -> core/services (file_selection, tmdb_resolver, write_pipeline)
       -> tmdb/* (API + images)
       -> ffmpeg/* (inspect + write + backups)
```

## Backups & Logs

Each run creates a directory under `runs/` (unless running in test mode). Example:

```
runs/20250102-153000/
  run.jsonl
  run.log
  My Movie.m4v.ffmeta
```

### Generated Files per Run

- `run.jsonl` records per-file status and metadata for the run.
- `run.log` captures full error output on failures.
- `*.ffmeta` files are metadata snapshots used for restore.
- `*.bak` files are original file backups stored in the same run directory.

## Troubleshooting

- **"unknown codec" / probe errors**: Increase `write.ffmpeg_analyzeduration` and `write.ffmpeg_probe_size`.
- **ffmpeg not found**: Set `write.ffmpeg_path` or install ffmpeg.
- **Wrong match**: Adjust `tmdb.min_score` or refine filename cleanup in `matching`.

## Testing

Unit tests:

```bash
python3 -m pytest -q tests/unit
```

Integration tests (requires network + API key):

```bash
python3 -m pytest -q tests/integration
```
