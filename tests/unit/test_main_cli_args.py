import json
import sys
from pathlib import Path

import main
from core import run


def _write_config(path: Path, backup_dir: Path, extensions=None) -> None:
    cfg = {
        "tmdb": {"api_key_env": "TMDB_API_KEY", "language": "en-US", "include_adult": False, "min_score": 0.1},
        "scan": {"extensions": extensions or [".m4v"], "ignore_substrings": [], "max_files": 0},
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
        lambda *args, **kwargs: {"id": 1, "title": "Top Gun", "release_date": "1986-05-16"},
    )
    monkeypatch.setattr(run.time, "sleep", lambda *_args, **_kwargs: None)


def test_cli_root_processes_files(capsys, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "movies"
    root.mkdir()
    (root / "Top Gun (1986).m4v").write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    _mock_tmdb(monkeypatch)
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--root", str(root)])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Found 1 file(s)." in out
    assert "TMDb: matched 'Top Gun' (1986)" in out


def test_cli_file_requires_configured_extension(capsys, tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).mp4"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs", extensions=[".m4v"])
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie)])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "File extension not configured" in out


def test_cli_file_missing(capsys, tmp_path: Path, monkeypatch) -> None:
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    missing = tmp_path / "missing.m4v"
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(missing)])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "Not a file" in out


def test_cli_config_missing(capsys, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "movies"
    root.mkdir()
    missing_cfg = tmp_path / "missing.json"
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(missing_cfg), "--root", str(root)])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "Config path not found" in out


def test_cli_defaults_to_module_configs(capsys, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "movies"
    root.mkdir()
    (root / "Top Gun (1986).m4v").write_text("data", encoding="utf-8")
    _mock_tmdb(monkeypatch)
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["main.py", "--root", str(root), "--test"])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Found 1 file(s)." in out


def test_cli_restore_backup_uses_backup_dir(capsys, tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    backup_dir = tmp_path / "runs" / "run"
    backup_dir.mkdir(parents=True)
    restored = {"called": False}

    def fake_restore(**_kwargs):
        restored["called"] = True
        return True

    monkeypatch.setattr(run, "ffmpeg_restore_metadata", fake_restore)
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie), "--restore-backup", str(backup_dir)])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert restored["called"] is True
    assert "Restored metadata from backup" in out


def test_cli_restore_backup_missing(capsys, tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs")
    missing_backup = tmp_path / "runs" / "missing"
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", str(cfg_path), "--file", str(movie), "--restore-backup", str(missing_backup)])

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "Backup directory not found" in out


def test_cli_only_ext_filters_files(capsys, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "movies"
    root.mkdir()
    (root / "movie.m4v").write_text("data", encoding="utf-8")
    (root / "movie.mp4").write_text("data", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, tmp_path / "runs", extensions=[".m4v", ".mp4"])
    _mock_tmdb(monkeypatch)
    monkeypatch.setenv("TMDB_API_KEY", "x")
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--config", str(cfg_path), "--root", str(root), "--only-ext", "m4v"],
    )

    exit_code = main.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Found 1 file(s)." in out
