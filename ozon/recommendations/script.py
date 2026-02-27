# =============================================================
# ozon/recommendations/script.py
#
# Генерирует рекомендации на основе аналитики и финансов.
# =============================================================

def process(analytics: dict, finance: dict) -> list:
    recs = []

    sales = analytics.get("sales", {})
    stock = analytics.get("stock", {})

    orders = sales.get("orders", 0)
    revenue = sales.get("revenue", 0)
    avg_check = sales.get("avg_check", 0)
    top_sku = sales.get("top_sku", [])

    # --- Продажи ---
    if orders == 0:
        recs.append("Продажи отсутствуют. Проверьте видимость карточек и наличие товаров.")
    elif revenue < 10000:
        recs.append("Низкая выручка. Рассмотрите участие в акциях Ozon или снижение цены.")

    if avg_check < 2000:
        recs.append("Низкий средний чек. Попробуйте кросс-продажи или комплекты.")
    elif avg_check > 5000:
        recs.append("Высокий средний чек — усиливайте продвижение премиальных позиций.")

    if top_sku:
        top_items = ", ".join([str(sku) for sku, _ in top_sku])
        recs.append(f"Топ-товары: {top_items}. Усильте их рекламу и следите за остатками.")

    # --- Склад ---
    zero_stock = stock.get("zero_stock", [])
    low_stock = stock.get("low_stock", [])

    if zero_stock:
        recs.append(f"Нулевые остатки у {len(zero_stock)} SKU: {', '.join(map(str, zero_stock[:5]))}. Срочно пополните.")
    if low_stock:
        recs.append(f"Критически мало товара у {len(low_stock)} SKU. Планируйте поставку.")

    # --- Финансы ---
    loss_skus = finance.get("loss_skus", [])
    low_margin = finance.get("low_margin_skus", [])
    margin_pct = finance.get("margin_pct", 0)
    penalties = finance.get("deductions_breakdown", {}).get("penalties", 0)

    if margin_pct < 20:
        recs.append(f"Общая маржа {margin_pct}% — ниже нормы. Проверьте цены и комиссии.")
    if loss_skus:
        recs.append(f"Убыточные SKU ({len(loss_skus)} шт.): {', '.join(map(str, loss_skus[:3]))}. Пересмотрите цены или выведите из ассортимента.")
    if low_margin:
        recs.append(f"Низкомаржинальных SKU: {len(low_margin)}. Оцените целесообразность.")
    if penalties > 0:
        recs.append(f"Штрафы Ozon: {penalties:,.0f} ₽. Проверьте причины в личном кабинете.")

    if not recs:
        recs.append("Всё в норме. Продолжайте мониторинг показателей.")

    return recs