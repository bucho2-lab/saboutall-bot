"""Диагностика: чей токен и где опубликованные посты. Токен в вывод не попадает."""
import json
import os
from pathlib import Path

import requests

from bot.instagram import _base

token = os.environ["IG_ACCESS_TOKEN"]
me = requests.get(f"{_base()}/me", params={"fields": "user_id,username,account_type,media_count", "access_token": token}, timeout=30).json()
print("Аккаунт токена:", me)
history = json.loads(Path("data/history.json").read_text(encoding="utf-8"))
for h in history:
    if h.get("published_id"):
        media = requests.get(f"{_base()}/{h['published_id']}",
                             params={"fields": "permalink,username,timestamp,media_type,media_url", "access_token": token},
                             timeout=30).json()
        print(h["title"], "->", media)
