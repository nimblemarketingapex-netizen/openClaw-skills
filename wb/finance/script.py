# =============================================================
# wb/finance/script.py
#
# Что делает этот модуль:
#   ✔ Получает детальный отчёт о реализации WB за период
#   ✔ Считает реальную выручку, маржу, вычеты
#   ✔ Разбивает вычеты по категориям (комиссия, логистика, хранение, штрафы)
#   ✔ Выявляет убыточные и низкомаржинальные SKU
#   ✔ Формирует ежедневный дайджест и отправляет в Telegram
# =============================================================

import requests
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


# =============================================================
# КОНФИГ
# =============================================================

# Типы операций из поля supplier_oper_name
# Продажи — увеличивают выручку
SALE_OPS = {
    "Продажа",
    "Корректная продажа",
}

# Возвраты — уменьшают выручку
RETURN_OPS = {
    "Возврат",
    "Коррекция возврата",
    "Возврат брака",
    "Возврат товара продавцом",
}

# Штрафы — отдельная статья расходов
PENALTY_OPS = {
    "Штраф",
    "Штрафы",
}

# Порог маржи: ниже 0% = убыточный SKU
DEFAULT_LOSS_THRESHOLD = 0
# Ниже 20% = низкомаржинальный SKU
DEFAULT_LOW_MARGIN_THRESHOLD = 20


# =============================================================
# HELPERS: КОНФИГ
# =============================================================

def get_wb_token(config: dict) -> str | None:
    try:
        return config["wb"]["WB_API_TOKEN"]["apiKey"]
    except (KeyError, TypeError):
        return None


def get_tg_config(config: dict) -> tuple[str | None, str | None]:
    try:
        return (
            config["telegram"]["botToken"],
            config["telegram"]["chatId"],
        )
    except (KeyError, TypeError):
        return None, None


def get_finance_config(config: dict) -> dict:
    return config.get("finance", {})


# =============================================================
# API: ОТЧЁТ О РЕАЛИЗАЦИИ
# =============================================================

def fetch_report(token: str, date_from: str, date_to: str) -> list[dict]:
    """
    Получает детальный отчёт о реализации за период.

    Пагинация через rrdid (ID последней строки).
    Если строк = 0 — все данные получены.

    Документация WB:
    GET /api/v5/supplier/reportDetailByPeriod
    """
    url = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
    headers = {"Authorization": token}

    all_rows: list[dict] = []
    rrdid = 0  # начинаем с 0

    while True:
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "rrdid": rrdid,
            "limit": 100_000,
        }

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.RequestException as e:
            logger.error(f"[finance] Ошибка запроса отчёта: {e}")
            break

        if r.status_code == 401:
            logger.error("[finance] Неверный WB токен (401)")
            break

        if r.status_code != 200:
            logger.warning(f"[finance] Код ответа: {r.status_code} | {r.text[:200]}")
            break

        try:
            rows = r.json()
        except Exception as e:
            logger.error(f"[finance] Ошибка парсинга JSON: {e}")
            break

        if not rows:
            # Пустой ответ — все данные получены
            break

        all_rows.extend(rows)

        # Берём rrdid последней строки для следующей страницы
        last_rrdid = rows[-1].get("rrd_id") or rows[-1].get("rrdid")
        if not last_rrdid or last_rrdid == rrdid:
            # Защита от бесконечного цикла
            break

        rrdid = last_rrdid

        # Если строк меньше лимита — это последняя страница
        if len(rows) < 100_000:
            break

    logger.info(f"[finance] Получено строк отчёта: {len(all_rows)}")
    return all_rows


# =============================================================
# АНАЛИЗ ОТЧЁТА
# =============================================================

def analyze_report(rows: list[dict], finance_cfg: dict) -> dict:
    """
    Разбирает строки отчёта о реализации.

    Возвращает:
    - общую выручку, вычеты, чистую выручку, маржу
    - разбивку вычетов по категориям
    - метрики по каждому SKU
    - список убыточных и низкомаржинальных SKU
    """

    loss_threshold = finance_cfg.get("loss_margin_threshold", DEFAULT_LOSS_THRESHOLD)
    low_margin_threshold = finance_cfg.get("low_margin_threshold", DEFAULT_LOW_MARGIN_THRESHOLD)

    # Агрегаты по всему отчёту
    gross_revenue = 0.0      # выручка до вычетов (sum retail_price для продаж)
    net_revenue = 0.0        # чистая выручка (sum ppvz_for_pay)
    total_commission = 0.0
    total_logistics = 0.0
    total_storage = 0.0
    total_penalties = 0.0
    total_advertising = 0.0
    orders_count = 0
    returns_count = 0

    # По SKU: nm_id -> накопители
    sku_data: dict[int, dict] = defaultdict(lambda: {
        "gross": 0.0,
        "net": 0.0,
        "logistics": 0.0,
        "commission": 0.0,
        "storage": 0.0,
        "orders": 0,
        "returns": 0,
    })

    for row in rows:
        op = (row.get("supplier_oper_name") or "").strip()
        nm_id = row.get("nm_id") or 0

        retail_price = float(row.get("retail_price") or 0)
        ppvz_for_pay = float(row.get("ppvz_for_pay") or 0)
        delivery_rub = float(row.get("delivery_rub") or 0)
        storage_fee = float(row.get("storage_fee") or 0)
        penalty = float(row.get("penalty") or 0)
        paid_acceptance = float(row.get("paid_acceptance") or 0)  # реклама/платная приёмка

        # Комиссия = разница между ценой продажи и суммой к выплате (до логистики)
        commission = retail_price - ppvz_for_pay - delivery_rub if retail_price > 0 else 0.0

        if op in SALE_OPS:
            gross_revenue += retail_price
            net_revenue += ppvz_for_pay
            total_commission += max(commission, 0)
            total_logistics += delivery_rub
            orders_count += 1

            if nm_id:
                sku_data[nm_id]["gross"] += retail_price
                sku_data[nm_id]["net"] += ppvz_for_pay
                sku_data[nm_id]["logistics"] += delivery_rub
                sku_data[nm_id]["commission"] += max(commission, 0)
                sku_data[nm_id]["orders"] += 1

        elif op in RETURN_OPS:
            # Возвраты уменьшают выручку
            gross_revenue -= retail_price
            net_revenue -= ppvz_for_pay
            returns_count += 1

            if nm_id:
                sku_data[nm_id]["gross"] -= retail_price
                sku_data[nm_id]["net"] -= ppvz_for_pay
                sku_data[nm_id]["returns"] += 1

        elif op in PENALTY_OPS:
            total_penalties += abs(penalty)

        # Хранение и платная приёмка — независимо от типа операции
        total_storage += storage_fee
        total_advertising += paid_acceptance

    # Итого вычетов
    total_deductions = total_commission + total_logistics + total_storage + total_penalties + total_advertising

    # Маржа по всему отчёту
    margin_pct = round((net_revenue / gross_revenue * 100), 1) if gross_revenue > 0 else 0.0

    # --- Анализ по SKU ---
    by_sku = {}
    loss_skus = []
    low_margin_skus = []

    for nm_id, d in sku_data.items():
        sku_margin = round((d["net"] / d["gross"] * 100), 1) if d["gross"] > 0 else 0.0
        is_loss = sku_margin <= loss_threshold
        is_low = loss_threshold < sku_margin <= low_margin_threshold

        by_sku[nm_id] = {
            "gross": round(d["gross"], 2),
            "net": round(d["net"], 2),
            "logistics": round(d["logistics"], 2),
            "commission": round(d["commission"], 2),
            "margin_pct": sku_margin,
            "orders": d["orders"],
            "returns": d["returns"],
            "is_loss": is_loss,
            "is_low_margin": is_low,
        }

        if is_loss:
            loss_skus.append(nm_id)
        elif is_low:
            low_margin_skus.append(nm_id)

    # Топ-5 SKU по чистой выручке
    top_skus = sorted(by_sku.items(), key=lambda x: x[1]["net"], reverse=True)[:5]

    return {
        "gross_revenue": round(gross_revenue, 2),
        "net_revenue": round(net_revenue, 2),
        "total_deductions": round(total_deductions, 2),
        "margin_pct": margin_pct,
        "to_pay": round(net_revenue, 2),
        "deductions_breakdown": {
            "commission": round(total_commission, 2),
            "logistics": round(total_logistics, 2),
            "storage": round(total_storage, 2),
            "penalties": round(total_penalties, 2),
            "advertising": round(total_advertising, 2),
        },
        "orders": orders_count,
        "returns": returns_count,
        "by_sku": by_sku,
        "top_skus": top_skus,
        "loss_skus": loss_skus,
        "low_margin_skus": low_margin_skus,
        "total_skus": len(by_sku),
    }


# =============================================================
# TELEGRAM: ФОРМАТИРОВАНИЕ
# =============================================================

def format_digest(report: dict, period_label: str) -> str:
    """
    Форматирует краткий дайджест для Telegram.
    Намеренно лаконичный — только флаги и ключевые числа.
    """

    def fmt(n: float) -> str:
        """Форматирует число с разделителями тысяч."""
        return f"{n:,.0f}".replace(",", " ")

    lines = [
        f"📦 *Дайджест за {period_label}*",
        "",
        f"💰 Выручка:       `{fmt(report['gross_revenue'])} ₽`",
        f"📉 Вычеты WB:     `{fmt(report['total_deductions'])} ₽`",
        f"✅ Чистыми:       `{fmt(report['net_revenue'])} ₽`",
        f"📊 Маржа:         `{report['margin_pct']}%`",
        "",
        f"🛒 Заказов:       `{report['orders']}`",
        f"↩️  Возвратов:     `{report['returns']}`",
    ]

    # Разбивка вычетов
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
    if d["advertising"] > 0:
        lines.append(f"  • Реклама:     `{fmt(d['advertising'])} ₽`")

    # Топ-товар
    if report["top_skus"]:
        top_nm, top_data = report["top_skus"][0]
        lines += [
            "",
            f"🏆 Топ-товар:    `{top_nm}` → `{fmt(top_data['net'])} ₽`",
        ]

    # Флаги проблем
    flags = []

    if report["loss_skus"]:
        skus_str = ", ".join(str(s) for s in report["loss_skus"][:5])
        suffix = f" и ещё {len(report['loss_skus']) - 5}" if len(report["loss_skus"]) > 5 else ""
        flags.append(f"🔴 Убыточных SKU: {len(report['loss_skus'])} → {skus_str}{suffix}")

    if report["low_margin_skus"]:
        flags.append(f"🟡 Низкая маржа: {len(report['low_margin_skus'])} SKU")

    if report["returns"] > 0 and report["orders"] > 0:
        return_pct = round(report["returns"] / report["orders"] * 100, 1)
        if return_pct > 15:
            flags.append(f"⚠️ Высокий % возвратов: {return_pct}%")

    if flags:
        lines += ["", "─────────────────"]
        lines.extend(flags)

    return "\n".join(lines)


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """
    Отправляет сообщение в Telegram с Markdown форматированием.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            logger.warning(f"[finance] Telegram ответил {r.status_code}: {r.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        logger.error(f"[finance] Ошибка отправки в Telegram: {e}")
        return False


# =============================================================
# ПУБЛИЧНЫЙ ИНТЕРФЕЙС
# =============================================================

def process(config: dict, date_from: str, date_to: str) -> dict:
    """
    Основная точка входа.
    Получает и анализирует отчёт о реализации за указанный период.

    Параметры:
        config    — конфиг со всеми токенами
        date_from — начало периода "YYYY-MM-DD"
        date_to   — конец периода  "YYYY-MM-DD"

    Возвращает словарь с полным финансовым анализом.
    """
    if not config.get("wb", {}).get("enabled"):
        logger.info("[finance] WB модуль отключён в конфиге")
        return {}

    token = get_wb_token(config)
    if not token:
        logger.error("[finance] WB токен не найден")
        return {}

    rows = fetch_report(token, date_from, date_to)
    if not rows:
        logger.warning("[finance] Отчёт пуст или не получен")
        return {}

    finance_cfg = get_finance_config(config)
    report = analyze_report(rows, finance_cfg)
    report["period"] = {"from": date_from, "to": date_to}

    return report


def send_daily_digest(config: dict) -> bool:
    """
    Формирует и отправляет ежедневный дайджест в Telegram.
    Данные берутся за вчерашний день (UTC).

    Вызывать через cron каждое утро, например в 09:00.
    """
    if not config.get("wb", {}).get("enabled"):
        return False

    bot_token, chat_id = get_tg_config(config)
    if not bot_token or not chat_id:
        logger.error("[finance] Telegram конфиг не найден")
        return False

    # Вчерашний день UTC
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    period_label = yesterday.strftime("%d.%m.%Y")

    report = process(config, date_from=date_str, date_to=date_str)

    if not report:
        # Нет данных — отправляем уведомление
        send_telegram(bot_token, chat_id,
            f"📦 Дайджест за {period_label}\n\n"
            "ℹ️ Данных за этот день нет.\n"
            "Возможно, отчёт ещё не сформирован (WB закрывает данные раз в неделю)."
        )
        return False

    text = format_digest(report, period_label)
    return send_telegram(bot_token, chat_id, text)


def send_weekly_digest(config: dict) -> bool:
    """
    Формирует и отправляет еженедельный дайджест в Telegram.
    Берёт данные за прошлую неделю (пн–вс) — именно так WB формирует отчёты.

    Вызывать через cron каждый понедельник утром.
    """
    if not config.get("wb", {}).get("enabled"):
        return False

    bot_token, chat_id = get_tg_config(config)
    if not bot_token or not chat_id:
        logger.error("[finance] Telegram конфиг не найден")
        return False

    today = datetime.now(timezone.utc).date()

    # Прошлая неделя: прошлый понедельник → прошлое воскресенье
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    date_from = last_monday.strftime("%Y-%m-%d")
    date_to = last_sunday.strftime("%Y-%m-%d")
    period_label = f"{last_monday.strftime('%d.%m')} – {last_sunday.strftime('%d.%m.%Y')}"

    report = process(config, date_from=date_from, date_to=date_to)

    if not report:
        send_telegram(bot_token, chat_id,
            f"📦 Еженедельный отчёт {period_label}\n\n"
            "ℹ️ Данных за этот период нет или отчёт ещё не готов."
        )
        return False

    # Для недельного дайджеста добавляем больше деталей
    text = format_digest(report, f"неделю {period_label}")

    # Добавляем топ-5 SKU
    if report.get("top_skus"):
        lines = ["\n📈 *Топ-5 товаров за неделю:*"]
        for i, (nm_id, d) in enumerate(report["top_skus"], 1):
            lines.append(
                f"  {i}. `{nm_id}` — `{d['net']:,.0f} ₽` "
                f"({d['margin_pct']}% маржа, {d['orders']} заказов)"
            )
        text += "\n" + "\n".join(lines)

    return send_telegram(bot_token, chat_id, text)