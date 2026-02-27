import requests
import logging

def call_local_llm(prompt):
    """
    Отправляем запрос в локальный Ollama.
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("response", "").strip()

    except Exception as e:
        logging.error(f"Ollama error: {e}")

    return "Не удалось сгенерировать краткое содержание."


def summarize_text(content):
    """
    Формируем промпт для резюме.
    """
    prompt = (
        "Сделай краткое содержание текста. "
        "Выдели главное, не растекайся: \n\n"
        f"{content}"
    )
    return call_local_llm(prompt)


def process(config):
    """
    Точка входа OpenClaw.
    Ожидаем в config:
    {
      "text": "...",   # или URL/контент
    }
    """
    text = config.get("text")
    if not text:
        return {"error": "No text provided"}

    summary = summarize_text(text)
    return {"summary": summary}