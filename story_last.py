"""Сторис к последнему опубликованному посту (ручной запуск из Actions)."""
import json
import os
from pathlib import Path

import requests

from bot.hosting import published_url, upload
from bot.instagram import publish_story
from bot.render import render_story

ROOT = Path(__file__).resolve().parent
history = json.loads((ROOT / "data/history.json").read_text(encoding="utf-8"))
last = next(h for h in reversed(history) if h.get("published_id"))
handle = os.getenv("CHANNEL_HANDLE", "@bucho2")
url = published_url(last["image"])
print(f"Пост: {last['title']} ({last['image']})\n{url}")
if last["image"].endswith(".mp4"):
    story_id = publish_story(video_url=url)
else:
    img = ROOT / "output" / last["image"]
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(requests.get(url, timeout=60).content)
    category = last.get("category", "")
    story_id = publish_story(image_url=upload(render_story(category, img, handle, img.with_name(img.stem + "-story.jpg"))))
print(f"Сторис: {story_id}")
last["story_id"] = story_id
(ROOT / "data/history.json").write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
