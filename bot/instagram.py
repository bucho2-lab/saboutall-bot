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


def _account(token: str) -> str:
    """ID аккаунта токена; заодно защита от публикации не в тот аккаунт (сверка с CHANNEL_HANDLE)."""
    me = _check(requests.get(f"{_base()}/me", params={"fields": "user_id,username", "access_token": token}, timeout=30))
    expected = os.getenv("CHANNEL_HANDLE", "").lstrip("@").lower()
    if expected and me.get("username", "").lower() != expected:
        raise RuntimeError(f"Токен от аккаунта @{me.get('username')}, а канал @{expected}. Публикация отменена.")
    return os.getenv("IG_USER_ID") or str(me.get("user_id") or me["id"])


def _publish(fields: dict, tries: int, pause: int) -> str:
    """Два шага: создать контейнер, дождаться обработки, опубликовать. Возвращает id поста."""
    token = os.environ["IG_ACCESS_TOKEN"]
    ig_user = _account(token)
    container = _check(requests.post(
        f"{_base()}/{ig_user}/media", data={**fields, "access_token": token}, timeout=60))["id"]

    for _ in range(tries):
        status = _check(requests.get(
            f"{_base()}/{container}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        ))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Контейнер {container} не обработан: {status}")
        time.sleep(pause)
    else:
        raise RuntimeError(f"Контейнер {container} не успел обработаться")

    return _check(requests.post(
        f"{_base()}/{ig_user}/media_publish",
        data={"creation_id": container, "access_token": token},
        timeout=60,
    ))["id"]


def publish_photo(image_url: str, caption: str) -> str:
    return _publish({"image_url": image_url, "caption": caption}, tries=30, pause=4)


def publish_reel(video_url: str, caption: str) -> str:
    """Ролик Reels; share_to_feed: показывать и в ленте профиля. Видео Instagram обрабатывает дольше."""
    return _publish({"media_type": "REELS", "video_url": video_url, "caption": caption,
                     "share_to_feed": "true"}, tries=60, pause=10)


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
