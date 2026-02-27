from wb.finance.script import send_daily_digest, send_weekly_digest

config = {
    "wb": {"enabled": True, "WB_API_TOKEN": {"apiKey": "..."}},
    "telegram": {"botToken": "...", "chatId": "..."},
    "finance": {}
}

send_daily_digest(config)