import os

import pytest
import requests

from tmdb.client import tmdb_request


@pytest.mark.integration
def test_tmdb_api_connection() -> None:
    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        pytest.skip("TMDB_API_KEY is not set in the environment.")
    session = requests.Session()
    data = tmdb_request(session, api_key, "/configuration", {})
    assert "images" in data
