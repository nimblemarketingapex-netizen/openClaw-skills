import requests
from config import TMDB_API_KEY, BASE_URL


class TMDBClient:

    def __init__(self):
        if not TMDB_API_KEY:
            raise ValueError("TMDB_API_KEY not set. Check .env")

    def _get(self, endpoint, params=None):
        params = params or {}
        params["api_key"] = TMDB_API_KEY
        params["language"] = "ru-RU"

        url = f"{BASE_URL}{endpoint}"
        response = requests.get(url, params=params)

        response.raise_for_status()

        return response.json()

    def search_movie(self, query):
        return self._get("/search/movie", {"query": query})

    def get_trending(self):
        return self._get("/trending/movie/week")

    def get_similar(self, movie_id):
        return self._get(f"/movie/{movie_id}/similar")