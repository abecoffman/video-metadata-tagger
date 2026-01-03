from core.services import write_pipeline


def test_filter_existing_tags_skips_present_values() -> None:
    tags = {"title": "Top Gun", "genre": "Action"}
    existing = {"title": "Existing Title"}
    filtered, skipped = write_pipeline.filter_existing_tags(tags, existing)

    assert filtered == {"genre": "Action"}
    assert skipped == ["title"]
