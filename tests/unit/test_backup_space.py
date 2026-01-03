from collections import namedtuple

from core.services import write_pipeline


def test_has_sufficient_backup_space(monkeypatch, tmp_path) -> None:
    usage = namedtuple("usage", ["total", "used", "free"])

    def fake_disk_usage(_path):
        return usage(total=100, used=90, free=10)

    monkeypatch.setattr(write_pipeline.shutil, "disk_usage", fake_disk_usage)

    assert write_pipeline.has_sufficient_backup_space(tmp_path, 5) is True
    assert write_pipeline.has_sufficient_backup_space(tmp_path, 20) is False
