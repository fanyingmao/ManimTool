"""视频合成中复用的覆盖层渲染（PIL 绘制 → numpy 数组）。

把"章节进度条 / 标题 / 字幕"这种纯静态图像的绘制逻辑和合成器解耦，
便于在 MoviePy 与 FFmpeg 两种后端中共用。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from manimtool.logging import logger

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(font: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (font, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates: list[str] = []
    if font:
        candidates.append(font)
    candidates.extend(_FONT_CANDIDATES)
    for path in candidates:
        try:
            f = ImageFont.truetype(path, size=size)
            _FONT_CACHE[key] = f
            return f
        except (OSError, ValueError):
            continue
    logger.warning(f"未找到合适字体（请求={font!r}），回退到 PIL 默认字体")
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


@dataclass(frozen=True)
class ChapterMeta:
    scene_id: str
    title: str
    duration: float


@dataclass
class OverlayStyle:
    width: int
    height: int
    font: str
    title_font_size: int
    subtitle_font_size: int
    progress_bar_enabled: bool
    progress_bar_height: int
    progress_bar_color: str
    progress_bar_bg_color: str
    progress_bar_padding: int
    chapter_label_color: str
    subtitle_box_color: str
    subtitle_box_opacity: float
    background_color: str


def render_progress_bar(
    style: OverlayStyle,
    chapters: list[ChapterMeta],
    current_index: int,
    progress_in_chapter: float,
) -> Image.Image:
    """绘制顶部进度条 + 章节标签条（带透明通道）。"""
    width = style.width
    bar_h = style.progress_bar_height
    pad = style.progress_bar_padding
    label_h = max(style.subtitle_font_size + 18, 48)
    total_h = pad + label_h + 12 + bar_h + pad // 2

    img = Image.new("RGBA", (width, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    label_font = _load_font(style.font, style.subtitle_font_size)
    bar_y = pad + label_h + 12
    bar_x0 = pad
    bar_x1 = width - pad
    bar_w = bar_x1 - bar_x0

    durations = [max(c.duration, 0.001) for c in chapters]
    total = sum(durations)
    fractions = [d / total for d in durations]

    cum = 0.0
    seg_xs: list[tuple[float, float]] = []
    for f in fractions:
        seg_xs.append((bar_x0 + cum * bar_w, bar_x0 + (cum + f) * bar_w))
        cum += f

    bg = _hex_to_rgba(style.progress_bar_bg_color, 220)
    fg = _hex_to_rgba(style.progress_bar_color, 255)
    dim = _hex_to_rgba(style.progress_bar_color, 90)

    draw.rounded_rectangle(
        (bar_x0, bar_y, bar_x1, bar_y + bar_h),
        radius=bar_h // 2,
        fill=bg,
    )

    for i, (x0, x1) in enumerate(seg_xs):
        if i < current_index:
            color = fg
            fill_to = x1
        elif i == current_index:
            color = fg
            fill_to = x0 + (x1 - x0) * max(0.0, min(1.0, progress_in_chapter))
        else:
            color = dim
            fill_to = x0
        if fill_to - x0 > 0.5:
            draw.rounded_rectangle(
                (x0, bar_y, fill_to, bar_y + bar_h),
                radius=bar_h // 2,
                fill=color,
            )
        if i < len(seg_xs) - 1:
            sx = int(x1)
            draw.rectangle((sx - 1, bar_y - 2, sx + 1, bar_y + bar_h + 2), fill=(0, 0, 0, 80))

    label_y = pad
    for i, (chap, (x0, x1)) in enumerate(zip(chapters, seg_xs, strict=True)):
        text = f"{i + 1}. {chap.title}"
        if i == current_index:
            text_color = _hex_to_rgba(style.chapter_label_color, 255)
            box_color = _hex_to_rgba(style.progress_bar_color, 230)
        else:
            text_color = _hex_to_rgba(style.chapter_label_color, 170)
            box_color = _hex_to_rgba("#1f2330", 160)

        tw, th = _measure(draw, text, label_font)
        seg_w = x1 - x0
        if tw + 24 > seg_w:
            avail = max(seg_w - 28, 30)
            text = _truncate(text, label_font, draw, int(avail))
            tw, th = _measure(draw, text, label_font)
        cx = (x0 + x1) / 2
        bx0 = cx - tw / 2 - 12
        bx1 = cx + tw / 2 + 12
        by0 = label_y
        by1 = label_y + th + 12
        draw.rounded_rectangle((bx0, by0, bx1, by1), radius=10, fill=box_color)
        draw.text((cx - tw / 2, by0 + 6), text, fill=text_color, font=label_font)

    return img


def render_subtitle(style: OverlayStyle, text: str) -> Image.Image | None:
    """绘制底部字幕条（带透明通道）。无文本时返回 None。"""
    if not text.strip():
        return None
    width = style.width
    font = _load_font(style.font, style.subtitle_font_size)

    pad_x = 36
    pad_y = 18
    max_w = width - 2 * pad_x - 40

    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    lines = _wrap_text(text, font, d, max_w)
    line_sizes = [_measure(d, ln, font) for ln in lines]
    line_h = max((h for _, h in line_sizes), default=style.subtitle_font_size)
    text_w = max((w for w, _ in line_sizes), default=0)
    text_h = line_h * len(lines) + (len(lines) - 1) * 6

    box_w = min(width - 2 * 40, text_w + 2 * pad_x)
    box_h = text_h + 2 * pad_y

    img = Image.new("RGBA", (width, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    box_x0 = (width - box_w) // 2
    box_x1 = box_x0 + box_w
    alpha = int(max(0.0, min(1.0, style.subtitle_box_opacity)) * 255)
    draw.rounded_rectangle(
        (box_x0, 0, box_x1, box_h),
        radius=14,
        fill=_hex_to_rgba(style.subtitle_box_color, alpha),
    )

    y = pad_y
    for ln, (lw, _) in zip(lines, line_sizes, strict=True):
        x = (width - lw) // 2
        draw.text((x, y), ln, fill=(255, 255, 255, 255), font=font)
        y += line_h + 6
    return img


def composite_image_on_canvas(
    canvas_size: tuple[int, int],
    background_color: str,
    image_path: Path,
    padding_top: int,
    padding_bottom: int,
) -> Image.Image:
    """把渲染好的图（PNG）按比例缩放后居中贴到画布。"""
    w, h = canvas_size
    canvas = Image.new("RGB", (w, h), color=_hex_to_rgb(background_color))
    if not image_path.exists():
        return canvas
    img = Image.open(image_path).convert("RGBA")
    avail_w = w - 80
    avail_h = h - padding_top - padding_bottom
    if avail_w <= 0 or avail_h <= 0:
        return canvas
    iw, ih = img.size
    scale = min(avail_w / iw, avail_h / ih, 1.0)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (w - nw) // 2
    y = padding_top + (avail_h - nh) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def to_numpy(img: Image.Image) -> np.ndarray:
    return np.array(img)


def _hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex_to_rgba(s: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = _hex_to_rgb(s)
    return (r, g, b, alpha)


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_w: int,
) -> list[str]:
    lines: list[str] = []
    cur = ""
    for ch in text:
        candidate = cur + ch
        w, _ = _measure(draw, candidate, font)
        if w > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines


def _truncate(
    text: str,
    font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_w: int,
) -> str:
    ell = "…"
    if _measure(draw, text, font)[0] <= max_w:
        return text
    out = ""
    for ch in text:
        if _measure(draw, out + ch + ell, font)[0] > max_w:
            return out + ell
        out += ch
    return out + ell
