import time
from tmdb_client import TMDBClient
from database import (
    set_movie_status,
    add_tag,
    get_tags
)

client = TMDBClient()

# ==============================
# КЭШ
# ==============================

_cache = {}
CACHE_TTL = 60 * 10  # 10 минут


def get_cached(key):
    """
    Получить из кэша, если не протух.
    """
    if key in _cache:
        value, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return value
    return None


def set_cache(key, value):
    """
    Сохранить в кэш.
    """
    _cache[key] = (value, time.time())


# ==============================
# ОСНОВНЫЕ РЕКОМЕНДАЦИИ
# ==============================

def search_and_save_as_watched(telegram_id, movie_name):
    """
    Поиск фильма по названию и сохранение как просмотренного.
    """
    results = client.search_movie(movie_name)

    if not results.get("results"):
        return "Фильм не найден 😔"

    movie = results["results"][0]
    title = movie.get("title")
    tmdb_id = movie.get("id")

    set_movie_status(telegram_id, tmdb_id, title, "watched")

    # добавим теги (если есть жанры)
    for genre in movie.get("genre_ids", []):
        add_tag(tmdb_id, str(genre))

    return f"✅ Сохранено как просмотрено: {title}"


def get_similar_movies(movie_name):
    """
    Похожие фильмы.
    """
    results = client.search_movie(movie_name)

    if not results.get("results"):
        return []

    movie = results["results"][0]
    tmdb_id = movie.get("id")

    similar = client.get_similar(tmdb_id)

    if not similar or not similar.get("results"):
        return []

    return [m.get("title") for m in similar["results"][:5] if m.get("title")]


def recommend_by_mood(mood):
    """
    Рекомендации по настроению.
    Используем поиск как простую стратегию.
    """
    cache_key = f"mood:{mood}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    results = client.search_movie(mood)

    if not results.get("results"):
        return []

    recs = [m.get("title") for m in results["results"][:5] if m.get("title")]

    set_cache(cache_key, recs)
    return recs


def get_trending():
    """
    Тренды недели (с кэшем).
    """
    cache_key = "trending"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    data = client.get_trending()

    if not data or not data.get("results"):
        return []

    result = [m.get("title") for m in data["results"][:5] if m.get("title")]

    set_cache(cache_key, result)
    return result


# ==============================
# УМНЫЕ РЕКОМЕНДАЦИИ НА ТЕГАХ
# ==============================

def recommend_by_tags(telegram_id):
    """
    Рекомендации на основе тегов просмотренных фильмов.
    """
    movies = client.get_trending()
    if not movies or not movies.get("results"):
        return []

    # простая стратегия:
    # берём теги пользователя и ищем фильмы с похожими тегами
    user_movies = []
    try:
        from database import get_user_movies
        user_movies = get_user_movies(telegram_id)
    except Exception:
        return []

    tags = set()
    for _, tmdb_id, _ in user_movies:
        tags.update(get_tags(tmdb_id))

    if not tags:
        return []

    recs = []
    for m in movies["results"]:
        movie_tags = set(str(g) for g in m.get("genre_ids", []))
        if tags & movie_tags:
            recs.append(m.get("title"))

    return recs[:5]