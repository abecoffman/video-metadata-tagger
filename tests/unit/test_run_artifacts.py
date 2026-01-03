from pathlib import Path

from core.services.run_artifacts import cleanup_run_dirs, setup_run_dirs


def test_cleanup_run_dirs_removes_previous_runs(tmp_path: Path) -> None:
    (tmp_path / "20250101-010101").mkdir()
    (tmp_path / "20250102-020202").mkdir()

    cleanup_run_dirs(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_setup_run_dirs_cleans_then_creates(tmp_path: Path) -> None:
    (tmp_path / "20250101-010101").mkdir()

    run_dirs = setup_run_dirs(None, tmp_path, test_mode=False)

    assert run_dirs is not None
    assert run_dirs.run_backup_dir is not None
    assert run_dirs.run_backup_dir.exists()
    assert not (tmp_path / "20250101-010101").exists()
