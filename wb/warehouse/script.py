# 🧠 Что делает этот код

# ✔ остатки по SKU
# ✔ дефицит (<5 шт.)
# ✔ залежавшийся товар (>30 дней без движения)
# ✔ рекомендации
# ✔ обработка ошибок API и конфигурации

import requests
import logging
from collections import defaultdict

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
# API: STOCKS
# -----------------------------

def get_stock_data(token):
    """
    Получаем остатки на складах.
    """
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
    headers = {"Authorization": token}

    try:
        r = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        logging.error(f"Stock API error: {e}")
        return []

    if r.status_code != 200:
        logging.warning(f"Stock API code: {r.status_code}")
        return []

    return r.json()


# -----------------------------
# ANALYSIS
# -----------------------------

def analyze_stocks(data):
    """
    Анализ складских остатков:
    - дефицит
    - залежавшиеся товары
    - общие остатки
    """

    stocks = defaultdict(int)
    low_stock = []
    stale_stock = []

    for item in data:
        sku = item.get("nmId") or item.get("sku")
        stock = int(item.get("quantity", 0))
        updated = item.get("lastChangeDate")  # дата последнего изменения

        if not sku:
            continue

        stocks[sku] += stock

        # дефицит
        if stock < 5:
            low_stock.append(sku)

        # залежавшийся товар (нет движения > 30 дней)
        if updated:
            try:
                from datetime import datetime, timedelta
                last = datetime.fromisoformat(updated.replace("Z", ""))
                if datetime.utcnow() - last > timedelta(days=30):
                    stale_stock.append(sku)
            except Exception:
                pass

    return {
        "total_skus": len(stocks),
        "low_stock": low_stock,
        "stale_stock": stale_stock
    }


# -----------------------------
# RECOMMENDATIONS
# -----------------------------

def generate_recommendations(report):
    recs = []

    if report["low_stock"]:
        recs.append(f"Дефицит SKU: {', '.join(map(str, report['low_stock']))}. Пополните остатки.")

    if report["stale_stock"]:
        recs.append(f"Залежавшиеся SKU: {', '.join(map(str, report['stale_stock']))}. Рассмотрите акцию.")

    if not report["low_stock"] and not report["stale_stock"]:
        recs.append("Склад в хорошем состоянии. Продолжайте мониторинг.")

    return recs


# -----------------------------
# PROCESS (MAIN LOGIC)
# -----------------------------

def process(config):
    """
    Точка входа аналитики склада.
    """
    if not config.get("wb", {}).get("enabled"):
        return {}

    token = get_wb_token(config)
    if not token:
        logging.warning("WB token not found")
        return {}

    stocks = get_stock_data(token)
    if not stocks:
        return {}

    report = analyze_stocks(stocks)
    report["recommendations"] = generate_recommendations(report)

    return report