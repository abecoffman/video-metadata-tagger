from pathlib import Path

import core.inspect as inspect_module
from config import config_from_dict


def _build_config() -> object:
    return config_from_dict(
        {
            "scan": {"extensions": [".m4v"]},
            "serialization": {"mappings": {"title": "{title}", "genre": "{genres_joined}"}},
            "write": {"ffmpeg_path": "ffmpeg", "backup_dir": "runs"},
        }
    )


def test_find_missing_tags() -> None:
    missing = inspect_module.find_missing_tags({"title": "Top Gun"}, ["title", "genre"])
    assert missing == ["genre"]


def test_inspect_writes_log(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    log_path = tmp_path / "inspect.log"
    cfg = _build_config()

    def fake_read_format_tags(self, _input_path: Path) -> dict:
        return {"title": "Top Gun"}

    monkeypatch.setattr(inspect_module.MediaInspector, "read_format_tags", fake_read_format_tags)

    report = inspect_module.inspect(
        root=tmp_path,
        file_path=None,
        cfg=cfg,
        only_exts=[".m4v"],
        log_path=log_path,
    )

    contents = log_path.read_text(encoding="utf-8")
    assert "[MISSING]" in contents
    assert "genre" in contents
    assert report.total_files == 1
    assert report.files_with_missing == 1


def test_inspect_reports_missing_artwork(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    log_path = tmp_path / "inspect.log"
    cfg = config_from_dict(
        {
            "scan": {"extensions": [".m4v"]},
            "serialization": {"mappings": {"title": "{title}"}},
            "write": {"ffmpeg_path": "ffmpeg", "backup_dir": "runs", "cover_art_enabled": True},
        }
    )

    def fake_read_format_tags(self, _input_path: Path) -> dict:
        return {"title": "Top Gun"}

    monkeypatch.setattr(inspect_module.MediaInspector, "read_format_tags", fake_read_format_tags)
    monkeypatch.setattr(inspect_module.MediaInspector, "has_attached_picture", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(inspect_module.MediaInspector, "has_artwork_tag", lambda *_args, **_kwargs: False)

    inspect_module.inspect(
        root=tmp_path,
        file_path=None,
        cfg=cfg,
        only_exts=[".m4v"],
        log_path=log_path,
    )

    contents = log_path.read_text(encoding="utf-8")
    assert "[MISSING]" in contents
    assert "artwork" in contents


def test_inspect_detects_covr_artwork(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    log_path = tmp_path / "inspect.log"
    cfg = config_from_dict(
        {
            "scan": {"extensions": [".m4v"]},
            "serialization": {"mappings": {"title": "{title}"}},
            "write": {"ffmpeg_path": "ffmpeg", "backup_dir": "runs", "cover_art_enabled": True},
        }
    )

    def fake_read_format_tags(self, _input_path: Path) -> dict:
        return {"title": "Top Gun", "covr": "data"}

    monkeypatch.setattr(inspect_module.MediaInspector, "read_format_tags", fake_read_format_tags)
    monkeypatch.setattr(inspect_module.MediaInspector, "has_attached_picture", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(inspect_module.MediaInspector, "has_artwork_tag", lambda *_args, **_kwargs: True)

    inspect_module.inspect(
        root=tmp_path,
        file_path=None,
        cfg=cfg,
        only_exts=[".m4v"],
        log_path=log_path,
    )

    contents = log_path.read_text(encoding="utf-8")
    assert "[OK]" in contents


def test_inspect_accepts_rdns_tags(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "Top Gun (1986).m4v"
    movie.write_text("data", encoding="utf-8")
    log_path = tmp_path / "inspect.log"
    cfg = config_from_dict(
        {
            "scan": {"extensions": [".m4v"]},
            "serialization": {"mappings": {"tmdb_id": "{tmdb_id}"}},
            "write": {
                "ffmpeg_path": "ffmpeg",
                "backup_dir": "runs",
                "rdns_namespace": "local.tmdb",
                "cover_art_enabled": False,
            },
        }
    )

    def fake_read_format_tags(self, _input_path: Path) -> dict:
        return {"----:com.apple.iTunes:local.tmdb:tmdb_id": "1271"}

    monkeypatch.setattr(inspect_module.MediaInspector, "read_format_tags", fake_read_format_tags)

    inspect_module.inspect(
        root=tmp_path,
        file_path=None,
        cfg=cfg,
        only_exts=[".m4v"],
        log_path=log_path,
    )

    contents = log_path.read_text(encoding="utf-8")
    assert "[OK]" in contents
    assert "rDNS: tmdb_id" in contents


def test_inspect_normalizes_itunes_year(tmp_path: Path, monkeypatch) -> None:
    movie = tmp_path / "300.mp4"
    movie.write_text("data", encoding="utf-8")
    log_path = tmp_path / "inspect.log"
    cfg = config_from_dict(
        {
            "scan": {"extensions": [".mp4"]},
            "serialization": {"mappings": {"title": "{title}", "year": "{release_year}"}},
            "write": {"ffmpeg_path": "ffmpeg", "backup_dir": "runs", "cover_art_enabled": False},
        }
    )

    def fake_read_format_tags(self, _input_path: Path) -> dict:
        return {"\u00a9nam": "300", "\u00a9day": "2007-03-07"}

    monkeypatch.setattr(inspect_module.MediaInspector, "read_format_tags", fake_read_format_tags)

    inspect_module.inspect(
        root=tmp_path,
        file_path=None,
        cfg=cfg,
        only_exts=[".mp4"],
        log_path=log_path,
    )

    contents = log_path.read_text(encoding="utf-8")
    assert "[OK]" in contents
