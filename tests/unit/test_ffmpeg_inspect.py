import json
from pathlib import Path
from types import SimpleNamespace

import ffmpeg.inspect as inspect_module


def test_has_drm_stream_detects_codec(monkeypatch) -> None:
    payload = {
        "streams": [
            {"codec_name": "drmi", "codec_tag_string": "drmi"},
        ]
    }

    def fake_run(_cmd, capture_output, text):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(inspect_module.subprocess, "run", fake_run)

    assert inspect_module.has_drm_stream("ffprobe", Path("movie.m4v")) is True
