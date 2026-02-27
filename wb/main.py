from wb.autoanswers.script import process as process_answers
from wb.analytics.script import process as process_analytics
from wb.warehouse.script import process as process_warehouse
from wb.forecast.script import process as process_forecast
from wb.recommendations.script import process as process_recommendations
from wb.finance.script import process as process_finance
from wb.finance.script import send_daily_digest

# -----------------------------
# ORCHESTRATOR
# -----------------------------

def run_wb_skill(config, date_from=None, date_to=None):
    """
    Главная точка входа.

    Порядок:
    1) автоответы
    2) аналитика
    3) склад
    4) прогноз (использует аналитику + склад)
    5) рекомендации
    """

    results = {}

    # 1. автоответы
    results["answers"] = process_answers(config)

    # 2. аналитика (только если переданы даты)
    analytics = {}
    if date_from and date_to:
        analytics = process_analytics(config, date_from, date_to)
        results["analytics"] = analytics
    else:
        results["analytics"] = {}

    # 3. склад
    stock = process_warehouse(config)
    results["warehouse"] = stock

    # 4. прогноз — передаём и аналитику, и склад
    results["forecast"] = process_forecast(analytics, stock)

    # 5. рекомендации — на основе аналитики
    results["recommendations"] = process_recommendations(analytics)

    # 6. финансовый анализ 
    results["finance"] = process_finance(config, date_from, date_to)

    return results