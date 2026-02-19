import json

# Опционально: импорт локальной модели OpenClaw
# from openclaw import model as openclaw_model

def generate_strategy(business_info, competitors_info=None, model=None):
    """
    Генерирует маркетинговую стратегию.
    :param business_info: текстовое описание бизнеса, оффера, ЦА
    :param competitors_info: текстовое описание конкурентов (необязательно)
    :param model: модель для анализа; если None, используется модель по умолчанию OpenClaw
    :return: JSON с SWOT, стратегией, планом на 3 месяца
    """
    prompt = f"""
Ты — эксперт по маркетингу и бизнес-стратегиям.
На основе информации о бизнесе:
{business_info}

И конкурентах (если есть):
{competitors_info if competitors_info else 'Нет данных о конкурентах.'}

Выполни следующие задачи:
1. Определи нишу, ЦА, оффер и позиционирование.
2. Сделай SWOT-анализ: сильные и слабые стороны, возможности и угрозы.
3. Предложи маркетинговую стратегию:
   - Привлечение клиентов
   - Контент-стратегия
   - Рекламная стратегия
   - Быстрые улучшения
4. Составь план действий на 3 месяца (по неделям), с конкретными шагами.
5. Выдавай **только структурированный JSON** со следующей структурой:

{{
  "business_summary": "...",
  "audience": "...",
  "offer_and_positioning": "...",
  "swot": {{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "opportunities": ["..."],
    "threats": ["..."]
  }},
  "strategy": {{
    "customer_acquisition": ["..."],
    "content_strategy": ["..."],
    "ad_strategy": ["..."],
    "quick_wins": ["..."],
    "3_month_plan": {{
      "month_1": ["..."],
      "month_2": ["..."],
      "month_3": ["..."]
    }}
  }}
}}
"""

    # Вызов модели
    if model:
        result_text = model.run(prompt)
    else:
        import openclaw
        result_text = openclaw.model.run(prompt)

    # Попытка превратить в JSON
    try:
        result_json = json.loads(result_text)
    except json.JSONDecodeError:
        result_json = {"raw_output": result_text}

    return result_json


# Пример использования
if __name__ == "__main__":
    business_info = """
Компания занимается производством органической косметики для женщин 25-45 лет.
Основной оффер: натуральные средства без химии, для чувствительной кожи.
Основная цель: увеличить онлайн-продажи и узнаваемость бренда.
"""
    competitors_info = """
Конкуренты предлагают аналогичную косметику, делают упор на низкую цену.
Сильная конкуренция в Instagram и TikTok.
"""

    strategy = generate_strategy(business_info, competitors_info)
    print(json.dumps(strategy, indent=2, ensure_ascii=False))