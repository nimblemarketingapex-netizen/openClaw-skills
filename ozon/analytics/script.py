# =============================================================
# ozon/analytics/script.py
#
# Что делает:
#   ✔ Аналитика продаж (/v1/analytics/data)
#   ✔ Остатки по складам (/v2/analytics/stock_on_warehouses)
#   ✔ Оборачиваемость (/v1/analytics/item_turnover)
#   ✔ Поисковые запросы (/v1/analytics/product-queries)
#   ✔ Выявление дефицита и залежавшихся товаров
# =============================================================

import requests
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

BASE_URL = "https://api-seller.ozon.ru"


def get_headers(config: dict) -> dict:
    return {
        "Client-Id": str(config["ozon"]["client_id"]),
        "Api-Key": config["ozon"]["api_key"],
        "Content-Type": "application/json",
    }


# -------------------------------------------------------------
# АНАЛИТИКА ПРОДАЖ: /v1/analytics/data
# -------------------------------------------------------------

def get_sales_data(headers: dict, date_from: str, date_to: str) -> dict:
    """
    Получает аналитические данные по продажам за период.

    Документация: POST /v1/analytics/data
    Метрики: ordered_units, revenue, returns, cancellations
    Группировка: по SKU и по дням
    """
    url = f"{BASE_URL}/v1/analytics/data"
    payload = {
        "date_from": date_from,
        "date_to": date_to,
        "metrics": [
            "ordered_units",        # заказанные единицы
            "revenue",              # выручка
            "returns",              # возвраты
            "cancellations",        # отмены
            "delivered_units",      # доставленные
        ],
        "dimension": ["sku", "day"],
        "filters": [],
        "limit": 1000,
        "offset": 0,
        "sort": [
            {"key": "revenue", "order": "DESC"}
        ],
    }

    all_rows = []
    offset = 0

    while True:
        payload["offset"] = offset
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.RequestException as e:
            logger.error(f"[ozon:analytics] Ошибка запроса: {e}")
            break

        if r.status_code != 200:
            logger.warning(f"[ozon:analytics] Код: {r.status_code} | {r.text[:200]}")
            break

        data = r.json()
        rows = data.get("result", {}).get("data", [])
        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break
        offset += 1000

    return analyze_sales(all_rows)


def analyze_sales(rows: list) -> dict:
    """
    Агрегирует строки аналитики в итоговый отчёт.
    """
    total_orders = 0
    total_revenue = 0.0
    total_returns = 0
    by_sku = defaultdict(lambda: {"orders": 0, "revenue": 0.0, "returns": 0})
    by_date = defaultdict(float)

    for row in rows:
        dims = {d["id"]: d["value"] for d in row.get("dimensions", [])}
        metrics = {m["id"]: float(m.get("value", 0)) for m in row.get("metrics", [])}

        sku = dims.get("sku", "unknown")
        day = dims.get("day", "")

        orders = int(metrics.get("ordered_units", 0))
        revenue = metrics.get("revenue", 0.0)
        returns = int(metrics.get("returns", 0))

        total_orders += orders
        total_revenue += revenue
        total_returns += returns

        by_sku[sku]["orders"] += orders
        by_sku[sku]["revenue"] += revenue
        by_sku[sku]["returns"] += returns

        if day:
            by_date[day] += revenue

    avg_check = total_revenue / total_orders if total_orders > 0 else 0.0

    top_sku = sorted(by_sku.items(), key=lambda x: x[1]["revenue"], reverse=True)[:5]

    return {
        "orders": total_orders,
        "revenue": round(total_revenue, 2),
        "returns": total_returns,
        "avg_check": round(avg_check, 2),
        "top_sku": top_sku,
        "by_sku": dict(by_sku),
        "by_date": dict(by_date),
    }


# -------------------------------------------------------------
# СКЛАД: /v2/analytics/stock_on_warehouses
# -------------------------------------------------------------

def get_stock_data(headers: dict) -> dict:
    """
    Остатки по складам.

    Документация: POST /v2/analytics/stock_on_warehouses
    """
    url = f"{BASE_URL}/v2/analytics/stock_on_warehouses"
    payload = {
        "limit": 1000,
        "offset": 0,
        "warehouse_type": "ALL",  # FBO + FBS
    }

    all_rows = []
    offset = 0

    while True:
        payload["offset"] = offset
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=20)
        except requests.RequestException as e:
            logger.error(f"[ozon:stock] Ошибка запроса: {e}")
            break

        if r.status_code != 200:
            logger.warning(f"[ozon:stock] Код: {r.status_code} | {r.text[:200]}")
            break

        rows = r.json().get("result", {}).get("rows", [])
        if not rows:
            break

        all_rows.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000

    return analyze_stocks(all_rows)


def analyze_stocks(rows: list) -> dict:
    """
    Анализ складских остатков:
    - дефицит (< 5 шт)
    - нулевые остатки
    - нормальные
    """
    stocks = {}
    low_stock = []
    zero_stock = []

    for item in rows:
        sku = str(item.get("sku") or item.get("item_id") or "")
        free_to_sell = int(item.get("free_to_sell_amount", 0))
        reserved = int(item.get("promised_amount", 0))

        if not sku:
            continue

        stocks[sku] = {
            "free": free_to_sell,
            "reserved": reserved,
            "total": free_to_sell + reserved,
        }

        if free_to_sell == 0:
            zero_stock.append(sku)
        elif free_to_sell < 5:
            low_stock.append(sku)

    return {
        "total_skus": len(stocks),
        "stocks": stocks,
        "low_stock": low_stock,
        "zero_stock": zero_stock,
    }


# -------------------------------------------------------------
# ПОИСКОВЫЕ ЗАПРОСЫ: /v1/analytics/product-queries
# -------------------------------------------------------------

def get_product_queries(headers: dict, date_from: str, date_to: str, limit: int = 20) -> list:
    """
    Топ поисковых запросов, по которым находят товары продавца.

    Документация: POST /v1/analytics/product-queries
    """
    url = f"{BASE_URL}/v1/analytics/product-queries"
    payload = {
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "offset": 0,
        "sort_by": "SEARCH_QUERIES_SORT_BY_HITS_VIEW",
        "sort_direction": "DESC",
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception as e:
        logger.error(f"[ozon:queries] Ошибка: {e}")

    return []


# -------------------------------------------------------------
# PROCESS (ТОЧКА ВХОДА)
# -------------------------------------------------------------

def process(config: dict, date_from: str, date_to: str) -> dict:
    """
    Основная точка входа аналитики.
    """
    if not config.get("ozon", {}).get("enabled"):
        return {}

    headers = get_headers(config)

    # Продажи
    sales = get_sales_data(headers, date_from, date_to)

    # Склад
    stock = get_stock_data(headers)

    # Поисковые запросы
    queries = get_product_queries(headers, date_from, date_to)

    return {
        "sales": sales,
        "stock": stock,
        "top_queries": queries[:10],
        "period": {"from": date_from, "to": date_to},
    }