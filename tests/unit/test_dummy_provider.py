from pathlib import Path

from core.mapping import transforms
from core.mapping_engine import MappingContext, build_tags_from_plan
from core.providers.dummy.adapter import DummyMappingProvider


def test_dummy_provider_uses_base_payload() -> None:
    plan = {
        "rules": [
            {
                "itunes_key": "title",
                "tmdb_sources": [{"endpoint": "/movie/{id}", "jsonpath": "$.title"}],
            }
        ]
    }
    ctx = MappingContext(
        content_id=123,
        language="en-US",
        include_adult=False,
        session=None,
        api_key="",
        request_delay=0.0,
        tv_season=None,
        tv_episode=None,
        image_base_url="",
        poster_sizes=[],
        cover_art_size="",
        run_dir=None,
        inspector=None,
        input_path=Path("/tmp/example.m4v"),
        dry_run=True,
        test_mode=True,
        allow_artwork_download=False,
    )
    base_payload = {"title": "Example"}
    provider = DummyMappingProvider()

    result = build_tags_from_plan(
        plan,
        ctx,
        base_payload,
        "/movie/{id}",
        [transforms],
        {"either", "ffmpeg"},
        provider,
    )

    assert result.tags["title"] == "Example"
