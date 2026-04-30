"""视频合成中复用的覆盖层渲染（PIL 绘制 → numpy 数组）。

把"章节进度条 / 标题 / 字幕"这种纯静态图像的绘制逻辑和合成器解耦，
便于在 MoviePy 与 FFmpeg 两种后端中共用。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from manimtool.logging import logger

_FONT_CACHE: dict[tuple[str, int], Any] = {}

# Linux / 常见发行版
_FONT_CANDIDATES_LINUX = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# macOS：PIL 必须用字体文件路径；PingFang / 冬青黑体等可覆盖中文
_FONT_CANDIDATES_DARWIN = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Supplemental/Kaiti.ttc",
    "/opt/homebrew/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/opt/homebrew/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


def _font_file_candidates(requested: str) -> list[str]:
    """构造 PIL ImageFont.truetype 可用的路径列表（族名会被忽略，走平台默认）。"""
    out: list[str] = []
    if requested:
        p = Path(requested).expanduser()
        if p.is_file():
            out.append(str(p.resolve()))
        # 族名如 "Noto Sans CJK SC" 不能传给 truetype，否则会失败
    if sys.platform == "darwin":
        out.extend(_FONT_CANDIDATES_DARWIN)
    out.extend(_FONT_CANDIDATES_LINUX)
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _load_font(font: str, size: int) -> Any:
    key = (font, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for path in _font_file_candidates(font):
        try:
            f = ImageFont.truetype(path, size=size)
            _FONT_CACHE[key] = f
            return f
        except (OSError, ValueError):
            continue
    logger.warning(
        f"未找到可渲染中文的字体文件（配置 font={font!r}）。"
        "请在 video.font 中填写本机 .ttf/.ttc 绝对路径，或安装 Noto CJK。"
    )
    return ImageFont.load_default()


def _measure(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


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
    """绘制顶部章节导航（进度嵌在标题带内，带透明通道）。"""
    width = style.width
    pad = style.progress_bar_padding
    label_h = max(style.subtitle_font_size + 20, 52)
    total_h = pad + label_h + 10

    img = Image.new("RGBA", (width, total_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    label_font = _load_font(style.font, style.subtitle_font_size)
    nav_y0 = pad
    nav_y1 = nav_y0 + label_h
    nav_x0 = pad
    nav_x1 = width - pad
    nav_w = nav_x1 - nav_x0

    durations = [max(c.duration, 0.001) for c in chapters]
    total = sum(durations)
    fractions = [d / total for d in durations]

    cum = 0.0
    seg_xs: list[tuple[float, float]] = []
    for f in fractions:
        seg_xs.append((nav_x0 + cum * nav_w, nav_x0 + (cum + f) * nav_w))
        cum += f

    nav_bg = _hex_to_rgba(style.progress_bar_bg_color, 205)
    active_bg = _hex_to_rgba(style.progress_bar_color, 140)
    done_bg = _hex_to_rgba(style.progress_bar_color, 180)

    draw.rounded_rectangle(
        (nav_x0, nav_y0, nav_x1, nav_y1),
        radius=max(10, label_h // 4),
        fill=nav_bg,
    )

    # 当前章节左侧为已完成；当前章节内按进度填充。
    for i, (x0, x1) in enumerate(seg_xs):
        if i < current_index:
            color = done_bg
            fill_to = x1
        elif i == current_index:
            color = active_bg
            fill_to = x0 + (x1 - x0) * max(0.0, min(1.0, progress_in_chapter))
        else:
            fill_to = x0
        if fill_to - x0 > 0.5:
            draw.rectangle((x0, nav_y0, fill_to, nav_y1), fill=color)
        if i < len(seg_xs) - 1:
            sx = int(x1)
            draw.rectangle((sx - 1, nav_y0 + 6, sx + 1, nav_y1 - 6), fill=(255, 255, 255, 110))

    label_y = nav_y0 + (label_h - style.subtitle_font_size) // 2 - 2
    for i, (chap, (x0, x1)) in enumerate(zip(chapters, seg_xs, strict=True)):
        text = chap.title
        if i == current_index:
            text_color = _hex_to_rgba(style.chapter_label_color, 255)
        else:
            text_color = _hex_to_rgba(style.chapter_label_color, 222)

        tw, th = _measure(draw, text, label_font)
        seg_w = x1 - x0
        if tw + 18 > seg_w:
            avail = max(seg_w - 20, 30)
            text = _truncate(text, label_font, draw, int(avail))
            tw, th = _measure(draw, text, label_font)
        cx = (x0 + x1) / 2
        draw.text((cx - tw / 2, label_y + (th * 0.05)), text, fill=text_color, font=label_font)

    return img


def render_progress_bar_layout(
    style: OverlayStyle,
    chapters: list[ChapterMeta],
    current_index: int,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """渲染"标签 + 已完成章节进度条"的静态层（不画当前章节填充）。

    返回 ``(image, (bar_x0, bar_y, bar_x1, bar_h))``，调用方可基于该坐标
    在视频合成时动态绘制当前章节的填充矩形（避免逐帧 overlay PNG）。
    """
    img = render_progress_bar(style, chapters, current_index, progress_in_chapter=0.0)
    pad = style.progress_bar_padding
    width = style.width
    label_h = max(style.subtitle_font_size + 20, 52)
    bar_h = max(4, min(10, style.progress_bar_height))
    bar_y = pad + label_h - bar_h - 6
    bar_x0 = pad
    bar_x1 = width - pad
    return img, (bar_x0, bar_y, bar_x1, bar_h)


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
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (w - nw) // 2
    y = padding_top + (avail_h - nh) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def to_numpy(img: Image.Image) -> np.ndarray:
    return np.array(img)


def hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex_to_rgb(s: str) -> tuple[int, int, int]:
    return hex_to_rgb(s)


def _hex_to_rgba(s: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(s)
    return (r, g, b, alpha)


def _wrap_text(
    text: str,
    font: Any,
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
    font: Any,
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
