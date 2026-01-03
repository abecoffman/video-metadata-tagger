from core.matching import build_search_candidates, clean_filename_for_search, is_extras_title


def test_clean_filename_for_search_examples() -> None:
    tokens = [
        "1080p",
        "x264",
        "bluray",
        "webrip",
        "hdrip",
        "dts",
        "yify",
        "rarbg",
    ]
    cases = [
        ("The.Matrix.1999.1080p.BluRay.x264", ("The Matrix", 1999)),
        ("Ace Ventura_ Pet Detective", ("Ace Ventura Pet Detective", None)),
        ("The Godfather Part II D1 1974", ("The Godfather Part II", 1974)),
        ("LOTR Fellowship Ext D1", ("Lord of the Rings Fellowship", None)),
        ("Top Gun (1986) 1080p BluRay x264", ("Top Gun", 1986)),
        ("Top Gun [1986]", ("Top Gun", 1986)),
        ("Top Gun (1986)", ("Top Gun", 1986)),
        ("Kill Bill V2", ("Kill Bill Vol 2", None)),
        ("Sex and the City s1v2", ("Sex and the City", None)),
        ("Lions For Lambs [WS]", ("Lions For Lambs", None)),
        ("300", ("300", None)),
    ]
    for stem, expected in cases:
        assert clean_filename_for_search(stem, tokens) == expected


def test_build_search_candidates_splits_and_corrects() -> None:
    candidates = build_search_candidates("Eddie Murphy Boomerang")
    assert "Eddie Murphy Boomerang" in candidates
    candidates = build_search_candidates("Napaleon Dynamite")
    assert "Napaleon Dynamite" in candidates
    candidates = build_search_candidates("Am\u00e9lie")
    assert "Amelie" in candidates


def test_extras_title_detection() -> None:
    assert is_extras_title("LOTR - Appendices Part One – From Book to Vision") is True


def test_build_search_candidates_avoids_single_token_fallback() -> None:
    candidates = build_search_candidates("Chappelle Show S1 D2")
    assert "Show" not in candidates
