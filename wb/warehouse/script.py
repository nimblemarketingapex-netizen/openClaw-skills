# 🧠 Что делает этот код

# ✔ остатки по SKU
# ✔ дефицит (<5 шт.)
# ✔ залежавшийся товар (>30 дней без движения)
# ✔ рекомендации
# ✔ обработка ошибок API и конфигурации

import requests
import logging
from collections import defaultdict
from datetime import datetime, timedelta


# -----------------------------
# CONFIG & TOKENS
# -----------------------------

def get_wb_token(config):
    try:
        return config["wb"]["WB_API_TOKEN"]["apiKey"]
    except (KeyError, TypeError):
        return None


# -----------------------------
# API: STOCKS
# GET /api/v1/supplier/stocks
# dateFrom — фильтр по lastChangeDate (дата последнего изменения)
# Лимит: 60 000 строк за запрос — нужна пагинация!
# -----------------------------

def get_stock_data(token):
    """
    Получаем актуальные остатки по всем складам.
    Пагинация через lastChangeDate последней записи.
    """
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
    headers = {"Authorization": token}

    # берём данные с изменениями за последние 90 дней
    date_from = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_stocks = []
    current_date_from = date_from

    while True:
        params = {"dateFrom": current_date_from}

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.RequestException as e:
            logging.error(f"Stock API error: {e}")
            break

        if r.status_code != 200:
            logging.warning(f"Stock API code: {r.status_code}, body: {r.text}")
            break

        try:
            data = r.json()
        except Exception:
            logging.error("Failed to parse stocks JSON")
            break

        if not data:
            # пустой массив = все остатки получены
            break

        all_stocks.extend(data)

        # если меньше 60 000 — это последняя страница
        if len(data) < 60000:
            break

        # берём lastChangeDate последней записи для следующего запроса
        last_date = data[-1].get("lastChangeDate")
        if not last_date:
            break

        current_date_from = last_date

    return all_stocks


# -----------------------------
# ANALYSIS
# -----------------------------

def analyze_stocks(data):
    """
    Анализ складских остатков:
    - общий остаток по SKU (stocks dict — нужен для forecast)
    - дефицит < 5 шт.
    - залежавшийся товар (нет движения > 30 дней)
    """
    stocks = defaultdict(int)       # SKU → суммарный остаток
    low_stock = []
    stale_stock = []
    seen_stale = set()              # чтобы не дублировать SKU

    for item in data:
        sku = item.get("nmId") or item.get("nmID") or item.get("sku")
        stock = int(item.get("quantity", 0))
        updated = item.get("lastChangeDate")

        if not sku:
            continue

        stocks[sku] += stock

        # дефицит (проверяем по каждой записи — один склад может быть пустым)
        if stock < 5 and sku not in low_stock:
            low_stock.append(sku)

        # залежавшийся товар
        if updated and sku not in seen_stale:
            try:
                last = datetime.fromisoformat(updated.replace("Z", "+00:00").replace("Z", ""))
                if datetime.utcnow() - last.replace(tzinfo=None) > timedelta(days=30):
                    stale_stock.append(sku)
                    seen_stale.add(sku)
            except Exception:
                pass

    return {
        "total_skus": len(stocks),
        "stocks": dict(stocks),     # ← словарь SKU → кол-во (нужен для forecast)
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
# PROCESS
# -----------------------------

def process(config):
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