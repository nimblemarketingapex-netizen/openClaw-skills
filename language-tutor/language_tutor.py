import json
import os
from datetime import datetime

DATA_FILE = "language_tutor_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"progress": {}, "words": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def on_message(context):
    """
    Основной обработчик сообщений.
    Поддерживает:
    - /learn <language>  (смешанный режим)
    - /addword <word> - <translation>  (сохранить слово)
    - /flashcards       (карточки)
    - /exam <language>   (режим экзамена)
    - статистика прогресса
    """

    text = context.message.text.strip()
    data = load_data()

    # === Добавление слова ===
    if text.startswith("/addword"):
        try:
            _, rest = text.split(maxsplit=1)
            word, translation = rest.split("-", maxsplit=1)
            word = word.strip()
            translation = translation.strip()

            data["words"].append({
                "word": word,
                "translation": translation,
                "added": datetime.now().isoformat()
            })
            save_data(data)

            context.send(f"✅ Слово сохранено:\n{word} — {translation}")
        except Exception:
            context.send("❌ Формат: /addword слово - перевод")
        return

    # === Карточки (flashcards) ===
    if text.startswith("/flashcards"):
        if not data["words"]:
            context.send("Карточек пока нет. Добавь слова через /addword.")
            return

        card = data["words"][0]  # простая логика: берём первую
        context.send(f"🃏 Карточка:\n{card['word']}\n(попробуй перевести)")
        return

    # === Режим экзамена ===
    if text.startswith("/exam"):
        parts = text.split(maxsplit=1)
        lang = parts[1] if len(parts) > 1 else "english"

        prompt = f"""
        Экзаменационный режим для языка: {lang}.
        Сгенерируй 5 вопросов:
        1) перевод
        2) грамматика
        3) составь предложение
        4) исправь ошибку
        5) короткий диалог

        После ответов пользователя — дай оценку и рекомендации.
        """
        reply = context.llm.call(prompt=prompt, max_tokens=350)
        context.send(reply)
        return

    # === Смешанный режим / обучение ===
    if text.startswith("/learn"):
        parts = text.split(maxsplit=1)
        lang = parts[1] if len(parts) > 1 else "english"

        prompt = f"""
        Ты — языковой тренер.
        Начни смешанную практику языка: {lang}.

        Формат:
        - диалог
        - грамматика
        - задание
        - пример ответа

        Также кратко упомяни карточки и статистику прогресса.
        """

        reply = context.llm.call(prompt=prompt, max_tokens=300)
        context.send(reply)
        return

    # === Статистика прогресса ===
    if text.startswith("/stats"):
        words_count = len(data.get("words", []))
        progress = data.get("progress", {})

        context.send(
            f"📊 Статистика\n"
            f"Сохранённых слов: {words_count}\n"
            f"Прогресс: {progress if progress else 'пока нет данных'}"
        )
        return

    # === Обычный смешанный ответ ===
    prompt = f"""
    Пользователь написал: {text}

    Ответь в смешанном режиме:
    - короткий диалог
    - грамматический совет
    - пример правильной фразы
    """

    reply = context.llm.call(prompt=prompt, max_tokens=250)
    context.send(reply)