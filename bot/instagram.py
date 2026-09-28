"""Публикация фото-поста через Instagram Graph API (Content Publishing)."""
from __future__ import annotations

import os
import time

import requests


def _base() -> str:
    # Токены «входа через Instagram» начинаются с IGAA и работают на graph.instagram.com,
    # токены «входа через Facebook» работают на graph.facebook.com. Эндпоинты публикации одинаковые.
    host = os.getenv("GRAPH_HOST") or (
        "graph.instagram.com" if os.getenv("IG_ACCESS_TOKEN", "").startswith("IG") else "graph.facebook.com")
    return f"https://{host}/{os.getenv('GRAPH_API_VERSION', 'v21.0')}"


def _check(resp: requests.Response) -> dict:
    data = resp.json()
    if resp.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram API: {data.get('error', data)}")
    return data


def _own_user_id(token: str) -> str:
    """ID аккаунта, которому принадлежит токен, чтобы не вписывать его вручную."""
    data = _check(requests.get(f"{_base()}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30))
    return str(data.get("user_id") or data["id"])


def publish_photo(image_url: str, caption: str) -> str:
    """Два шага: создать контейнер с картинкой, дождаться обработки, опубликовать. Возвращает id поста."""
    token = os.environ["IG_ACCESS_TOKEN"]
    # защита от публикации не в тот аккаунт: токен должен принадлежать каналу из CHANNEL_HANDLE
    me = _check(requests.get(f"{_base()}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30))
    expected = os.getenv("CHANNEL_HANDLE", "").lstrip("@").lower()
    if expected and me.get("username", "").lower() != expected:
        raise RuntimeError(f"Токен от аккаунта @{me.get('username')}, а канал @{expected}. Публикация отменена.")
    ig_user = os.getenv("IG_USER_ID") or str(me.get("user_id") or me["id"])

    container = _check(requests.post(
        f"{_base()}/{ig_user}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
        timeout=60,
    ))["id"]

    for _ in range(30):
        status = _check(requests.get(
            f"{_base()}/{container}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Контейнер {container} не обработан: {status}")
        time.sleep(4)

    return _check(requests.post(
        f"{_base()}/{ig_user}/media_publish",
        data={"creation_id": container, "access_token": token},
        timeout=60,
    ))["id"]


def refresh_instagram_token(token: str) -> str:
    """Продлевает токен «входа через Instagram» ещё на 60 дней (токен должен быть старше суток)."""
    return _check(requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=30,
    ))["access_token"]


def refresh_long_lived_token(app_id: str, app_secret: str, token: str) -> str:
    """Продлевает долгоживущий токен (живёт 60 дней). Запускайте раз в месяц."""
    return _check(requests.get(
        f"{_base()}/oauth/access_token",
        params={"grant_type": "fb_exchange_token", "client_id": app_id,
                "client_secret": app_secret, "fb_exchange_token": token},
        timeout=30,
    ))["access_token"]
