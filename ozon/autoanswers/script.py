# =============================================================
# ozon/autoanswers/script.py
#
# Что делает:
#   ✔ Получает новые отзывы без ответа (/v1/review/list)
#   ✔ Генерирует ответ через AI (OpenAI или Ollama)
#   ✔ Отправляет ответ (/v1/review/comment/create)
#   ✔ Получает вопросы покупателей (/v1/question/list)
#   ✔ Отвечает на вопросы (/v1/question/answer/create)
#   ✔ Фильтрует триггерные слова → эскалация в Telegram
# =============================================================

import requests
import logging
import os

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)

BASE_URL = "https://api-seller.ozon.ru"

# -------------------------------------------------------------
# ТРИГГЕРНЫЕ СЛОВА (угрозы, юридические претензии)
# -------------------------------------------------------------
TRIGGER_WORDS = [
    "суд", "судиться", "полиция", "прокуратура",
    "жалоба", "заявление", "юрист", "адвокат",
    "мошенники", "обман", "верните деньги",
    "подаю в суд", "роспотребнадзор", "штраф",
]


def contains_trigger(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in TRIGGER_WORDS)


# -------------------------------------------------------------
# HELPERS: КОНФИГ
# -------------------------------------------------------------

def get_headers(config: dict) -> dict:
    """
    Ozon требует два заголовка: Client-Id и Api-Key.
    Все запросы — POST с JSON.
    """
    return {
        "Client-Id": str(config["ozon"]["client_id"]),
        "Api-Key": config["ozon"]["api_key"],
        "Content-Type": "application/json",
    }


def get_tg_config(config: dict) -> tuple:
    try:
        return config["telegram"]["botToken"], config["telegram"]["chatId"]
    except (KeyError, TypeError):
        return None, None


def get_openai_key(config: dict) -> str | None:
    try:
        return config["openai"]["apiKey"]
    except (KeyError, TypeError):
        return os.getenv("OPENAI_API_KEY")


# -------------------------------------------------------------
# TELEGRAM
# -------------------------------------------------------------

def send_to_telegram(config: dict, text: str) -> None:
    bot_token, chat_id = get_tg_config(config)
    if not bot_token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"[ozon:tg] Ошибка: {e}")


# -------------------------------------------------------------
# AI: ГЕНЕРАЦИЯ ОТВЕТА
# -------------------------------------------------------------

def call_openai(prompt: str, api_key: str) -> str | None:
    if openai is None:
        return None
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": (
                    "Ты помощник продавца на маркетплейсе Ozon. "
                    "Отвечай вежливо, по делу, не более 3 предложений."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[ozon:openai] Ошибка: {e}")
        return None


def call_local_ai(prompt: str) -> str:
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"[ozon:ollama] Ошибка: {e}")
    return "Спасибо за ваш отзыв! Мы ценим ваше мнение."


def generate_answer(text: str, config: dict) -> str:
    if not text:
        return "Спасибо за ваш отзыв!"
    api_key = get_openai_key(config)
    if api_key:
        answer = call_openai(text, api_key)
        if answer:
            return answer
    return call_local_ai(text)


# -------------------------------------------------------------
# ОТЗЫВЫ: /v1/review/list + /v1/review/comment/create
# -------------------------------------------------------------

def get_reviews(headers: dict, last_id: str = "") -> tuple[list, str]:
    """
    Получает список отзывов.
    Пагинация через last_id (возвращается в ответе).

    Документация: POST /v1/review/list
    """
    url = f"{BASE_URL}/v1/review/list"
    payload = {
        "filter": {
            "is_processed": False,  # только без ответа
        },
        "limit": 50,
        "last_id": last_id,
        "sort": {
            "sort_by": "REVIEW_SORT_BY_PUBLISHED_AT",
            "sort_direction": "DESC",
        },
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        logger.error(f"[ozon:reviews] Ошибка запроса: {e}")
        return [], ""

    if r.status_code != 200:
        logger.warning(f"[ozon:reviews] Код: {r.status_code} | {r.text[:200]}")
        return [], ""

    data = r.json()
    reviews = data.get("reviews", [])
    next_last_id = data.get("last_id", "")
    return reviews, next_last_id


def send_review_answer(headers: dict, review_id: str, text: str) -> bool:
    """
    Отправляет ответ на отзыв.

    Документация: POST /v1/review/comment/create
    """
    url = f"{BASE_URL}/v1/review/comment/create"
    payload = {
        "review_id": review_id,
        "text": text,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"[ozon:reviews] Ошибка отправки ответа: {e}")
        return False


def process_reviews(config: dict) -> list:
    """
    Точка входа: обработка отзывов.
    """
    if not config.get("ozon", {}).get("enabled"):
        return []

    headers = get_headers(config)
    results = []
    last_id = ""

    while True:
        reviews, last_id = get_reviews(headers, last_id)
        if not reviews:
            break

        for review in reviews:
            review_id = review.get("review_id") or review.get("uuid")
            if not review_id:
                continue

            text = review.get("text", "")

            # Триггер → Telegram без ответа
            if contains_trigger(text):
                send_to_telegram(config,
                    f"⚠️ Ozon — триггерный отзыв\n\n{text[:500]}\n\nID: {review_id}"
                )
                results.append({"id": review_id, "action": "sent_to_telegram"})
                continue

            # Генерируем и отправляем ответ
            answer = generate_answer(text, config)
            ok = send_review_answer(headers, review_id, answer)
            results.append({"id": review_id, "answered": ok})

        # Если пришло меньше 50 — конец пагинации
        if len(reviews) < 50 or not last_id:
            break

    logger.info(f"[ozon:reviews] Обработано: {len(results)}")
    return results


# -------------------------------------------------------------
# ВОПРОСЫ: /v1/question/list + /v1/question/answer/create
# -------------------------------------------------------------

def get_questions(headers: dict, page: int = 1) -> list:
    """
    Получает вопросы покупателей без ответа.

    Документация: POST /v1/question/list
    """
    url = f"{BASE_URL}/v1/question/list"
    payload = {
        "filter": {
            "is_processed": False,
        },
        "page": page,
        "page_size": 50,
        "sort": {
            "sort_by": "QUESTION_SORT_BY_PUBLISHED_AT",
            "sort_direction": "DESC",
        },
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        logger.error(f"[ozon:questions] Ошибка запроса: {e}")
        return []

    if r.status_code != 200:
        logger.warning(f"[ozon:questions] Код: {r.status_code} | {r.text[:200]}")
        return []

    return r.json().get("questions", [])


def send_question_answer(headers: dict, question_id: str, text: str) -> bool:
    """
    Отправляет ответ на вопрос покупателя.

    Документация: POST /v1/question/answer/create
    """
    url = f"{BASE_URL}/v1/question/answer/create"
    payload = {
        "question_id": question_id,
        "text": text,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"[ozon:questions] Ошибка отправки ответа: {e}")
        return False


def process_questions(config: dict) -> list:
    """
    Точка входа: обработка вопросов покупателей.
    """
    if not config.get("ozon", {}).get("enabled"):
        return []

    headers = get_headers(config)
    results = []
    page = 1

    while True:
        questions = get_questions(headers, page)
        if not questions:
            break

        for q in questions:
            question_id = q.get("question_id") or q.get("uuid")
            if not question_id:
                continue

            text = q.get("text", "")

            # Триггер → Telegram
            if contains_trigger(text):
                send_to_telegram(config,
                    f"⚠️ Ozon — триггерный вопрос\n\n{text[:500]}\n\nID: {question_id}"
                )
                results.append({"id": question_id, "action": "sent_to_telegram"})
                continue

            answer = generate_answer(text, config)
            ok = send_question_answer(headers, question_id, answer)
            results.append({"id": question_id, "answered": ok})

        if len(questions) < 50:
            break
        page += 1

    logger.info(f"[ozon:questions] Обработано: {len(results)}")
    return results