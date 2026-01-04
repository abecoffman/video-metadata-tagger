from datetime import datetime
from pathlib import Path

from ffmpeg.backups import (
    backup_metadata_path,
    create_run_backup_dir,
    ffmpeg_backup_metadata,
    ffmpeg_restore_metadata,
)


class _Proc:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stderr = ""


def test_create_run_backup_dir_uses_timestamp(tmp_path: Path) -> None:
    base = tmp_path / "logs"
    now = datetime(2024, 1, 2, 3, 4, 5)
    run_dir = create_run_backup_dir(base, now=now)
    assert run_dir.exists()
    assert run_dir.name == "20240102-030405"


def test_backup_metadata_path_uses_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    input_path = root / "movies" / "Top Gun (1986).m4v"
    backup_dir = tmp_path / "logs" / "run"
    expected = backup_dir / "movies__Top Gun (1986).m4v.ffmeta"
    assert backup_metadata_path(backup_dir, input_path, root) == expected


def test_ffmpeg_backup_metadata_invokes_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "movie.m4v"
    input_path.write_text("data", encoding="utf-8")
    backup_dir = tmp_path / "logs"
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return _Proc(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    backup_path = ffmpeg_backup_metadata(
        ffmpeg_path="ffmpeg",
        input_path=input_path,
        backup_dir=backup_dir,
        root=tmp_path,
        dry_run=False,
        test_mode=False,
    )

    assert backup_path == backup_dir / "movie.m4v.ffmeta"
    assert calls


def test_ffmpeg_restore_metadata_invokes_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "movie.m4v"
    input_path.write_text("data", encoding="utf-8")
    metadata_path = tmp_path / "movie.m4v.ffmeta"
    metadata_path.write_text("FFMETADATA1\n", encoding="utf-8")
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        return _Proc(0)

    monkeypatch.setattr("subprocess.run", fake_run)

    restored = ffmpeg_restore_metadata(
        ffmpeg_path="ffmpeg",
        input_path=input_path,
        metadata_path=metadata_path,
        atomic_replace=True,
        dry_run=False,
        test_mode=False,
    )

    assert restored is True
    assert calls
