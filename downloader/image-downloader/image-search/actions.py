import requests
from duckduckgo_search import DDGS
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

class ImageSearchSkill:
    name = "image-search"
    version = "1.0.0"
    description = "Search and download images by query"

    def __init__(self):
        self.output_dir = Path.home() / ".openclaw/workspace/skills/downloader/image-downloader/image-search/outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _success(self, data: Any) -> Dict:
        return {"success": True, "data": data}

    def _error(self, message: str) -> Dict:
        return {"success": False, "error": message}

    def search(self, query: str, limit: int = 5, filter_ext: List[str] = None) -> Dict:
        """
        Поиск картинок по запросу.

        Args:
            query: текст запроса
            limit: сколько результатов
            filter_ext: фильтр по расширению (["jpg", "png"])
        """
        try:
            results = DDGS().images(query, max_results=limit)
            urls = [r["image"] for r in results if "image" in r]

            # фильтр по расширению
            if filter_ext:
                urls = [
                    u for u in urls
                    if any(u.lower().endswith(f".{ext}") for ext in filter_ext)
                ]

            return self._success({"query": query, "urls": urls})
        except Exception as e:
            return self._error(str(e))

    def search_and_download(self, query: str, limit: int = 5, filter_ext: List[str] = None) -> Dict:
        """
        Поиск + скачивание одной командой.
        """
        result = self.search(query, limit=limit, filter_ext=filter_ext)

        if not result["success"]:
            return result

        urls = result["data"]["urls"]
        return self.download(urls)

    def download(self, urls: List[str]) -> Dict:
        """
        Скачивание картинок по URL.
        """
        files = []

        for i, url in enumerate(urls):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    # только картинки
                    if not url.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue

                    path = self.output_dir / f"img_{i}.jpg"
                    path.write_bytes(resp.content)
                    files.append(str(path))
            except:
                continue

        return self._success({
            "downloaded": len(files),
            "files": files
        })

# singleton
skill = ImageSearchSkill()