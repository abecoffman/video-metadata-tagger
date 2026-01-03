import json
import sys
from pathlib import Path

import main
from core import run
from tmdb import client as tmdb_client


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
    monkeypatch.setattr(
        run,
        "tmdb_search_best_match_with_candidates_scored",
        lambda **kwargs: tmdb_client.MatchCandidate(
            result={"id": 1}, score=9.0, votes=100, popularity=5.0, media_type="movie"
        ),
    )
    monkeypatch.setattr(run, "tmdb_search_best_tv_match_with_candidates_scored", lambda **kwargs: None)
    monkeypatch.setattr(
        run,
        "tmdb_movie_details",
        lambda *args, **kwargs: {"id": 1, "title": "Top Gun", "release_date": "1986-05-16"},
    )
    monkeypatch.setattr(run.time, "sleep", lambda *_args, **_kwargs: None)


def test_rerun_failed_filters_manifest(capsys, tmp_path: Path, monkeypatch) -> None:
    movie_ok = tmp_path / "ok.m4v"
    movie_ok.write_text("data", encoding="utf-8")
    movie_fail = tmp_path / "fail.m4v"
    movie_fail.write_text("data", encoding="utf-8")

    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    _mock_tmdb(monkeypatch)
    monkeypatch.setenv("TMDB_API_KEY", "x")

    manifest = tmp_path / "run.jsonl"
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"path": str(movie_ok), "status": "ok"}),
                json.dumps({"path": str(movie_fail), "status": "failed"}),
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--config", str(cfg_path), "--rerun-failed", str(manifest)],
    )

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Found 1 file(s)." in out
    assert str(movie_ok) not in out
