from dotenv import load_dotenv
import os

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not TMDB_API_KEY:
    print("⚠ TMDB_API_KEY не задан — TMDB функции недоступны")

BASE_URL = "https://api.themoviedb.org/3"