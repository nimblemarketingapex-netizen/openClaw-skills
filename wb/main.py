from wb.autoanswers.script import process as process_answers
from wb.analytics.script import process as process_analytics
from wb.warehouse.script import process as process_warehouse
from wb.forecast.script import process as process_forecast
from wb.recommendations.script import process as process_recommendations

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
    4) прогноз
    5) рекомендации
    """

    results = {}

    # автоответы
    results["answers"] = process_answers(config)

    # аналитика
    if date_from and date_to:
        analytics = process_analytics(config, date_from, date_to)
        results["analytics"] = analytics
    else:
        analytics = {}

    # склад
    stock = process_warehouse(config)
    results["warehouse"] = stock

    # прогноз
    forecast = process_forecast(analytics, stock)
    results["forecast"] = forecast

    # рекомендации
    recommendations = process_recommendations(analytics)
    results["recommendations"] = recommendations

    return results