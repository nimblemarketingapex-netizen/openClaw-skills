from database import add_user
from recommender import (
    search_and_save_as_watched,
    get_similar_movies,
    recommend_by_mood,
    get_trending,
    recommend_by_tags
)
from database import mark_planned, mark_dropped, get_user_movies


def handle_message(telegram_id, text):
    """
    Главная точка обработки сообщений.
    OpenClaw вызывает эту функцию.
    """

    add_user(telegram_id)

    text = text.strip()
    low = text.lower()

    # ==============================
    # СТАТУСЫ
    # ==============================

    if low.startswith("смотрел"):
        movie = text[7:].strip()
        return search_and_save_as_watched(telegram_id, movie)

    if low.startswith("планирую"):
        movie = text[8:].strip()
        # сохраняем как planned
        # сначала ищем фильм (для ID)
        from tmdb_client import TMDBClient
        client = TMDBClient()
        res = client.search_movie(movie)

        if not res.get("results"):
            return "Фильм не найден 😔"

        m = res["results"][0]
        tmdb_id = m.get("id")
        title = m.get("title")

        mark_planned(telegram_id, tmdb_id, title)
        return f"📌 Добавлено в план: {title}"

    if low.startswith("бросил"):
        movie = text[6:].strip()
        from tmdb_client import TMDBClient
        client = TMDBClient()
        res = client.search_movie(movie)

        if not res.get("results"):
            return "Фильм не найден 😔"

        m = res["results"][0]
        tmdb_id = m.get("id")
        title = m.get("title")

        mark_dropped(telegram_id, tmdb_id, title)
        return f"🚫 Отмечено как dropped: {title}"

    # ==============================
    # РЕКОМЕНДАЦИИ
    # ==============================

    if low.startswith("похожие"):
        movie = text[7:].strip()
        similar = get_similar_movies(movie)

        if not similar:
            return "Не нашёл похожих фильмов 😔"

        return "Похожие фильмы:\n" + "\n".join(f"• {m}" for m in similar)

    if low.startswith("хочу"):
        mood = text[4:].strip()
        recs = recommend_by_mood(mood)

        if not recs:
            return "Не нашёл подходящих фильмов 😔"

        return "Рекомендации:\n" + "\n".join(f"• {m}" for m in recs)

    if low in ("тренды", "что смотрят"):
        trends = get_trending()

        if not trends:
            return "Трендов пока нет 😔"

        return "Тренды недели:\n" + "\n".join(f"• {m}" for m in trends)

    if low.startswith("рекомендации"):
        recs = recommend_by_tags(telegram_id)
        if not recs:
            return "Пока нет персональных рекомендаций 😔"

        return "Персональные рекомендации:\n" + "\n".join(f"• {m}" for m in recs)

    # ==============================
    # СПИСОК МОИХ ФИЛЬМОВ
    # ==============================

    if low == "мои фильмы":
        movies = get_user_movies(telegram_id)

        if not movies:
            return "Список пуст 😔"

        lines = [f"{title} — {status}" for title, _, status in movies]
        return "Мои фильмы:\n" + "\n".join(f"• {l}" for l in lines)

    return (
        "Не понял команду.\n"
        "Попробуй:\n"
        "- смотрел <фильм>\n"
        "- планирую <фильм>\n"
        "- бросил <фильм>\n"
        "- похожие <фильм>\n"
        "- хочу <описание>\n"
        "- тренды\n"
        "- рекомендации\n"
        "- мои фильмы"
    )