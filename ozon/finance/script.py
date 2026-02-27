# =============================================================
# ozon/finance/script.py
#
# Что делает:
#   ✔ Отчёт о реализации (/v2/finance/realization)
#   ✔ Транзакции с разбивкой (/v3/finance/transaction/list)
#   ✔ Итоги транзакций (/v3/finance/transaction/totals)
#   ✔ Баланс (/v1/finance/balance)
#   ✔ Расчёт маржи, вычетов, убыточных SKU
#   ✔ Ежедневный и еженедельный дайджест в Telegram
# =============================================================

import requests
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://api-seller.ozon.ru"

# Типы операций в транзакциях Ozon
SALE_OPS = {"MarketplaceMarketplaceSellers"}
RETURN_OPS = {"MarketplaceReturnAfterDeliveryWriteOff", "MarketplaceSaleReturnsWriteOff"}
COMMISSION_OPS = {"MarketplaceSellerCompanyName"}

DEFAULT_LOSS_THRESHOLD = 0
DEFAULT_LOW_MARGIN_THRESHOLD = 20


# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------

def get_headers(config: dict) -> dict:
    return {
        "Client-Id": str(config["ozon"]["client_id"]),
        "Api-Key": config["ozon"]["api_key"],
        "Content-Type": "application/json",
    }


def get_tg_config(config: dict) -> tuple:
    try:
        return config["telegram"]["botToken"], config["telegram"]["chatId"]
    except (KeyError, TypeError):
        return None, None


def get_finance_cfg(config: dict) -> dict:
    return config.get("finance", {})


# -------------------------------------------------------------
# БАЛАНС: /v1/finance/balance
# -------------------------------------------------------------

def get_balance(headers: dict) -> dict:
    """
    Текущий баланс продавца.

    Документация: POST /v1/finance/balance
    """
    url = f"{BASE_URL}/v1/finance/balance"
    try:
        r = requests.post(url, headers=headers, json={}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"[ozon:balance] Ошибка: {e}")
    return {}


# -------------------------------------------------------------
# ОТЧЁТ О РЕАЛИЗАЦИИ: /v2/finance/realization
# -------------------------------------------------------------

def get_realization_report(headers: dict, month: int, year: int) -> dict:
    """
    Отчёт о реализации за конкретный месяц.
    Ozon формирует отчёты по месяцам, не по произвольным датам.

    Документация: POST /v2/finance/realization
    """
    url = f"{BASE_URL}/v2/finance/realization"
    payload = {
        "month": month,
        "year": year,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"[ozon:realization] Код: {r.status_code} | {r.text[:200]}")
    except Exception as e:
        logger.error(f"[ozon:realization] Ошибка: {e}")

    return {}


# -------------------------------------------------------------
# ТРАНЗАКЦИИ: /v3/finance/transaction/list
# -------------------------------------------------------------

def get_transactions(headers: dict, date_from: str, date_to: str) -> list:
    """
    Список транзакций за период с полной разбивкой.
    Это более детальный источник данных чем отчёт о реализации —
    обновляется в реальном времени.

    Документация: POST /v3/finance/transaction/list
    """
    url = f"{BASE_URL}/v3/finance/transaction/list"
    all_rows = []
    page = 1

    while True:
        payload = {
            "filter": {
                "date": {
                    "from": f"{date_from}T00:00:00.000Z",
                    "to": f"{date_to}T23:59:59.000Z",
                },
                "operation_type": [],  # все типы операций
                "posting_number": "",
                "transaction_type": "all",
            },
            "page": page,
            "page_size": 1000,
        }

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.RequestException as e:
            logger.error(f"[ozon:transactions] Ошибка запроса: {e}")
            break

        if r.status_code != 200:
            logger.warning(f"[ozon:transactions] Код: {r.status_code} | {r.text[:200]}")
            break

        data = r.json()
        rows = data.get("result", {}).get("operations", [])
        if not rows:
            break

        all_rows.extend(rows)

        page_count = data.get("result", {}).get("page_count", 1)
        if page >= page_count:
            break
        page += 1

    logger.info(f"[ozon:transactions] Получено операций: {len(all_rows)}")
    return all_rows


def get_transaction_totals(headers: dict, date_from: str, date_to: str) -> dict:
    """
    Итоговые суммы транзакций за период (без разбивки по операциям).

    Документация: POST /v3/finance/transaction/totals
    """
    url = f"{BASE_URL}/v3/finance/transaction/totals"
    payload = {
        "filter": {
            "date": {
                "from": f"{date_from}T00:00:00.000Z",
                "to": f"{date_to}T23:59:59.000Z",
            },
            "posting_number": "",
            "transaction_type": "all",
        },
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get("result", {})
    except Exception as e:
        logger.error(f"[ozon:totals] Ошибка: {e}")

    return {}


# -------------------------------------------------------------
# АНАЛИЗ ТРАНЗАКЦИЙ
# -------------------------------------------------------------

def analyze_transactions(operations: list, finance_cfg: dict) -> dict:
    """
    Разбирает список операций на составляющие:
    - выручка, вычеты, маржа
    - разбивка по типам вычетов
    - метрики по SKU
    """
    loss_threshold = finance_cfg.get("loss_margin_threshold", DEFAULT_LOSS_THRESHOLD)
    low_margin_threshold = finance_cfg.get("low_margin_threshold", DEFAULT_LOW_MARGIN_THRESHOLD)

    gross_revenue = 0.0
    commission_total = 0.0
    logistics_total = 0.0
    storage_total = 0.0
    penalty_total = 0.0
    other_total = 0.0
    orders_count = 0
    returns_count = 0

    by_sku: dict = defaultdict(lambda: {"gross": 0.0, "commission": 0.0, "orders": 0, "returns": 0})

    for op in operations:
        op_type = op.get("operation_type", "")
        amount = float(op.get("amount", 0))
        items = op.get("items", [])

        # Классифицируем по типу операции
        if "Delivery" in op_type or "Sale" in op_type:
            if amount > 0:
                gross_revenue += amount
                orders_count += 1
                for item in items:
                    sku = str(item.get("sku", ""))
                    if sku:
                        by_sku[sku]["gross"] += amount
                        by_sku[sku]["orders"] += 1

        elif "Return" in op_type:
            returns_count += 1
            gross_revenue -= abs(amount)
            for item in items:
                sku = str(item.get("sku", ""))
                if sku:
                    by_sku[sku]["returns"] += 1

        elif "Commission" in op_type or "MarketplaceCommission" in op_type:
            commission_total += abs(amount)
            for item in items:
                sku = str(item.get("sku", ""))
                if sku:
                    by_sku[sku]["commission"] += abs(amount)

        elif "Logistic" in op_type or "Delivery" in op_type:
            logistics_total += abs(amount)

        elif "Storage" in op_type:
            storage_total += abs(amount)

        elif "Penalty" in op_type or "Fine" in op_type:
            penalty_total += abs(amount)

        else:
            other_total += abs(amount)

    total_deductions = commission_total + logistics_total + storage_total + penalty_total
    net_revenue = gross_revenue - total_deductions
    margin_pct = round(net_revenue / gross_revenue * 100, 1) if gross_revenue > 0 else 0.0

    # Анализ по SKU
    processed_skus = {}
    loss_skus = []
    low_margin_skus = []

    for sku, d in by_sku.items():
        sku_net = d["gross"] - d["commission"]
        sku_margin = round(sku_net / d["gross"] * 100, 1) if d["gross"] > 0 else 0.0
        is_loss = sku_margin <= loss_threshold
        is_low = loss_threshold < sku_margin <= low_margin_threshold

        processed_skus[sku] = {
            "gross": round(d["gross"], 2),
            "net": round(sku_net, 2),
            "margin_pct": sku_margin,
            "orders": d["orders"],
            "returns": d["returns"],
            "is_loss": is_loss,
            "is_low_margin": is_low,
        }

        if is_loss:
            loss_skus.append(sku)
        elif is_low:
            low_margin_skus.append(sku)

    top_skus = sorted(processed_skus.items(), key=lambda x: x[1]["gross"], reverse=True)[:5]

    return {
        "gross_revenue": round(gross_revenue, 2),
        "net_revenue": round(net_revenue, 2),
        "total_deductions": round(total_deductions, 2),
        "margin_pct": margin_pct,
        "to_pay": round(net_revenue, 2),
        "deductions_breakdown": {
            "commission": round(commission_total, 2),
            "logistics": round(logistics_total, 2),
            "storage": round(storage_total, 2),
            "penalties": round(penalty_total, 2),
            "other": round(other_total, 2),
        },
        "orders": orders_count,
        "returns": returns_count,
        "by_sku": processed_skus,
        "top_skus": top_skus,
        "loss_skus": loss_skus,
        "low_margin_skus": low_margin_skus,
    }


# -------------------------------------------------------------
# ФОРМАТИРОВАНИЕ ДАЙДЖЕСТА
# -------------------------------------------------------------

def format_digest(report: dict, balance: dict, period_label: str) -> str:
    def fmt(n: float) -> str:
        return f"{n:,.0f}".replace(",", " ")

    # Баланс
    balance_amount = float(
        balance.get("balance", {}).get("amount", 0) or
        balance.get("result", {}).get("balance", 0) or 0
    )

    lines = [
        f"📦 *Дайджест Ozon за {period_label}*",
        "",
        f"💳 Баланс:        `{fmt(balance_amount)} ₽`",
        "",
        f"💰 Выручка:       `{fmt(report['gross_revenue'])} ₽`",
        f"📉 Вычеты:        `{fmt(report['total_deductions'])} ₽`",
        f"✅ Чистыми:       `{fmt(report['net_revenue'])} ₽`",
        f"📊 Маржа:         `{report['margin_pct']}%`",
        "",
        f"🛒 Заказов:       `{report['orders']}`",
        f"↩️  Возвратов:     `{report['returns']}`",
    ]

    d = report["deductions_breakdown"]
    lines += [
        "",
        "📋 *Вычеты подробно:*",
        f"  • Комиссия:    `{fmt(d['commission'])} ₽`",
        f"  • Логистика:   `{fmt(d['logistics'])} ₽`",
        f"  • Хранение:    `{fmt(d['storage'])} ₽`",
    ]
    if d["penalties"] > 0:
        lines.append(f"  • ⚠️ Штрафы:    `{fmt(d['penalties'])} ₽`")

    if report.get("top_skus"):
        top_sku, top_data = report["top_skus"][0]
        lines += [
            "",
            f"🏆 Топ-товар:    `{top_sku}` → `{fmt(top_data['gross'])} ₽`",
        ]

    # Флаги проблем
    flags = []
    if report["loss_skus"]:
        skus_str = ", ".join(str(s) for s in report["loss_skus"][:5])
        suffix = f" и ещё {len(report['loss_skus']) - 5}" if len(report["loss_skus"]) > 5 else ""
        flags.append(f"🔴 Убыточных SKU: {len(report['loss_skus'])} → {skus_str}{suffix}")

    if report["low_margin_skus"]:
        flags.append(f"🟡 Низкая маржа: {len(report['low_margin_skus'])} SKU")

    if report["orders"] > 0 and report["returns"] > 0:
        return_pct = round(report["returns"] / report["orders"] * 100, 1)
        if return_pct > 15:
            flags.append(f"⚠️ Высокий % возвратов: {return_pct}%")

    if flags:
        lines += ["", "─────────────────"]
        lines.extend(flags)

    return "\n".join(lines)


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"[ozon:tg] Ошибка: {e}")
        return False


# -------------------------------------------------------------
# ПУБЛИЧНЫЙ ИНТЕРФЕЙС
# -------------------------------------------------------------

def process(config: dict, date_from: str, date_to: str) -> dict:
    """
    Основная точка входа: финансовый анализ за период.

    date_from, date_to — формат "YYYY-MM-DD"
    """
    if not config.get("ozon", {}).get("enabled"):
        return {}

    headers = get_headers(config)
    finance_cfg = get_finance_cfg(config)

    # Пробуем сначала детальные транзакции (реальное время)
    operations = get_transactions(headers, date_from, date_to)

    if not operations:
        logger.warning("[ozon:finance] Транзакции пусты")
        return {}

    report = analyze_transactions(operations, finance_cfg)
    report["period"] = {"from": date_from, "to": date_to}

    # Totals для сверки
    totals = get_transaction_totals(headers, date_from, date_to)
    if totals:
        report["totals_raw"] = totals

    return report


def send_daily_digest(config: dict) -> bool:
    """
    Ежедневный дайджест в Telegram.
    Берёт данные за вчера.
    """
    if not config.get("ozon", {}).get("enabled"):
        return False

    bot_token, chat_id = get_tg_config(config)
    if not bot_token or not chat_id:
        return False

    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    period_label = yesterday.strftime("%d.%m.%Y")

    headers = get_headers(config)
    balance = get_balance(headers)
    report = process(config, date_from=date_str, date_to=date_str)

    if not report:
        send_telegram(bot_token, chat_id,
            f"📦 Дайджест Ozon за {period_label}\n\n"
            "ℹ️ Данных за этот день нет или транзакции ещё не обработаны."
        )
        return False

    text = format_digest(report, balance, period_label)
    return send_telegram(bot_token, chat_id, text)


def send_weekly_digest(config: dict) -> bool:
    """
    Еженедельный дайджест в Telegram.
    Берёт прошлую неделю (пн–вс).
    """
    if not config.get("ozon", {}).get("enabled"):
        return False

    bot_token, chat_id = get_tg_config(config)
    if not bot_token or not chat_id:
        return False

    today = datetime.now(timezone.utc).date()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    date_from = last_monday.strftime("%Y-%m-%d")
    date_to = last_sunday.strftime("%Y-%m-%d")
    period_label = f"{last_monday.strftime('%d.%m')} – {last_sunday.strftime('%d.%m.%Y')}"

    headers = get_headers(config)
    balance = get_balance(headers)
    report = process(config, date_from=date_from, date_to=date_to)

    if not report:
        send_telegram(bot_token, chat_id,
            f"📦 Еженедельный отчёт Ozon {period_label}\n\n"
            "ℹ️ Данных за этот период нет."
        )
        return False

    text = format_digest(report, balance, f"неделю {period_label}")

    # Добавляем топ-5 SKU в недельный отчёт
    if report.get("top_skus"):
        lines = ["\n📈 *Топ-5 товаров за неделю:*"]
        for i, (sku, d) in enumerate(report["top_skus"], 1):
            lines.append(
                f"  {i}. `{sku}` — `{d['gross']:,.0f} ₽` "
                f"({d['margin_pct']}% маржа, {d['orders']} заказов)"
            )
        text += "\n" + "\n".join(lines)

    return send_telegram(bot_token, chat_id, text)