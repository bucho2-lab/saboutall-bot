"""Выкладывает картинку по публичной ссылке: Instagram Graph API сам скачивает изображение по URL."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import requests


def upload(path: Path) -> str:
    host = os.getenv("IMAGE_HOST", "github").lower()
    if host == "github":
        return _github(path)
    if host == "imgbb":
        return _imgbb(path)
    raise ValueError(f"Неизвестный IMAGE_HOST={host}")


def _github(path: Path) -> str:
    """Кладёт файл в публичный репозиторий через Contents API и отдаёт raw-ссылку."""
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.getenv("GITHUB_BRANCH", "main")
    remote_path = f"published/{path.name}"
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/contents/{remote_path}",
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                 "Accept": "application/vnd.github+json"},
        json={"message": f"image {path.name}", "branch": branch,
              "content": base64.b64encode(path.read_bytes()).decode()},
        timeout=60,
    )
    resp.raise_for_status()
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{remote_path}"
    # raw.githubusercontent отдаёт новый файл не мгновенно
    for _ in range(12):
        if requests.head(url, timeout=20).status_code == 200:
            return url
        time.sleep(5)
    raise RuntimeError(f"Картинка не появилась по адресу {url}")


def _imgbb(path: Path) -> str:
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": os.environ["IMGBB_API_KEY"],
              "image": base64.b64encode(path.read_bytes()).decode()},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]
