import sqlite3
from datetime import datetime

DB_NAME = "cinema.db"

_initialized = False


def get_connection():
    """
    Получить соединение с SQLite.
    """
    return sqlite3.connect(DB_NAME)


def init_db():
    """
    Инициализация базы данных.
    Создаёт таблицы, если их нет.
    Выполняется один раз.
    """
    global _initialized
    if _initialized:
        return

    _initialized = True

    conn = get_connection()
    cursor = conn.cursor()

    # таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id TEXT UNIQUE
    )
    """)

    # таблица фильмов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tmdb_id INTEGER UNIQUE,
        title TEXT
    )
    """)

    # связь пользователь ↔ фильм (статус)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_id INTEGER,
        status TEXT,
        updated_at TEXT,
        UNIQUE(user_id, movie_id)
    )
    """)

    # таблица тегов (умные рекомендации)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movie_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER,
        tag TEXT,
        UNIQUE(movie_id, tag)
    )
    """)

    conn.commit()
    conn.close()


def add_user(telegram_id):
    """
    Добавляет пользователя (если его нет).
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
        (telegram_id,)
    )

    conn.commit()
    conn.close()


def save_movie(tmdb_id, title):
    """
    Сохраняет фильм в базе (если не существует).
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO movies (tmdb_id, title) VALUES (?, ?)",
        (tmdb_id, title)
    )

    conn.commit()
    conn.close()


def set_movie_status(telegram_id, tmdb_id, title, status):
    """
    Сохраняет/обновляет статус фильма для пользователя.
    status: watched | in_progress | planned | dropped
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    # убедимся, что пользователь есть
    cursor.execute(
        "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
        (telegram_id,)
    )
    cursor.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    user_id = row[0]

    # убедимся, что фильм есть
    cursor.execute(
        "INSERT OR IGNORE INTO movies (tmdb_id, title) VALUES (?, ?)",
        (tmdb_id, title)
    )
    cursor.execute(
        "SELECT id FROM movies WHERE tmdb_id = ?",
        (tmdb_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    movie_id = row[0]

    # связь пользователь ↔ фильм
    cursor.execute("""
    INSERT OR REPLACE INTO user_movies (user_id, movie_id, status, updated_at)
    VALUES (?, ?, ?, ?)
    """, (user_id, movie_id, status, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()


def get_user_movies(telegram_id, status=None):
    """
    Получить фильмы пользователя (опционально по статусу).
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT movies.title, movies.tmdb_id, user_movies.status
    FROM user_movies
    JOIN users ON users.id = user_movies.user_id
    JOIN movies ON movies.id = user_movies.movie_id
    WHERE users.telegram_id = ?
    """

    params = [telegram_id]

    if status:
        query += " AND user_movies.status = ?"
        params.append(status)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return results


# ==============================
# ТЕГИ (умные рекомендации)
# ==============================

def add_tag(tmdb_id, tag):
    """
    Добавить тег к фильму.
    tag: строка (например: космос, драма, фантастика)
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM movies WHERE tmdb_id = ?",
        (tmdb_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    movie_id = row[0]

    cursor.execute("""
    INSERT OR IGNORE INTO movie_tags (movie_id, tag)
    VALUES (?, ?)
    """, (movie_id, tag))

    conn.commit()
    conn.close()


def get_tags(tmdb_id):
    """
    Получить теги фильма.
    """
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT tag FROM movie_tags
    JOIN movies ON movies.id = movie_tags.movie_id
    WHERE movies.tmdb_id = ?
    """, (tmdb_id,))

    tags = [row[0] for row in cursor.fetchall()]
    conn.close()

    return tags


# ==============================
# СТАТУСЫ (planned / dropped)
# ==============================

def mark_status(telegram_id, tmdb_id, title, status):
    """
    Универсальная смена статуса.
    status: watched | in_progress | planned | dropped
    """
    set_movie_status(telegram_id, tmdb_id, title, status)


def mark_planned(telegram_id, tmdb_id, title):
    """
    Пометить фильм как planned.
    """
    mark_status(telegram_id, tmdb_id, title, "planned")


def mark_dropped(telegram_id, tmdb_id, title):
    """
    Пометить фильм как dropped.
    """
    mark_status(telegram_id, tmdb_id, title, "dropped")