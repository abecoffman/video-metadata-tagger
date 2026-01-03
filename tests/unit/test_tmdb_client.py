from tmdb.client import MatchCandidate, choose_preferred_match, normalize_title, title_similarity
from tmdb.helpers import build_image_url, select_image_size


def test_title_similarity_prefers_closer_match() -> None:
    assert normalize_title("Top Gun") == "top gun"
    assert title_similarity("Top Gun", "Top Gun Maverick") > title_similarity(
        "Top Gun", "The Berlin Wall Escape to Freedom"
    )


def test_title_similarity_handles_misspellings() -> None:
    assert title_similarity("Curious Case of Benjamen Button", "The Curious Case of Benjamin Button") > 0.7
    assert title_similarity("Napaleon Dynamite", "Napoleon Dynamite") > 0.7
    assert title_similarity("Vicky Christina Barcelona", "Vicky Cristina Barcelona") > 0.7


def test_title_similarity_handles_accents() -> None:
    assert title_similarity("Ame\u0301lie", "Amelie") > 0.7
    assert title_similarity("Am\u00e9lie", "Amelie") > 0.7


def test_choose_preferred_match_prefers_popular_tv() -> None:
    movie = MatchCandidate(result={"id": 1}, score=8.9, votes=5, popularity=0.0143, media_type="movie")
    tv = MatchCandidate(result={"id": 2}, score=8.9, votes=200, popularity=15.2, media_type="tv")
    chosen = choose_preferred_match(movie, tv)
    assert chosen is tv


def test_title_similarity_rejects_wrong_match() -> None:
    assert title_similarity("Wall-E", "Eton Wall Game") <= 0.6


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
