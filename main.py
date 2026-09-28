"""Один запуск = один пост.

    python main.py                 # подготовить пост (картинка + подпись в output/), без публикации
    python main.py --publish       # подготовить и опубликовать в Instagram
    python main.py --kind fact     # только факты; --kind news только новости; по умолчанию чередует
    python main.py --sample        # офлайн-проверка на встроенных примерах, без сети
    python main.py --format reel   # ролик Reels 9:16 на фоне фото по теме вместо картинки
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from bot.render import render
from bot.sources import Item, fetch_facts, fetch_news
from bot.writer import Post, write_post

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data/history.json"
CANDIDATES = ROOT / "data/candidates.json"
QUEUE = ROOT / "data/queue"
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


def next_from_queue(seen: set) -> tuple[Path, dict] | None:
    """Самый старый готовый пост из data/queue/, который ещё не публиковался."""
    for path in sorted(QUEUE.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[queue] пропускаю {path.name}: {e}")
            continue
        if data.get("url") in seen:
            path.unlink()
            continue
        return path, data
    return None


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
    ap.add_argument("--format", choices=["photo", "reel"], default="photo")
    args = ap.parse_args()
    publish = args.publish or os.getenv("PUBLISH", "false").lower() == "true"

    history = load_history()
    # повторы отсекаем только по реально опубликованным постам, пробные прогоны не в счёт
    published = [h for h in history if h.get("published_id")]
    seen = {h["url"] for h in published} | {h["source_title"] for h in published}

    queued = None
    media_queries: list[str] = []
    if args.sample:
        candidates = SAMPLE
    else:
        news, facts = fetch_news(ROOT / "sources.json"), fetch_facts()
        fresh = lambda items: [c for c in items if c.url not in seen and c.title not in seen]
        news, facts = fresh(news), fresh(facts)
        # свежие материалы для Claude, который по расписанию пишет посты в data/queue/
        CANDIDATES.write_text(json.dumps(
            {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
             "news": [c.to_dict() for c in news[:30]], "facts": [c.to_dict() for c in facts[:15]]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        queued = next_from_queue(seen)
        kind = pick_kind(args.kind, history)
        candidates = (news if kind == "news" else facts) or news or facts
    candidates = candidates[:25]

    if queued:
        path, data = queued
        post = Post(chosen_index=0, **{k: data[k] for k in ("category", "title", "body", "caption", "hashtags")})
        item = Item(data.get("kind", "news"), data.get("source_title", data["title"]), "", data.get("url", ""), data["source"])
        media_queries = data.get("media") or []
        print(f"Пост из очереди: {path.name}")
    elif candidates:
        post, item = write_post(candidates)
    else:
        raise SystemExit("Нет новых материалов для поста")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    handle = os.getenv("CHANNEL_HANDLE", "@your_channel")
    hashtags = " ".join("#" + h.lstrip("#").replace(" ", "") for h in post.hashtags)
    caption = f"{post.caption}\n\nИсточник: {item.source}"

    if args.format == "reel":
        from bot.media import fetch_photos
        from bot.video import render_video
        photos = fetch_photos(media_queries or [post.title], OUTPUT / "photos")
        media_path = render_video(post.category, post.title, post.body, item.source, handle,
                                  OUTPUT / f"{stamp}.mp4", photos=photos)
        if photos:  # свободные лицензии требуют указать автора
            caption += "\nФото: " + "; ".join(dict.fromkeys(ph.credit for ph in photos)) + " (Wikimedia Commons)"
    else:
        media_path = render(post.category, post.title, post.body, item.source, handle, OUTPUT / f"{stamp}.jpg")
    caption += f"\n\n{hashtags}"
    (OUTPUT / f"{stamp}.txt").write_text(caption, encoding="utf-8")
    print(f"Файл: {media_path}\n\n{caption}\n")

    record = {"time": stamp, "kind": item.kind, "format": args.format, "url": item.url,
              "source_title": item.title, "title": post.title, "image": media_path.name, "published_id": None}

    if publish:
        from bot.hosting import upload
        from bot.instagram import publish_photo, publish_reel
        media_url = upload(media_path)
        send = publish_reel if args.format == "reel" else publish_photo
        record["published_id"] = send(media_url, caption)
        print(f"Опубликовано: {record['published_id']}")
        if queued:
            queued[0].unlink()  # в режиме предпросмотра пост остаётся в очереди
    else:
        print("Режим предпросмотра: в Instagram ничего не отправлено (включите PUBLISH=true или --publish).")

    if not args.sample:
        history.append(record)
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(history[-500:], ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
