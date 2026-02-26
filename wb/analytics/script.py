# 🧠 Что делает этот код:
# берёт токен из конфига;
# тянет продажи за период;
# считает:
# заказы,выручку,средний чек;возвращает отчёт.

import requests
import logging
from collections import defaultdict
from datetime import datetime

# -----------------------------
# CONFIG & TOKENS
# -----------------------------

def get_wb_token(config):
    """
    Достаёт API-токен:
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


# -----------------------------
# API: SALES STATISTICS
# -----------------------------

def get_sales_stats(token, date_from, date_to):
    """
    Получаем статистику продаж за период.
    """
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
    headers = {"Authorization": token}
    params = {
        "dateFrom": date_from,
        "dateTo": date_to
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.RequestException as e:
        logging.error(f"Sales stats error: {e}")
        return []

    if r.status_code != 200:
        logging.warning(f"Sales stats code: {r.status_code}")
        return []

    return r.json()


# -----------------------------
# ANALYSIS (IMPROVED)
# -----------------------------

def analyze_sales(data):
    """
    Улучшенная аналитика:
    - GMV
    - заказы
    - средний чек
    - разбивка по товарам
    - динамика по дням
    """

    summary = {
        "total_orders": 0,
        "gmv": 0.0,
        "avg_check": 0.0,
        "by_sku": defaultdict(float),
        "by_date": defaultdict(float)
    }

    for item in data:
        price = float(item.get("priceWithDiscount", 0))
        sku = item.get("nmId") or item.get("sku")
        date = item.get("date")

        summary["total_orders"] += 1
        summary["gmv"] += price

        if sku:
            summary["by_sku"][sku] += price

        if date:
            # нормализуем дату (только день)
            day = date.split("T")[0]
            summary["by_date"][day] += price

    # средний чек
    summary["avg_check"] = (
        summary["gmv"] / summary["total_orders"]
        if summary["total_orders"] else 0
    )

    # топ-товары (5 шт.)
    top_sku = sorted(
        summary["by_sku"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    return {
        "orders": summary["total_orders"],
        "gmv": summary["gmv"],
        "avg_check": summary["avg_check"],
        "top_sku": top_sku,
        "by_date": dict(summary["by_date"])
    }


# -----------------------------
# PROCESS (MAIN LOGIC)
# -----------------------------

def process(config, date_from, date_to):
    """
    Основная точка входа аналитики.
    """
    if not config.get("wb", {}).get("enabled"):
        return {}

    token = get_wb_token(config)
    if not token:
        logging.warning("WB token not found")
        return {}

    stats = get_sales_stats(token, date_from, date_to)
    if not stats:
        return {}

    return analyze_sales(stats)