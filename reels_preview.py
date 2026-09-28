"""Пробный ролик из первого поста очереди: фото по теме + анимация текста. Ничего не публикует."""
import json
from pathlib import Path

from bot.media import fetch_photos
from bot.video import render_video

ROOT = Path(__file__).resolve().parent
post_file = sorted((ROOT / "data/queue").glob("*.json"))[0]
post = json.loads(post_file.read_text(encoding="utf-8"))
photos = fetch_photos(post.get("media") or [post["title"]], ROOT / "output/photos")
print(f"{post_file.name}: фото {len(photos)}")
for ph in photos:
    print(" ", ph.credit, ph.page)
out = ROOT / "previews/reels.mp4"
render_video(post["category"], post["title"], post["body"], post["source"], "@bucho2", out, photos=photos)
(ROOT / "previews/reels.txt").write_text(
    post["title"] + "\n" + "\n".join(f"{ph.credit} {ph.page}" for ph in photos) + "\n", encoding="utf-8")
print("Готово:", out)
