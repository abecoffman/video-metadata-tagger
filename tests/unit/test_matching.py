from core.matching import clean_filename_for_search


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
        ("Top Gun (1986) 1080p BluRay x264", ("Top Gun", None)),
        ("Kill Bill V2", ("Kill Bill Vol 2", None)),
        ("Sex and the City s1v2", ("Sex and the City", None)),
        ("Lions For Lambs [WS]", ("Lions For Lambs", None)),
        ("300", ("300", None)),
    ]
    for stem, expected in cases:
        assert clean_filename_for_search(stem, tokens) == expected
