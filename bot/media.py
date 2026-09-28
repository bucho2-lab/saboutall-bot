"""Фото по теме поста со свободной лицензией из Wikimedia Commons (с указанием автора)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import requests

from .sources import UA

API = "https://commons.wikimedia.org/w/api.php"
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Photo:
    path: Path
    author: str
    license: str
    page: str

    @property
    def credit(self) -> str:
        return f"{self.author} / {self.license}" if self.author else self.license


def _search(query: str, limit: int = 12) -> list[dict]:
    resp = requests.get(API, headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600,
    })
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    return sorted(pages.values(), key=lambda p: p.get("index", 0))


def fetch_photos(queries: list[str], out_dir: Path, per_query: int = 1, total: int = 3) -> list[Photo]:
    """По одному-два крупных фото на каждый запрос, всего не больше total."""
    out_dir.mkdir(parents=True, exist_ok=True)
    photos: list[Photo] = []
    seen: set[str] = set()
    for query in queries:
        taken = 0
        try:
            results = _search(query)
        except Exception as e:
            print(f"[media] {query}: {e}")
            continue
        for page in results:
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            url = info.get("thumburl") or info.get("url")
            if not url or url in seen or info.get("width", 0) < 900:
                continue
            if info.get("width", 0) < info.get("height", 0) * 0.5:  # слишком узкие полосы
                continue
            try:
                img = requests.get(url, headers=UA, timeout=60)
                img.raise_for_status()
            except Exception as e:
                print(f"[media] {url}: {e}")
                continue
            path = out_dir / f"photo{len(photos)}.jpg"
            path.write_bytes(img.content)
            author = TAG_RE.sub("", meta.get("Artist", {}).get("value", "")).strip()
            photos.append(Photo(path, author[:60], meta.get("LicenseShortName", {}).get("value", "Wikimedia Commons"),
                                info.get("descriptionurl", "")))
            seen.add(url)
            taken += 1
            if taken >= per_query or len(photos) >= total:
                break
        if len(photos) >= total:
            break
    return photos
