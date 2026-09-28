"""Сбор кандидатов для поста: свежие новости из RSS и факты из русской Википедии."""
from __future__ import annotations

import calendar
import html
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

UA = {"User-Agent": "news-facts-bot/1.0 (instagram channel automation)"}
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Item:
    kind: str          # "news" | "fact"
    title: str
    summary: str
    url: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", text or ""))).strip()


def fetch_news(config_path: Path) -> list[Item]:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    max_age = cfg.get("max_age_hours", 36) * 3600
    per_feed = cfg.get("max_items_per_feed", 15)
    now = time.time()
    items: list[Item] = []
    for feed in cfg.get("rss", []):
        try:
            resp = requests.get(feed["url"], headers=UA, timeout=20)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as e:  # один упавший источник не должен ронять весь запуск
            print(f"[sources] {feed['name']}: {e}")
            continue
        for entry in parsed.entries[:per_feed]:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published and now - calendar.timegm(published) > max_age:
                continue
            title = _clean(entry.get("title", ""))
            if not title:
                continue
            items.append(Item(
                kind="news",
                title=title,
                summary=_clean(entry.get("summary", ""))[:800],
                url=entry.get("link", ""),
                source=feed["name"],
            ))
    return items


def fetch_facts(count: int = 12) -> list[Item]:
    """События «в этот день» из Википедии. Это проверенные факты с источником, а не выдумка модели."""
    today = datetime.now(timezone.utc)
    url = f"https://ru.wikipedia.org/api/rest_v1/feed/onthisday/events/{today:%m}/{today:%d}"
    try:
        resp = requests.get(url, headers=UA, timeout=20)
        resp.raise_for_status()
        events = resp.json().get("events", [])
    except Exception as e:
        print(f"[sources] Википедия: {e}")
        return []
    items: list[Item] = []
    for ev in events[:count]:
        pages = ev.get("pages") or [{}]
        page = pages[0]
        extract = _clean(page.get("extract", ""))
        items.append(Item(
            kind="fact",
            title=f"{ev.get('year')} год: {_clean(ev.get('text', ''))}",
            summary=extract[:800],
            url=page.get("content_urls", {}).get("desktop", {}).get("page", ""),
            source="Википедия",
        ))
    return items
