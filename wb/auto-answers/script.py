# 🚀 Как это работает:
# process(config) вызывается OpenClaw/Telegram.
# если модуль включён — берём токен.
# запрашиваем новые комментарии.
# для каждого комментария генерим ответ.
# отправляем ответ на маркетплейс.
# возвращаем статус (успешно/нет).


import requests
import logging
import os
from openai import OpenAI

# -----------------------------
# TRIGGERS
# -----------------------------

TRIGGER_WORDS = [
    "суд", "судиться", "полиция", "прокуратура", "жалоба в суд",
    "заявление", "накажу", "юрист", "гнев", "обман",
    "мошенники", "верните деньги", "подаю в суд", "угроза", "разберусь"
]


def contains_trigger(text):
    text = text.lower()
    return any(word in text for word in TRIGGER_WORDS)


# -----------------------------
# TELEGRAM
# -----------------------------

def send_to_telegram(config, comment):
    try:
        bot_token = config["telegram"]["botToken"]
        chat_id = config["telegram"]["chatId"]

        message = (
            "⚠️ Триггерный комментарий\n\n"
            f"{comment.get('text', '')}\n\n"
            f"ID: {comment.get('id')}"
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)

    except Exception as e:
        logging.error(f"Telegram send error: {e}")


# -----------------------------
# CONFIG & TOKENS
# -----------------------------

def get_wb_token(config):
    try:
        return config["wb"]["WB_API_TOKEN"]["apiKey"]
    except (KeyError, TypeError):
        return None


def get_openai_key(config):
    try:
        return config["openai"]["apiKey"]
    except (KeyError, TypeError):
        return os.getenv("OPENAI_API_KEY")


# -----------------------------
# AI: OPENAI (новый SDK >= 1.0.0) OR LOCAL FALLBACK
# -----------------------------

def call_openai(prompt, api_key):
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты помощник продавца Wildberries. Отвечай дружелюбно и по делу."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None


def call_local_ai(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()

    except Exception as e:
        logging.error(f"Ollama error: {e}")

    return "Спасибо за ваш отзыв!"


def generate_answer(comment, config):
    text = comment.get("text", "").strip()
    if not text:
        return "Спасибо за ваш отзыв!"

    api_key = get_openai_key(config)
    if api_key:
        answer = call_openai(text, api_key)
        if answer:
            return answer

    return call_local_ai(text)


# -----------------------------
# API: GET UNANSWERED FEEDBACKS
# Документация: GET /api/v1/feedbacks
# Пагинация: take / skip
# -----------------------------

def get_unanswered_feedbacks(token, skip=0, take=100):
    """
    Получаем только НЕотвеченные отзывы.
    isAnswered=false — ключевой параметр!
    """
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": token}
    params = {
        "isAnswered": "false",   # только без ответа
        "skip": skip,
        "take": take,
        "order": "dateDesc"
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.RequestException as e:
        logging.error(f"WB feedbacks request error: {e}")
        return [], 0

    if r.status_code != 200:
        logging.warning(f"WB feedbacks response code: {r.status_code}, body: {r.text}")
        return [], 0

    data = r.json()
    feedbacks = data.get("data", {}).get("feedbacks", [])
    count_unanswered = data.get("data", {}).get("countUnanswered", 0)

    return feedbacks, count_unanswered


# -----------------------------
# API: SEND ANSWER
# PATCH /api/v1/feedbacks — payload: {"id": "...", "text": "..."}
# -----------------------------

def send_answer(token, feedback_id, answer_text):
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    # ✅ Правильная структура payload (НЕ вложенный "answer")
    payload = {
        "id": feedback_id,
        "text": answer_text
    }

    try:
        r = requests.patch(url, headers=headers, json=payload, timeout=10)
    except requests.RequestException as e:
        logging.error(f"Send answer error: {e}")
        return False

    if r.status_code != 200:
        logging.warning(f"Send answer failed: {r.status_code}, body: {r.text}")
        return False

    return True


# -----------------------------
# PROCESS (MAIN LOGIC)
# -----------------------------

def process(config):
    """
    Основная точка входа:
    - читаем НЕотвеченные отзывы (с пагинацией)
    - если триггер → Telegram (без ответа)
    - иначе → генерим ответ и отправляем
    """
    if not config.get("wb", {}).get("enabled"):
        return []

    token = get_wb_token(config)
    if not token:
        logging.warning("WB token not found")
        return []

    results = []
    skip = 0
    take = 100

    while True:
        feedbacks, count_unanswered = get_unanswered_feedbacks(token, skip=skip, take=take)

        if not feedbacks:
            break

        for c in feedbacks:
            feedback_id = c.get("id")
            if not feedback_id:
                continue

            text = c.get("text", "")

            if contains_trigger(text):
                send_to_telegram(config, c)
                results.append({"id": feedback_id, "action": "sent_to_telegram"})
                continue

            answer = generate_answer(c, config)
            ok = send_answer(token, feedback_id, answer)
            results.append({"id": feedback_id, "answered": ok})

        skip += take

        # если забрали все — выходим
        if skip >= count_unanswered:
            break

    return results