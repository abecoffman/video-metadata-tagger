from core.serialization import build_template_context, render_tag_value


def test_build_template_context_truncates_overview() -> None:
    movie = {
        "title": "Top Gun",
        "release_date": "1986-05-16",
        "overview": "x" * 20,
        "genres": [{"name": "Action"}],
        "production_companies": [{"name": "Paramount"}],
        "id": 42,
    }
    ctx = build_template_context(movie, max_overview_len=10)
    assert ctx["overview"].endswith("...")
    assert ctx["genres_joined"] == "Action"
    assert ctx["production_companies_joined"] == "Paramount"


def test_render_tag_value_handles_missing_keys() -> None:
    ctx = {"title": "Top Gun"}
    assert render_tag_value("{title}", ctx) == "Top Gun"
    assert render_tag_value("{missing}", ctx) == "{missing}"
