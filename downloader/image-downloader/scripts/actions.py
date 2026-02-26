import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

class ImageDownloaderSkill:
    name = "image-downloader"
    version = "1.0.0"
    description = "Download images and galleries from the internet"

    def __init__(self):
        self.gallery_dir = Path.home() / ".openclaw/workspace/skills/downloader/image-downloader/outputs"
        self.gallery_dir.mkdir(parents=True, exist_ok=True)

    # ---------- utils ----------

    def _valid_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    def _success(self, data: Any) -> Dict:
        return {"success": True, "data": data}

    def _error(self, message: str) -> Dict:
        return {"success": False, "error": message}

    # ---------- main download ----------

    def download(self, url: str, limit: Optional[int] = None) -> Dict:
        if not self._valid_url(url):
            return self._error("Invalid URL")

        if shutil.which("gallery-dl") is None:
            return self._error("gallery-dl not installed. Run: pip install gallery-dl")

        cmd = ["gallery-dl", "-d", str(self.gallery_dir)]

        if limit:
            cmd.extend(["--range", f"1-{limit}"])

        cmd.append(url)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600
            )

            if result.returncode == 0:
                return self._success({
                    "message": "Download completed",
                    "output_dir": str(self.gallery_dir)
                })

            return self._error(result.stderr)

        except subprocess.TimeoutExpired:
            return self._error("Download timed out")
        except Exception as e:
            return self._error(str(e))