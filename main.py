"""Один запуск = один пост.

    python main.py                 # подготовить пост (картинка + подпись в output/), без публикации
    python main.py --publish       # подготовить и опубликовать в Instagram
    python main.py --kind fact     # только факты; --kind news только новости; по умолчанию чередует
    python main.py --sample        # офлайн-проверка на встроенных примерах, без сети
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from bot.render import render
from bot.sources import Item, fetch_facts, fetch_news
from bot.writer import write_post

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data/history.json"
OUTPUT = ROOT / "output"

SAMPLE = [
    Item("news", "Астрономы нашли планету, у которой год длится меньше суток",
         "Экзопланета обращается вокруг своей звезды за 17 часов. Она почти вдвое больше Земли, "
         "а температура на поверхности превышает 2000 градусов.", "https://example.org/1", "N+1"),
    Item("fact", "1928 год: Александр Флеминг обнаружил пенициллин",
         "Пенициллин был открыт случайно: плесень попала в чашку с бактериями, оставленную в лаборатории.",
         "https://ru.wikipedia.org/wiki/Пенициллин", "Википедия"),
]


def load_history() -> list[dict]:
    if HISTORY.exists():
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    return []


def pick_kind(requested: str, history: list[dict]) -> str:
    if requested != "auto":
        return requested
    last = history[-1]["kind"] if history else "fact"
    return "news" if last == "fact" else "fact"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["auto", "news", "fact"], default="auto")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()
    publish = args.publish or os.getenv("PUBLISH", "false").lower() == "true"

    history = load_history()
    seen = {h["url"] for h in history} | {h["source_title"] for h in history}

    if args.sample:
        candidates = SAMPLE
        kind = "sample"
    else:
        kind = pick_kind(args.kind, history)
        candidates = fetch_news(ROOT / "sources.json") if kind == "news" else fetch_facts()
        if not candidates:  # источник пуст, пробуем другой тип
            kind = "fact" if kind == "news" else "news"
            candidates = fetch_news(ROOT / "sources.json") if kind == "news" else fetch_facts()
    candidates = [c for c in candidates if c.url not in seen and c.title not in seen][:25]
    if not candidates:
        raise SystemExit("Нет новых материалов для поста")

    post, item = write_post(candidates)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    image_path = render(post.category, post.title, post.body, item.source,
                        os.getenv("CHANNEL_HANDLE", "@your_channel"), OUTPUT / f"{stamp}.jpg")

    hashtags = " ".join("#" + h.lstrip("#").replace(" ", "") for h in post.hashtags)
    caption = f"{post.caption}\n\nИсточник: {item.source}\n\n{hashtags}"
    (OUTPUT / f"{stamp}.txt").write_text(caption, encoding="utf-8")
    print(f"Картинка: {image_path}\n\n{caption}\n")

    record = {"time": stamp, "kind": item.kind, "url": item.url, "source_title": item.title,
              "title": post.title, "image": image_path.name, "published_id": None}

    if publish:
        from bot.hosting import upload
        from bot.instagram import publish_photo
        image_url = upload(image_path)
        record["published_id"] = publish_photo(image_url, caption)
        print(f"Опубликовано: {record['published_id']}")
    else:
        print("Режим предпросмотра: в Instagram ничего не отправлено (включите PUBLISH=true или --publish).")

    if not args.sample:
        history.append(record)
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(history[-500:], ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
