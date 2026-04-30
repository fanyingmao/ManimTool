"""覆盖层渲染基本测试（纯 PIL，不依赖 moviepy/ffmpeg）。"""

from __future__ import annotations

from manimtool.video.overlays import (
    ChapterMeta,
    OverlayStyle,
    render_progress_bar,
    render_subtitle,
)


def _style() -> OverlayStyle:
    return OverlayStyle(
        width=1280,
        height=720,
        font="",
        title_font_size=44,
        subtitle_font_size=28,
        progress_bar_enabled=True,
        progress_bar_height=12,
        progress_bar_color="#4C6EF5",
        progress_bar_bg_color="#2B2F38",
        progress_bar_padding=24,
        chapter_label_color="#FFFFFF",
        subtitle_box_color="#000000",
        subtitle_box_opacity=0.5,
        background_color="#0E1117",
    )


def test_render_progress_bar_returns_rgba_image() -> None:
    chapters = [
        ChapterMeta(scene_id="a", title="第一节", duration=5.0),
        ChapterMeta(scene_id="b", title="第二节", duration=10.0),
        ChapterMeta(scene_id="c", title="第三节", duration=8.0),
    ]
    img = render_progress_bar(_style(), chapters, current_index=1, progress_in_chapter=0.4)
    assert img.mode == "RGBA"
    assert img.size[0] == 1280
    assert img.size[1] > 0


def test_render_subtitle_returns_image_or_none() -> None:
    assert render_subtitle(_style(), "") is None
    img = render_subtitle(_style(), "这是一条测试字幕，用于检查换行与排版。")
    assert img is not None
    assert img.mode == "RGBA"
    assert img.size[0] == 1280
