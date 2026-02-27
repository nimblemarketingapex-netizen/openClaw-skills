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
    - берём реальные продажи по SKU из аналитики (в рублях)
    - сравниваем с остатком из склада (в штуках)
    - считаем, когда закончится товар

    sales_analytics — результат analytics/script.py:
        {
            "by_sku": {sku: revenue_rub, ...},
            "top_sku": [(sku, revenue), ...],
            ...
        }

    stock_report — результат warehouse/script.py:
        {
            "stocks": {sku: qty, ...},
            "low_stock": [...],
            ...
        }
    """

    forecasts = []

    by_sku = sales_analytics.get("by_sku", {})
    stocks = stock_report.get("stocks", {})

    # считаем среднюю цену из аналитики (GMV / заказы)
    total_orders = sales_analytics.get("orders", 0)
    total_gmv = sales_analytics.get("gmv", 0)

    # средняя цена по всем SKU (fallback если нет данных)
    avg_price_global = (total_gmv / total_orders) if total_orders > 0 else 1000

    for sku, revenue in by_sku.items():
        stock_qty = stocks.get(sku, 0)

        # кол-во проданных штук за период (используем среднюю цену)
        # в идеале брать цену конкретного SKU, но аналитика WB отдаёт только GMV
        sold_qty = revenue / avg_price_global

        # среднее в день (период 30 дней)
        avg_per_day = sold_qty / 30

        if avg_per_day <= 0:
            continue

        days_left = stock_qty / avg_per_day

        forecasts.append({
            "sku": sku,
            "stock": stock_qty,
            "avg_per_day": round(avg_per_day, 2),
            "days_left": round(days_left, 1),
            "revenue": round(revenue, 2)
        })

    # сортируем по срочности (меньше дней — первые)
    forecasts.sort(key=lambda x: x["days_left"])

    return forecasts


def generate_recommendations(forecasts):
    recs = []

    for f in forecasts:
        if f["days_left"] < 7:
            recs.append(
                f"🔴 SKU {f['sku']}: закончится примерно через {f['days_left']} дней "
                f"(остаток {f['stock']} шт.). Срочное пополнение!"
            )
        elif f["days_left"] < 14:
            recs.append(
                f"🟡 SKU {f['sku']}: запас на ~{f['days_left']} дней "
                f"(остаток {f['stock']} шт.). Планируйте пополнение."
            )

    if not recs:
        recs.append("✅ Склад и продажи в норме. Риски дефицита не выявлены.")

    return recs


def process(sales_analytics, stock_report):
    """
    Точка входа прогноза.
    """
    if not sales_analytics or not stock_report:
        return {"forecasts": [], "recommendations": ["Нет данных для прогноза."]}

    forecasts = forecast_replenishment(sales_analytics, stock_report)
    return {
        "forecasts": forecasts,
        "recommendations": generate_recommendations(forecasts)
    }