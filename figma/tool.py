import requests
import time

BASE_URL = "http://127.0.0.1:4000"

def run(action: str, user_id: str, **kwargs):
    """
    action: "get_file" | "command" | "get_nodes" | "get_response"
    """
    try:
        # Получить файл через REST API
        if action == "get_file":
            file_key = kwargs.get("file_key")
            r = requests.get(f"{BASE_URL}/figma/file/{file_key}", params={"user_id": user_id}, timeout=20)
            r.raise_for_status()
            return r.json()

        # Отправить команду в плагин
        if action == "command":
            command = kwargs.get("command")
            r = requests.post(f"{BASE_URL}/figma/command",
                json={"user_id": user_id, "command": command}, timeout=10)
            r.raise_for_status()
            return r.json()

        # Получить узлы страницы через плагин
        # ИСПРАВЛЕНО: используем requestId + wait=1 для надёжного получения ответа
        if action == "get_nodes":
            name_filter = kwargs.get("name_filter", None)
            cmd = {"type": "get-page-nodes"}
            if name_filter:
                cmd["nameFilter"] = name_filter

            # Отправляем команду и получаем requestId
            r = requests.post(f"{BASE_URL}/figma/command",
                json={"user_id": user_id, "command": cmd}, timeout=10)
            r.raise_for_status()
            result = r.json()

            if not result.get("ok"):
                return result

            request_id = result.get("requestId")

            # Получаем ответ с polling (wait=1 ждёт до 8 сек на сервере)
            params = {"wait": "1"}
            if request_id:
                params["rid"] = request_id

            resp = requests.get(
                f"{BASE_URL}/figma/response/{user_id}",
                params=params,
                timeout=12  # чуть больше чем серверный timeout 8сек
            )
            resp.raise_for_status()
            return resp.json()

        # Получить последний ответ вручную (для отладки)
        if action == "get_response":
            request_id = kwargs.get("request_id", None)
            params = {}
            if request_id:
                params["rid"] = request_id
            r = requests.get(f"{BASE_URL}/figma/response/{user_id}", params=params, timeout=10)
            r.raise_for_status()
            return r.json()

    except Exception as e:
        return {"error": True, "message": str(e)}