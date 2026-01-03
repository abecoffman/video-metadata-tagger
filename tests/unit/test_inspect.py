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

    def fake_read_format_tags(_ffprobe_path: str, _input_path: Path) -> dict:
        return {"title": "Top Gun"}

    monkeypatch.setattr(inspect_module, "read_format_tags", fake_read_format_tags)

    report = inspect_module.inspect(
        root=tmp_path,
        file_path=None,
        cfg=cfg,
        only_exts=[".m4v"],
        log_path=log_path,
    )

    contents = log_path.read_text(encoding="utf-8")
    assert "Missing tags: genre" in contents
    assert report.total_files == 1
    assert report.files_with_missing == 1
