# 🧠 Что делает этот код:
# берёт токен из конфига;
# тянет продажи за период;
# считает:
# заказы,выручку,средний чек;возвращает отчёт.

import requests
import logging
from collections import defaultdict


# -----------------------------
# CONFIG & TOKENS
# -----------------------------

def get_wb_token(config):
    try:
        return config["wb"]["WB_API_TOKEN"]["apiKey"]
    except (KeyError, TypeError):
        return None


# -----------------------------
# API: SALES STATISTICS
# GET /api/v1/supplier/sales
# dateFrom — дата начала (включительно), dateTo НЕ поддерживается
# Пагинация: если ответ не пустой — запрашиваем дальше по lastChangeDate
# -----------------------------

def get_sales_stats(token, date_from, date_to=None):
    """
    Получаем продажи начиная с date_from.
    date_to — используем для фильтрации на стороне клиента,
    т.к. API принимает только dateFrom.

    date_from формат: "2024-01-01"
    """
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
    headers = {"Authorization": token}

    all_sales = []
    current_date_from = date_from

    while True:
        params = {"dateFrom": current_date_from}

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.RequestException as e:
            logging.error(f"Sales stats request error: {e}")
            break

        if r.status_code != 200:
            logging.warning(f"Sales stats code: {r.status_code}, body: {r.text}")
            break

        try:
            data = r.json()
        except Exception:
            logging.error("Failed to parse sales stats JSON")
            break

        if not data:
            break

        # фильтруем по date_to на клиенте (если передан)
        if date_to:
            filtered = [
                item for item in data
                if item.get("lastChangeDate", "") <= date_to + "T23:59:59"
            ]
        else:
            filtered = data

        all_sales.extend(filtered)

        # пагинация: берём lastChangeDate последней записи
        last_date = data[-1].get("lastChangeDate")
        if not last_date or len(data) < 500:
            # меньше 500 записей — значит это последняя страница
            break

        current_date_from = last_date  # следующий запрос с этой даты

    return all_sales


# -----------------------------
# ANALYSIS
# -----------------------------

def analyze_sales(data):
    summary = {
        "total_orders": 0,
        "gmv": 0.0,
        "avg_check": 0.0,
        "by_sku": defaultdict(float),
        "by_date": defaultdict(float)
    }

    for item in data:
        # WB возвращает priceWithDiscount или forPay
        price = float(item.get("priceWithDiscount") or item.get("forPay") or 0)
        sku = item.get("nmId") or item.get("nmID") or item.get("sku")
        date = item.get("date") or item.get("lastChangeDate")

        summary["total_orders"] += 1
        summary["gmv"] += price

        if sku:
            summary["by_sku"][sku] += price

        if date:
            day = date.split("T")[0]
            summary["by_date"][day] += price

    summary["avg_check"] = (
        summary["gmv"] / summary["total_orders"]
        if summary["total_orders"] else 0
    )

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
        "by_sku": dict(summary["by_sku"]),   # ← добавлено для forecast
        "by_date": dict(summary["by_date"])
    }


# -----------------------------
# PROCESS
# -----------------------------

def process(config, date_from, date_to):
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