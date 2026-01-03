import json
import sys
from pathlib import Path

import main
from core import run


def _write_config(path: Path, backup_dir: Path) -> None:
    cfg = {
        "tmdb": {"api_key_env": "TMDB_API_KEY", "language": "en-US", "include_adult": False, "min_score": 0.1},
        "scan": {"extensions": [".m4v"], "ignore_substrings": [], "max_files": 0},
        "matching": {"strip_tokens": [], "prefer_year_from_filename": True},
        "write": {
            "enabled": False,
            "dry_run": False,
            "backup_original": True,
            "backup_dir": str(backup_dir),
        },
        "serialization": {"mappings": {"title": "{title}"}, "max_overview_length": 500},
    }
    path.write_text(json.dumps(cfg), encoding="utf-8")


def _mock_tmdb(monkeypatch) -> None:
    monkeypatch.setattr(run, "tmdb_search_best_match", lambda **kwargs: {"id": 1})
    monkeypatch.setattr(
        run,
        "tmdb_movie_details",
        lambda *args, **kwargs: {
            "id": 1,
            "title": "Top Gun",
            "release_date": "1986-05-16",
            "overview": "A pilot story.",
            "genres": [{"name": "Action"}],
            "production_companies": [{"name": "Paramount"}],
        },
    )
    monkeypatch.setattr(run.time, "sleep", lambda *_args, **_kwargs: None)


def test_test_mode_basic_logs_only_movie(capsys, tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    _mock_tmdb(monkeypatch)
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie), "--test"])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Movie: Top Gun (1986)" in out
    assert "TMDb metadata:" not in out
    assert "Tags:" not in out
    assert "Guess:" not in out


def test_test_mode_verbose_logs_metadata(capsys, tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    _mock_tmdb(monkeypatch)
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setattr(
        sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie), "--test", "verbose"]
    )

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "TMDb metadata:" in out
    assert '"title": "Top Gun"' in out
    assert "Serialized metadata:" in out
