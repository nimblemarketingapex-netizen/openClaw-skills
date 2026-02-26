from main import handle_message

def process_message(user_id: str, text: str) -> str:
    """
    Entry point for OpenClaw.
    Принимает:
    - user_id (ID пользователя)
    - text (сообщение)
    Возвращает строку — ответ бота.
    """
    return handle_message(user_id, text)
    