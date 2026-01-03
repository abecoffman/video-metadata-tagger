import json
import sys
from pathlib import Path
from typing import Optional

import main
from core import run
from core.services import tmdb_resolver


def _write_config(path: Path, backup_dir: Path, enabled: bool) -> None:
    cfg = {
        "tmdb": {"api_key_env": "TMDB_API_KEY", "language": "en-US", "include_adult": False, "min_score": 0.1},
        "scan": {"extensions": [".m4v"], "ignore_substrings": [], "max_files": 0},
        "matching": {"strip_tokens": [], "prefer_year_from_filename": True},
        "write": {
            "enabled": True,
            "dry_run": False,
            "backup_original": False,
            "backup_dir": str(backup_dir),
            "cover_art_enabled": enabled,
            "cover_art_size": "w185",
            "ffmpeg_path": "ffmpeg",
            "atomic_replace": True,
        },
        "serialization": {"mappings": {"title": "{title}"}, "max_overview_length": 500},
    }
    path.write_text(json.dumps(cfg), encoding="utf-8")


def _mock_tmdb(monkeypatch, poster_path: Optional[str]) -> None:
    monkeypatch.setattr(run, "tmdb_search_best_match", lambda **kwargs: {"id": 1})
    monkeypatch.setattr(
        run,
        "tmdb_movie_details",
        lambda *args, **kwargs: {
            "id": 1,
            "title": "Top Gun",
            "release_date": "1986-05-16",
            "poster_path": poster_path,
        },
    )
    monkeypatch.setattr(
        tmdb_resolver,
        "tmdb_configuration",
        lambda *args, **kwargs: {
            "images": {"secure_base_url": "https://image.tmdb.org/t/p/", "poster_sizes": ["w185"]}
        },
    )
    monkeypatch.setattr(run.time, "sleep", lambda *_args, **_kwargs: None)


def test_cover_art_downloads_and_attaches(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs", enabled=True)
    _mock_tmdb(monkeypatch, poster_path="/poster.jpg")
    monkeypatch.setenv("TMDB_API_KEY", "x")

    cover_file = tmp_path / "poster.jpg"
    cover_file.write_bytes(b"img")

    def fake_download(session, url, suffix):
        return cover_file

    captured = {"cover": None}

    def fake_write(**kwargs):
        captured["cover"] = kwargs.get("cover_art_path")
        return True

    monkeypatch.setattr(run, "download_cover_art", fake_download)
    monkeypatch.setattr(run, "ffmpeg_write_metadata", fake_write)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie)])

    exit_code = main.main()

    assert exit_code == 0
    assert captured["cover"] == cover_file
    assert not cover_file.exists()


def test_cover_art_skips_when_missing_poster(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs", enabled=True)
    _mock_tmdb(monkeypatch, poster_path=None)
    monkeypatch.setenv("TMDB_API_KEY", "x")

    called = {"download": False, "cover": None}

    def fake_download(session, url, suffix):
        called["download"] = True
        return None

    def fake_write(**kwargs):
        called["cover"] = kwargs.get("cover_art_path")
        return True

    monkeypatch.setattr(run, "download_cover_art", fake_download)
    monkeypatch.setattr(run, "ffmpeg_write_metadata", fake_write)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie)])

    exit_code = main.main()

    assert exit_code == 0
    assert called["download"] is False
    assert called["cover"] is None


def test_cover_art_logs_selected_image_in_verbose(capsys, tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs", enabled=True)
    _mock_tmdb(monkeypatch, poster_path="/poster.jpg")
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie), "--test", "verbose"])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Cover art: https://image.tmdb.org/t/p/w185/poster.jpg" in out
