from tmdb.tmdb_client import normalize_title, title_similarity
from tmdb.tmdb_images import build_image_url, select_image_size


def test_title_similarity_prefers_closer_match() -> None:
    assert normalize_title("Top Gun") == "top gun"
    assert title_similarity("Top Gun", "Top Gun Maverick") > title_similarity(
        "Top Gun", "The Berlin Wall Escape to Freedom"
    )


def test_select_image_size_prefers_requested() -> None:
    available = ["w185", "w500", "original"]
    assert select_image_size(available, "w500") == "w500"


def test_select_image_size_falls_back_to_original() -> None:
    available = ["w185", "original"]
    assert select_image_size(available, "w342") == "original"


def test_build_image_url_formats_path() -> None:
    assert (
        build_image_url("https://image.tmdb.org/t/p/", "w185", "/poster.jpg")
        == "https://image.tmdb.org/t/p/w185/poster.jpg"
    )
