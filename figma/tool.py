import requests

BASE_URL = "http://127.0.0.1:4000"

def run(user_id: str, fileKey: str, mode: str = "summary"):
    """
    Получает данные Figma через локальный backend.
    """
    try:
        url = f"{BASE_URL}/figma/file/{fileKey}"
        response = requests.get(
            url,
            params={"user_id": user_id},
            timeout=20
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        return {
            "error": True,
            "message": str(e)
        }