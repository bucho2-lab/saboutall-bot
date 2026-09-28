"""Короткий вертикальный ролик 1080×1920 для Reels из того же поста: движущийся фон, текст появляется по строкам."""
from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .render import DEFAULT_PALETTE, PALETTES, _fit, _font

W, H = 1080, 1920
PAD = 90
FPS = 30


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # запасной вариант: ffmpeg из pip-пакета
    return imageio_ffmpeg.get_ffmpeg_exe()


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _background(top, bottom) -> Image.Image:
    """Градиент выше кадра: при движении окна вниз фон плавно «течёт»."""
    tall = H + 600
    grad = Image.linear_gradient("L").resize((W, tall))
    return Image.composite(Image.new("RGB", (W, tall), bottom), Image.new("RGB", (W, tall), top), grad)


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _photo_background(photos, top, duration):
    """Слайд-шоу фото с плавным наездом и затемнением, чтобы текст читался."""
    big = [_cover(Image.open(p), int(W * 1.15), int(H * 1.15)) for p in photos]
    shade = Image.new("RGBA", (W, H))
    sd = ImageDraw.Draw(shade)
    for y in range(H):
        a = int(60 + 140 * (y / H))  # сверху фото видно лучше, к тексту и подвалу темнее
        sd.line((0, y, W, y), fill=top + (a,))
    seg = duration / len(big)
    fade = 0.6

    def frame_at(t: float) -> Image.Image:
        k = min(int(t / seg), len(big) - 1)

        def shot(i, tt):
            src = big[i]
            z = 1.0 + 0.12 * (tt / seg)  # наезд
            cw, ch = int(src.width / z), int(src.height / z)
            dx = (src.width - cw) * (0.5 + 0.3 * math.sin(i + tt * 0.3))
            dy = (src.height - ch) * 0.5
            return src.crop((int(dx), int(dy), int(dx) + cw, int(dy) + ch)).resize((W, H), Image.BILINEAR)

        local = t - k * seg
        frame = shot(k, local)
        if k + 1 < len(big) and local > seg - fade:
            frame = Image.blend(frame, shot(k + 1, local - seg), (local - (seg - fade)) / fade)
        frame = frame.convert("RGBA")
        frame.alpha_composite(shade)
        return frame

    return frame_at


def _text_layer(lines, font, size, spacing, color) -> list[Image.Image]:
    out = []
    for line in lines:
        layer = Image.new("RGBA", (W, int(size * spacing) + 20), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((PAD, 0), line, font=font, fill=color)
        out.append(layer)
    return out


def render_video(category: str, title: str, body: str, source: str, handle: str,
                 out_path: Path, duration: float = 12.0, photos=None) -> Path:
    """photos: список Photo из bot.media; без них фон будет градиентом."""
    top, bottom, accent = PALETTES.get(category.upper(), DEFAULT_PALETTE)
    bg = _background(top, bottom)
    photo_bg = _photo_background([ph.path for ph in photos], top, duration) if photos else None
    probe = ImageDraw.Draw(Image.new("RGB", (W, H)))
    max_w = W - 2 * PAD

    t_font, t_lines, t_size, _ = _fit(probe, title, "bold", 104, 60, max_w, 560)
    b_font, b_lines, b_size, _ = _fit(probe, body, "regular", 56, 36, max_w, 620, 1.4)
    title_layers = _text_layer(t_lines, t_font, t_size, 1.18, (255, 255, 255))
    body_layers = _text_layer(b_lines, b_font, b_size, 1.4, (236, 236, 244))

    tag_font = _font("bold", 40)
    tag = category.upper()
    tw = int(probe.textlength(tag, font=tag_font))
    pill = Image.new("RGBA", (tw + 60, 76), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle((0, 0, tw + 59, 75), radius=38, fill=accent)
    pd.text((30, 15), tag, font=tag_font, fill=top)

    f_font = _font("regular", 36)
    footer = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    fd = ImageDraw.Draw(footer)
    fd.text((PAD, 0), handle, font=f_font, fill=accent)
    src = f"Источник: {source}"
    fd.text((W - PAD - fd.textlength(src, font=f_font), 0), src, font=f_font, fill=(190, 190, 205))
    credit = None
    if photos:
        c_font = _font("regular", 24)
        text = "Фото: " + "; ".join(dict.fromkeys(ph.credit for ph in photos))
        credit = Image.new("RGBA", (W, 40), (0, 0, 0, 0))
        cd = ImageDraw.Draw(credit)
        while cd.textlength(text, font=c_font) > W - 2 * PAD and len(text) > 20:
            text = text[:-2]
        cd.text((PAD, 0), text, font=c_font, fill=(200, 200, 210))

    # вертикальная компоновка: блок текста по центру кадра
    title_h = len(t_lines) * int(t_size * 1.18)
    body_h = len(b_lines) * int(b_size * 1.4)
    block_h = 76 + 70 + title_h + 50 + 10 + 50 + body_h
    y0 = max(260, (H - block_h) // 2 - 60)
    y_title = y0 + 76 + 70
    y_line = y_title + title_h + 50
    y_body = y_line + 60

    title_start, title_step = 0.4, 0.35
    body_start = title_start + len(t_lines) * title_step + 0.6
    body_step = 0.55
    frames = int(duration * FPS)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ffmpeg(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for i in range(frames):
        t = i / FPS
        # фон медленно сползает, декоративный круг плавает
        if photo_bg:
            frame = photo_bg(t)
            d = ImageDraw.Draw(frame)
        else:
            shift = int(600 * t / duration)
            frame = bg.crop((0, shift, W, shift + H)).convert("RGBA")
            d = ImageDraw.Draw(frame)
            cx = W - 60 + 40 * math.sin(t * 0.6)
            cy = 180 + 30 * math.cos(t * 0.5)
            d.ellipse((cx - 300, cy - 300, cx + 300, cy + 300), outline=accent, width=6)
            d.ellipse((80 + 20 * math.cos(t * 0.4) - 160, H + 40 - 160, 80 + 20 * math.cos(t * 0.4) + 160, H + 40 + 160),
                      outline=accent + (90,), width=3)
        if credit:
            frame.alpha_composite(credit, (0, H - PAD - 50))

        # полоса прогресса сверху, как в сторис
        d.rectangle((0, 0, int(W * t / duration), 8), fill=accent)

        a = _ease((t - 0.1) / 0.5)
        if a > 0:
            p = pill.copy()
            p.putalpha(p.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(p, (PAD, y0 + int(30 * (1 - a))))

        for k, layer in enumerate(title_layers):
            a = _ease((t - title_start - k * title_step) / 0.5)
            if a > 0:
                l2 = layer.copy()
                l2.putalpha(l2.getchannel("A").point(lambda v: int(v * a)))
                frame.alpha_composite(l2, (0, y_title + k * int(t_size * 1.18) + int(40 * (1 - a))))

        a = _ease((t - body_start + 0.4) / 0.5)
        if a > 0:
            d.rectangle((PAD, y_line, PAD + int(140 * a), y_line + 10), fill=accent)

        for k, layer in enumerate(body_layers):
            a = _ease((t - body_start - k * body_step) / 0.5)
            if a > 0:
                l2 = layer.copy()
                l2.putalpha(l2.getchannel("A").point(lambda v: int(v * a)))
                frame.alpha_composite(l2, (0, y_body + k * int(b_size * 1.4) + int(30 * (1 - a))))

        a = _ease((t - (duration - 3.0)) / 0.6)
        if a > 0:
            f2 = footer.copy()
            f2.putalpha(f2.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(f2, (0, H - PAD - 120))

        proc.stdin.write(frame.convert("RGB").tobytes())

    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg не собрал видео")
    return out_path
