# 🧠 Что делает этот код

# ✔ берёт продажи (аналитика)
# ✔ берёт остатки (склад)
# ✔ считает средние продажи
# ✔ прогнозирует дни до дефицита
# ✔ даёт рекомендации

from datetime import datetime, timedelta
import logging

def forecast_replenishment(sales_analytics, stock_report):
    """
    Прогноз пополнения:
    - берём средние продажи
    - сравниваем с остатком
    - считаем, когда закончится товар
    """

    forecasts = []

    # продажи по SKU (из аналитики)
    by_sku = sales_analytics.get("by_sku", {})
    low_stock = stock_report.get("low_stock", [])

    for sku, revenue in by_sku.items():
        # предположим средняя цена 1000 -> конвертируем в кол-во (очень упрощённо)
        avg_price = 1000
        sold_qty = revenue / avg_price

        # средние продажи в день (если период = 30 дней)
        avg_per_day = sold_qty / 30

        # остаток
        stock_qty = 0
        if hasattr(stock_report, "get"):
            stocks = stock_report.get("stocks", {})
            stock_qty = stocks.get(sku, 0)

        if avg_per_day <= 0:
            continue

        days_left = stock_qty / avg_per_day

        forecasts.append({
            "sku": sku,
            "stock": stock_qty,
            "avg_per_day": avg_per_day,
            "days_left": round(days_left, 1)
        })

    return forecasts


def generate_recommendations(forecasts):
    """
    Рекомендации на основе прогноза.
    """
    recs = []

    for f in forecasts:
        if f["days_left"] < 7:
            recs.append(
                f"SKU {f['sku']} закончится примерно через {f['days_left']} дней. "
                "Рекомендуется пополнение."
            )
        elif f["days_left"] < 14:
            recs.append(
                f"SKU {f['sku']} запас на ~{f['days_left']} дней. "
                "Планируйте пополнение."
            )

    if not recs:
        recs.append("Склад и продажи в норме. Риски дефицита не выявлены.")

    return recs


def process(sales_analytics, stock_report):
    """
    Точка входа прогноза.
    """
    forecasts = forecast_replenishment(sales_analytics, stock_report)
    return {
        "forecasts": forecasts,
        "recommendations": generate_recommendations(forecasts)
    }