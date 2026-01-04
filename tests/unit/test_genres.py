from core.mapping.genres import normalize_genres


def test_normalize_genres_maps_scifi_and_dedupes() -> None:
    raw = ["Science Fiction", "Sci-Fi & Fantasy", "Drama", "Drama", "Kids", ""]
    assert normalize_genres(raw) == ["Drama"]


def test_normalize_genres_handles_common_tmdb_names() -> None:
    raw = [
        "Action",
        "Adventure",
        "Action & Adventure",
        "Animation",
        "Biography",
        "Comedy",
        "Crime",
        "Documentary",
        "Drama",
        "Family",
        "Fantasy",
        "History",
        "Horror",
        "Music",
        "Mystery",
        "Romance",
        "Science Fiction",
        "Sci-Fi & Fantasy",
        "Thriller",
        "War",
        "Western",
        "Kids",
        "Sport",
        "TV Movie",
        "Reality",
        "News",
        "Talk",
        "Soap",
    ]
    assert normalize_genres(raw) == ["Documentary"]


def test_normalize_genres_filters_unknown_tmdb_names() -> None:
    raw = ["Unlisted", "Unknown Genre", "Adventure Reality", ""]
    assert normalize_genres(raw) == []


def test_normalize_genres_maps_tmdb_compounds() -> None:
    raw = ["Action & Adventure", "Sci-Fi & Fantasy", "War & Politics"]
    assert normalize_genres(raw) == ["Action"]


def test_normalize_genres_applies_priority_order() -> None:
    raw = ["Horror", "Romance", "Documentary", "Comedy"]
    assert normalize_genres(raw) == ["Documentary", "Comedy"]


def test_normalize_genres_limits_to_two() -> None:
    raw = ["Action", "Drama", "Comedy", "Thriller"]
    assert normalize_genres(raw) == ["Action", "Comedy"]


def test_normalize_genres_prefers_two_when_no_compound() -> None:
    raw = ["TV Movie", "Drama", "Comedy"]
    assert normalize_genres(raw) == ["Comedy", "Drama"]
