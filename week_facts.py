"""События «в этот день» из русской Википедии на неделю вперёд, одним запуском. Для плана тем, ничего не публикует."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from bot.sources import UA

ROOT = Path(__file__).resolve().parent
start = datetime.now(timezone(timedelta(hours=3))).date() + timedelta(days=1)
out = {}
for i in range(7):
    day = start + timedelta(days=i)
    url = f"https://ru.wikipedia.org/api/rest_v1/feed/onthisday/events/{day:%m}/{day:%d}"
    try:
        resp = requests.get(url, headers=UA, timeout=30)
        resp.raise_for_status()
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"{day}: {e}")
        events = []
    out[day.isoformat()] = [
        {"year": ev.get("year"), "text": ev.get("text", ""),
         "pages": [p.get("titles", {}).get("normalized", p.get("title", "")) for p in ev.get("pages", [])[:3]]}
        for ev in events
    ]
    print(day, len(events))
path = ROOT / "data/week_facts.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("Готово:", path)
