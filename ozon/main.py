# =============================================================
# ozon/main.py — оркестратор скилла Ozon
# =============================================================

from ozon.autoanswers.script import process_reviews, process_questions
from ozon.analytics.script import process as process_analytics
from ozon.finance.script import process as process_finance
from ozon.recommendations.script import process as process_recommendations


def run_ozon_skill(config: dict, date_from: str = None, date_to: str = None) -> dict:
    """
    Главная точка входа.

    Порядок:
    1) автоответы на отзывы
    2) ответы на вопросы
    3) аналитика продаж и склада
    4) финансы
    5) рекомендации
    """

    results = {}

    # 1. Автоответы на отзывы
    results["reviews"] = process_reviews(config)

    # 2. Ответы на вопросы покупателей
    results["questions"] = process_questions(config)

    # 3. Аналитика (только если передан период)
    if date_from and date_to:
        analytics = process_analytics(config, date_from, date_to)
        results["analytics"] = analytics
    else:
        analytics = {}

    # 4. Финансы
    if date_from and date_to:
        finance = process_finance(config, date_from, date_to)
        results["finance"] = finance
    else:
        finance = {}

    # 5. Рекомендации на основе аналитики
    results["recommendations"] = process_recommendations(analytics, finance)

    return results