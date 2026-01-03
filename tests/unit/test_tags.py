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
    assert ctx["media_type"] == "movie"


def test_build_template_context_handles_tv() -> None:
    show = {
        "name": "Coupling",
        "first_air_date": "2000-05-12",
        "overview": "x" * 20,
        "genres": [{"name": "Comedy"}],
        "networks": [{"name": "BBC"}],
        "id": 7,
        "episode_run_time": [30],
        "number_of_seasons": 4,
        "number_of_episodes": 28,
    }
    ctx = build_template_context(show, max_overview_len=10, media_type="tv")
    assert ctx["title"] == "Coupling"
    assert ctx["release_year"] == "2000"
    assert ctx["production_companies_joined"] == "BBC"
    assert ctx["networks_joined"] == "BBC"
    assert ctx["runtime"] == "30"
    assert ctx["episode_runtime"] == "30"
    assert ctx["number_of_seasons"] == "4"
    assert ctx["number_of_episodes"] == "28"
    assert ctx["media_type"] == "tv"


def test_render_tag_value_handles_missing_keys() -> None:
    ctx = {"title": "Top Gun"}
    assert render_tag_value("{title}", ctx) == "Top Gun"
    assert render_tag_value("{missing}", ctx) == "{missing}"
