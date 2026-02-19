import requests
from bs4 import BeautifulSoup
import re
import json

# Если у тебя есть локальная модель в OpenClaw, можно импортировать её API:
# from openclaw import model as openclaw_model

def fetch_page(url):
    """Загружает страницу и возвращает HTML-код"""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Ошибка при загрузке страницы: {e}"

def extract_text(html):
    """Извлекает читаемый текст со страницы"""
    soup = BeautifulSoup(html, "lxml")
    
    # Удаляем скрипты, стили и пустые теги
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    text = soup.get_text(separator="\n")
    # Очистка лишних пробелов
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()
    return text

def analyze_content(text, url, model=None):
    """
    Универсальный анализ текста.
    Если model=None, OpenClaw выбирает текущую модель по умолчанию.
    """
    prompt = f"""
Ты — эксперт по маркетингу и UX. Проанализируй сайт {url}.
Определи:
1. Основной продукт/услугу компании.
2. Целевую аудиторию.
3. Основные офферы и уникальные преимущества.
4. Слабые места сайта (UX, контент, визуальное оформление).
5. Предложения по улучшению сайта, контента и офферов.

Отдай результат в JSON со структурой:
{{
  "company_summary": "...",
  "audience": "...",
  "offers": ["..."],
  "weak_points": ["..."],
  "recommendations": ["..."]
}}
"""
    if model:
        # Пример вызова локальной модели
        return model.run(prompt)
    else:
        # Использовать модель по умолчанию OpenClaw
        import openclaw
        result_text = openclaw.model.run(prompt)
    
    # Попытка конвертировать в JSON
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {"raw_output": result_text}

def site_analysis(url, model=None):
    """Главная функция скилла — возвращает структурированный анализ сайта"""
    html = fetch_page(url)
    if html.startswith("Ошибка"):
        return {"error": html}
    
    text = extract_text(html)
    analysis = analyze_content(text, url, model=model)
    return analysis

# Пример использования
if __name__ == "__main__":
    url = "https://example.com"  # замените на URL сайта
    result = site_analysis(url)
    print(json.dumps(result, indent=2, ensure_ascii=False))