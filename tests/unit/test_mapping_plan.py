from core.mapping_engine import extract_jsonpath


def test_extract_jsonpath_handles_wildcards_and_filters() -> None:
    payload = {
        "genres": [{"name": "Action"}, {"name": "Drama"}],
        "crew": [
            {"job": "Director", "name": "Pat Doe"},
            {"job": "Producer", "name": "Sam Doe"},
        ],
        "posters": [{"file_path": "/poster.jpg"}],
    }

    assert extract_jsonpath(payload, "$.genres[*].name") == ["Action", "Drama"]
    assert extract_jsonpath(payload, "$.crew[?(@.job=='Director')].name") == ["Pat Doe"]
    assert extract_jsonpath(payload, "$.posters[0].file_path") == "/poster.jpg"
