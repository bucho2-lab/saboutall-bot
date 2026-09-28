"""Рендер картинки 1080×1350 (формат 4:5, лучший охват в ленте Instagram)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
PAD = 90
ROOT = Path(__file__).resolve().parent.parent

# Палитры по категориям: (верх градиента, низ градиента, акцент)
PALETTES = {
    "КОСМОС": ((18, 16, 58), (58, 22, 92), (255, 196, 87)),
    "НАУКА": ((10, 38, 64), (14, 88, 110), (122, 232, 196)),
    "ИСТОРИЯ": ((52, 30, 18), (110, 62, 30), (255, 214, 150)),
    "ПРИРОДА": ((12, 48, 30), (32, 100, 60), (200, 240, 120)),
    "ТЕХНОЛОГИИ": ((14, 20, 36), (30, 52, 96), (96, 190, 255)),
}
DEFAULT_PALETTE = ((24, 24, 32), (60, 40, 80), (255, 120, 120))

FONT_CANDIDATES = {
    "bold": [ROOT / "fonts/Montserrat-Bold.ttf",
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")],
    "regular": [ROOT / "fonts/Montserrat-Medium.ttf",
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")],
}


def _font(style: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[style]:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise FileNotFoundError("Нет шрифта с кириллицей: положите Montserrat в fonts/ или установите DejaVu")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit(draw, text, style, max_size, min_size, max_width, max_height, spacing=1.18):
    """Подбирает самый крупный кегль, при котором текст влезает в блок."""
    for size in range(max_size, min_size - 1, -2):
        font = _font(style, size)
        lines = _wrap(draw, text, font, max_width)
        height = int(len(lines) * size * spacing)
        if height <= max_height:
            return font, lines, size, height
    font = _font(style, min_size)
    return font, _wrap(draw, text, font, max_width), min_size, max_height


def _gradient(top, bottom) -> Image.Image:
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img


def render(category: str, title: str, body: str, source: str, handle: str, out_path: Path) -> Path:
    top, bottom, accent = PALETTES.get(category.upper(), DEFAULT_PALETTE)
    img = _gradient(top, bottom)
    draw = ImageDraw.Draw(img)
    max_w = W - 2 * PAD

    # Декоративный круг-акцент
    draw.ellipse((W - 330, -170, W + 170, 330), outline=accent, width=6)

    # Плашка категории
    tag_font = _font("bold", 34)
    tag = category.upper()
    tw = draw.textlength(tag, font=tag_font)
    draw.rounded_rectangle((PAD, PAD, PAD + tw + 48, PAD + 64), radius=32, fill=accent)
    draw.text((PAD + 24, PAD + 13), tag, font=tag_font, fill=top)

    # Заголовок
    y = PAD + 150
    t_font, t_lines, t_size, t_h = _fit(draw, title, "bold", 92, 54, max_w, 460)
    for line in t_lines:
        draw.text((PAD, y), line, font=t_font, fill=(255, 255, 255))
        y += int(t_size * 1.18)

    # Черта-разделитель
    y += 30
    draw.rectangle((PAD, y, PAD + 120, y + 8), fill=accent)
    y += 60

    # Текст
    footer_y = H - PAD - 40
    b_font, b_lines, b_size, _ = _fit(draw, body, "regular", 50, 32, max_w, footer_y - y - 40, 1.4)
    for line in b_lines:
        draw.text((PAD, y), line, font=b_font, fill=(236, 236, 244))
        y += int(b_size * 1.4)

    # Подвал
    f_font = _font("regular", 30)
    draw.text((PAD, footer_y), handle, font=f_font, fill=accent)
    src = f"Источник: {source}"
    draw.text((W - PAD - draw.textlength(src, font=f_font), footer_y), src, font=f_font, fill=(190, 190, 205))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92)  # Instagram Graph API принимает только JPEG
    return out_path
