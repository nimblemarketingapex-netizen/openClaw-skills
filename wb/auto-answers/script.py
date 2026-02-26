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
import openai

# -----------------------------
# CONFIG & TOKENS
# -----------------------------

def get_wb_token(config):
    """
    Достаёт API-токен Wildberries:
    {
      "wb": {
        "enabled": true,
        "WB_API_TOKEN": {"apiKey": "KEY"}
      }
    }
    """
    try:
        return config["wb"]["WB_API_TOKEN"]["apiKey"]
    except (KeyError, TypeError):
        return None


def get_openai_key(config):
    """
    Достаёт ключ OpenAI из конфига:
    {
      "openai": {"apiKey": "KEY"}
    }
    """
    try:
        return config["openai"]["apiKey"]
    except (KeyError, TypeError):
        return os.getenv("OPENAI_API_KEY")


# -----------------------------
# AI: OPENAI OR LOCAL FALLBACK
# -----------------------------

def call_openai(prompt, api_key):
    """
    Вызов OpenAI GPT.
    """
    openai.api_key = api_key

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты помощник продавца Wildberries. Отвечай дружелюбно и по делу."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None


def call_local_ai(prompt):
    """
    Локальная заглушка, если OpenAI недоступен.
    """
    return "Спасибо за ваш отзыв! Мы работаем над улучшением сервиса."


def generate_answer(comment, config):
    """
    Генерация ответа:
    1) OpenAI (если ключ есть)
    2) локальный fallback
    """
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
# API: GET NEW COMMENTS
# -----------------------------

def get_new_comments(token, page=1, page_size=50):
    """
    Получаем новые комментарии/отзывы (пагинация).
    """
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {"Authorization": token}
    params = {"page": page, "pageSize": page_size}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.RequestException as e:
        logging.error(f"WB API request error: {e}")
        return []

    if r.status_code != 200:
        logging.warning(f"WB API response code: {r.status_code}")
        return []

    data = r.json()
    return data.get("data", [])


# -----------------------------
# API: SEND ANSWER
# -----------------------------

def send_answer(token, feedback_id, answer):
    """
    Отправка ответа на комментарий.
    """
    url = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    payload = {
        "id": feedback_id,
        "answer": {"text": answer}
    }

    try:
        r = requests.patch(url, headers=headers, json=payload, timeout=10)
    except requests.RequestException as e:
        logging.error(f"Send answer error: {e}")
        return False

    return r.status_code == 200


# -----------------------------
# PROCESS (MAIN LOGIC)
# -----------------------------

def process(config):
    """
    Основная точка входа:
    - проверяем модуль
    - берём токен
    - читаем комментарии
    - генерим ответы
    - отправляем
    - возвращаем статус
    """
    if not config.get("wb", {}).get("enabled"):
        return []

    token = get_wb_token(config)
    if not token:
        logging.warning("WB token not found")
        return []

    results = []
    page = 1

    while True:
        comments = get_new_comments(token, page=page)
        if not comments:
            break

        for c in comments:
            feedback_id = c.get("id")
            if not feedback_id:
                continue

            answer = generate_answer(c, config)
            ok = send_answer(token, feedback_id, answer)

            results.append({
                "id": feedback_id,
                "answered": ok
            })

        page += 1

    return results