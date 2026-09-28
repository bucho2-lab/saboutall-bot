"""Выбор самого интересного кандидата и написание текста поста через Claude."""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .sources import Item

SYSTEM = """Ты редактор русскоязычного Instagram-канала «интересные факты и новости».
Тебе дают список кандидатов (новости и исторические факты). Выбери ОДИН, который
вызовет у широкой аудитории реакцию «ого, не знал». Избегай политики, войн, катастроф
с жертвами, криминала и чёрного юмора, если есть что-то нейтральное и любопытное.

Пиши только на основе данного текста кандидата. Не добавляй цифры, даты и детали,
которых в нём нет. Текст должен быть твоими словами, а не копией источника.

Поля:
- title: цепляющий заголовок для картинки, до 60 символов, без точки в конце.
- body: 1–3 коротких предложения для картинки, до 220 символов, самое интересное.
- caption: подпись под постом, 400–900 символов, 2–4 абзаца, живо и понятно,
  в конце вопрос к читателям. Без хэштегов и без ссылок.
- hashtags: 6–10 хэштегов на русском без символа #.
- category: одно слово для плашки на картинке, например НАУКА, КОСМОС, ИСТОРИЯ, ТЕХНОЛОГИИ, ПРИРОДА."""


class Post(BaseModel):
    chosen_index: int = Field(description="Номер выбранного кандидата из списка")
    category: str
    title: str
    body: str
    caption: str
    hashtags: list[str]


def _format_candidates(items: list[Item]) -> str:
    lines = []
    for i, it in enumerate(items):
        kind = "НОВОСТЬ" if it.kind == "news" else "ФАКТ"
        lines.append(f"[{i}] ({kind}, {it.source}) {it.title}\n{it.summary}")
    return "\n\n".join(lines)


def write_post(items: list[Item]) -> tuple[Post, Item]:
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _write_with_claude(items)
        except Exception as e:
            print(f"[writer] Claude недоступен: {e}")
    if os.getenv("GITHUB_TOKEN") and os.getenv("GH_MODEL", "openai/gpt-4.1-mini") != "none":
        try:
            return _write_with_github_models(items)
        except Exception as e:
            print(f"[writer] GitHub Models недоступен: {e}")
    print("[writer] собираю пост по шаблону")
    return _write_fallback(items)


def _write_with_github_models(items: list[Item]) -> tuple[Post, Item]:
    """Бесплатная модель из GitHub Models: в Actions работает по встроенному GITHUB_TOKEN, ключ не нужен."""
    import json
    import requests

    schema = json.dumps(Post.model_json_schema(), ensure_ascii=False)
    models = [os.getenv("GH_MODEL", "openai/gpt-4.1-mini"), "openai/gpt-4o-mini"]
    errors = []
    for model in dict.fromkeys(models):
        resp = requests.post(
            "https://models.github.ai/inference/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                     "Accept": "application/json", "Content-Type": "application/json",
                     "X-GitHub-Api-Version": "2022-11-28"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM + "\n\nОтветь только JSON-объектом по схеме:\n" + schema},
                    {"role": "user", "content": "Кандидаты:\n\n" + _format_candidates(items)},
                ],
                "temperature": 0.7,
                "stream": False,
            },
            timeout=120,
        )
        try:
            content = resp.json()["choices"][0]["message"]["content"] or ""
            # модель иногда оборачивает JSON в ```json ... ```
            post = Post.model_validate_json(content[content.find("{"):content.rfind("}") + 1])
        except Exception as e:
            errors.append(f"{model}: {resp.status_code} {resp.headers.get('content-type')} "
                          f"len={len(resp.content)} {resp.text[:300]!r} ({e})")
            continue
        idx = post.chosen_index if 0 <= post.chosen_index < len(items) else 0
        return post, items[idx]
    raise RuntimeError("; ".join(errors))


def _write_fallback(items: list[Item]) -> tuple[Post, Item]:
    # без модели берём первый материал, у которого есть описание: иначе картинка будет из одного заголовка
    idx = next((i for i, x in enumerate(items) if len(x.summary) > 60), 0)
    it = items[idx]
    title = it.title if len(it.title) <= 90 else it.title[:87].rstrip() + "…"
    body = it.summary[:217].rstrip() + ("…" if len(it.summary) > 217 else "")
    post = Post(
        chosen_index=idx,
        category="ИСТОРИЯ" if it.kind == "fact" else "НОВОСТИ",
        title=title,
        body=body,
        caption="\n\n".join(x for x in (it.title, it.summary[:800], "А вы знали об этом?") if x),
        hashtags=["факты", "интересныефакты", "новости", "знаниясила", "этоинтересно"],
    )
    return post, it
