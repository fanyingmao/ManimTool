"""基于 MoviePy 的视频合成器（兼容 1.x / 2.x）。

实现要点：
    - 每个 scene 用 ImageClip × AudioFileClip 对齐到 TTS 时长，
      确保"读到对应内容才显示对应内容"
    - 顶部叠加章节进度条 + 章节标签条（基于全片累计进度）
    - 底部按 SubtitleCue 时间窗滚动字幕
    - 若 ``Scene.reveal_points`` 非空，在画面左上角叠加按时间逐步出现的要点面板
    - 场景之间使用 crossfade 过渡（可关闭）
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageDraw

try:  # MoviePy 1.x
    from moviepy.editor import (
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_videoclips,
    )

    _MOVIEPY_V2 = False
except ImportError:  # MoviePy 2.x
    from moviepy import (
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_videoclips,
    )

    _MOVIEPY_V2 = True

from manimtool.errors import VideoComposeError
from manimtool.logging import logger
from manimtool.schemas import Scene, SceneArtifact, VideoArtifact
from manimtool.video.base import BaseComposer
from manimtool.video.codec_util import effective_video_codec
from manimtool.video.overlays import (
    ChapterMeta,
    OverlayStyle,
    composite_image_on_canvas,
    render_progress_bar,
    render_subtitle,
    to_numpy,
)
from manimtool.video.overlays import (
    _load_font as _overlay_load_font,
)


def _set_position(clip: Any, pos: Any) -> Any:
    if hasattr(clip, "with_position"):
        return clip.with_position(pos)
    return clip.set_position(pos)


def _set_start(clip: Any, t: float) -> Any:
    if hasattr(clip, "with_start"):
        return clip.with_start(t)
    return clip.set_start(t)


def _set_end(clip: Any, t: float) -> Any:
    if hasattr(clip, "with_end"):
        return clip.with_end(t)
    return clip.set_end(t)


def _set_duration(clip: Any, d: float) -> Any:
    if hasattr(clip, "with_duration"):
        return clip.with_duration(d)
    return clip.set_duration(d)


def _set_audio(clip: Any, audio: Any) -> Any:
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    return clip.set_audio(audio)


def _subclip(clip: Any, t1: float, t2: float) -> Any:
    if hasattr(clip, "subclipped"):
        return clip.subclipped(t1, t2)
    return clip.subclip(t1, t2)


def _crossfadein(clip: Any, d: float) -> Any:
    """2.x 用 vfx.CrossFadeIn，1.x 用 .crossfadein()."""
    if hasattr(clip, "crossfadein"):
        return clip.crossfadein(d)
    try:
        from moviepy import vfx

        return clip.with_effects([vfx.CrossFadeIn(d)])
    except Exception:
        return clip


def _encode_thread_count(config: Any) -> int:
    n = getattr(config, "encode_threads", None)
    if n is not None and int(n) > 0:
        return int(n)
    cores = os.cpu_count() or 4
    # libx264 可吃多线程；Apple Silicon 常见 8～16 核，原先上限 8 偏保守
    return max(4, min(16, cores))


def _moviepy_effective_params(config: Any) -> tuple[int, int, int, Literal["none", "fade", "slide"], float, float, str]:
    """根据 render_profile 得到 (宽, 高, fps, 场景转场, 转场时长秒, 进度条每秒分段, x264 preset)。"""
    w, h = config.resolution
    fps = int(config.fps)
    transition: Literal["none", "fade", "slide"] = config.transition
    trans_d = max(0.0, float(config.transition_duration))
    seg = float(getattr(config, "progress_segments_per_second", 2.0))
    preset = str(getattr(config, "encode_preset", "medium") or "medium")

    if getattr(config, "render_profile", "normal") == "draft":
        w, h = 1280, 720
        fps = min(fps, 24)
        seg = min(seg, 0.5)
        transition = "none"
        trans_d = 0.0
        if preset in ("placebo", "veryslow", "slower", "slow", "medium"):
            preset = "veryfast"

    return w, h, fps, transition, trans_d, seg, preset


def _style_from_config(config: Any, width: int, height: int) -> OverlayStyle:
    return OverlayStyle(
        width=width,
        height=height,
        font=getattr(config, "font", ""),
        title_font_size=getattr(config, "title_font_size", 56),
        subtitle_font_size=getattr(config, "subtitle_font_size", 38),
        progress_bar_enabled=getattr(config, "progress_bar_enabled", True),
        progress_bar_height=getattr(config, "progress_bar_height", 14),
        progress_bar_color=getattr(config, "progress_bar_color", "#4C6EF5"),
        progress_bar_bg_color=getattr(config, "progress_bar_bg_color", "#2B2F38"),
        progress_bar_padding=getattr(config, "progress_bar_padding", 28),
        chapter_label_color=getattr(config, "chapter_label_color", "#FFFFFF"),
        subtitle_box_color=getattr(config, "subtitle_box_color", "#000000"),
        subtitle_box_opacity=getattr(config, "subtitle_box_opacity", 0.55),
        background_color=getattr(config, "background_color", "#0E1117"),
    )


class MoviePyComposer(BaseComposer):
    def compose(
        self,
        title: str,
        artifacts: list[SceneArtifact],
        output_path: Path,
    ) -> VideoArtifact:
        if not artifacts:
            raise VideoComposeError("artifacts 为空，无法合成视频")

        width, height, fps, eff_transition, transition_d, seg_per_sec, encode_preset = (
            _moviepy_effective_params(self.config)
        )
        style = _style_from_config(self.config, width, height)
        encode_threads = _encode_thread_count(self.config)
        logger.info(
            "MoviePy 合成参数: profile=%s 画幅=%sx%s fps=%s 进度条分段/秒=%.2f 场景转场=%s preset=%s threads=%s",
            getattr(self.config, "render_profile", "normal"),
            width,
            height,
            fps,
            seg_per_sec,
            eff_transition,
            encode_preset,
            encode_threads,
        )

        chapters = [
            ChapterMeta(
                scene_id=a.scene.id,
                title=a.scene.title,
                duration=max(a.tts.duration, 0.5),
            )
            for a in artifacts
        ]
        total_duration = sum(c.duration for c in chapters)

        scene_clips: list[Any] = []
        try:
            for idx, art in enumerate(artifacts):
                clip = self._build_scene_clip(
                    idx=idx,
                    art=art,
                    chapters=chapters,
                    style=style,
                    progress_segments_per_second=seg_per_sec,
                )
                scene_clips.append(clip)

            transition = eff_transition
            if transition == "fade" and transition_d > 0 and len(scene_clips) > 1:
                faded = [scene_clips[0]]
                for c in scene_clips[1:]:
                    faded.append(_crossfadein(c, transition_d))
                final = concatenate_videoclips(
                    faded, method="compose", padding=-transition_d
                )
            else:
                final = concatenate_videoclips(scene_clips, method="compose")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            encode_logger: str | None = (
                "bar" if getattr(self.config, "moviepy_encode_progress", True) else None
            )
            vcodec = effective_video_codec(self.config)
            logger.info(f"MoviePy 导出视频编码器: {vcodec}（encode_device={getattr(self.config, 'encode_device', 'cpu')}）")
            final.write_videofile(
                str(output_path),
                fps=fps,
                codec=vcodec,
                audio_codec=self.config.audio_codec,
                preset=encode_preset,
                threads=encode_threads,
                logger=encode_logger,
            )
        except VideoComposeError:
            raise
        except Exception as e:
            raise VideoComposeError(f"MoviePy 合成失败: {e}") from e
        finally:
            import contextlib

            for c in scene_clips:
                with contextlib.suppress(Exception):
                    c.close()

        logger.info(f"视频已写入: {output_path}")
        return VideoArtifact(
            title=title,
            video_path=output_path,
            duration=total_duration,
            scenes=artifacts,
        )

    def _build_scene_clip(
        self,
        *,
        idx: int,
        art: SceneArtifact,
        chapters: list[ChapterMeta],
        style: OverlayStyle,
        progress_segments_per_second: float,
    ) -> Any:
        width, height = style.width, style.height
        duration = chapters[idx].duration

        try:
            audio = AudioFileClip(str(art.tts.audio_path))
        except Exception as e:
            raise VideoComposeError(
                f"无法读取音频 {art.tts.audio_path}: {e}"
            ) from e

        audio = _subclip(audio, 0, min(audio.duration, duration))

        bg_image = composite_image_on_canvas(
            (width, height),
            style.background_color,
            art.rendered.image_path,
            padding_top=getattr(self.config, "image_padding_top", 160),
            padding_bottom=getattr(self.config, "image_padding_bottom", 240),
        )
        bg_array = np.array(bg_image)
        base = ImageClip(bg_array, duration=duration)

        layers: list[Any] = [base]

        if style.progress_bar_enabled:
            try:
                bar_clip = self._build_progress_clip(
                    chapters=chapters,
                    current_index=idx,
                    duration=duration,
                    style=style,
                    segments_per_second=progress_segments_per_second,
                )
                layers.append(bar_clip)
            except Exception as e:
                logger.warning(f"进度条层创建失败，跳过: {e}")

        # Scene.reveal_points：按时间逐步显示左上角要点面板
        if art.scene.reveal_points:
            try:
                reveal_clips = self._build_reveal_clips(
                    art.scene, duration=duration, style=style
                )
                layers.extend(reveal_clips)
            except Exception as e:
                logger.warning(f"reveal points 层创建失败，跳过: {e}")

        if self.config.subtitle_enabled and art.tts.cues:
            subtitle_clips = self._build_subtitle_clips(art, style, duration)
            layers.extend(subtitle_clips)

        composite = _set_duration(
            CompositeVideoClip(layers, size=(width, height)),
            duration,
        )
        composite = _set_audio(composite, audio)
        return composite

    def _build_progress_clip(
        self,
        *,
        chapters: list[ChapterMeta],
        current_index: int,
        duration: float,
        style: OverlayStyle,
        segments_per_second: float,
    ) -> Any:
        """把章节进度条切成若干段 ``ImageClip``，叠成一个 ``CompositeVideoClip``。

        分段的中位时间作为该段的"当前进度"，segments_per_second 控制平滑度。
        """
        segments_per_second = max(0.25, float(segments_per_second))
        n_segments = max(2, int(round(duration * segments_per_second)))
        seg_dur = duration / n_segments
        clips: list[Any] = []
        bar_h = 0
        for i in range(n_segments):
            t_mid = (i + 0.5) * seg_dur
            progress = t_mid / max(duration, 1e-3)
            bar = render_progress_bar(style, chapters, current_index, progress)
            arr = to_numpy(bar)
            seg = ImageClip(arr, duration=seg_dur, transparent=True)
            seg = _set_position(seg, ("center", 0))
            seg = _set_start(seg, i * seg_dur)
            clips.append(seg)
            bar_h = bar.size[1]
        composite = _set_duration(
            CompositeVideoClip(clips, size=(style.width, bar_h)),
            duration,
        )
        composite = _set_position(composite, ("center", 0))
        return composite

    def _build_subtitle_clips(
        self,
        art: SceneArtifact,
        style: OverlayStyle,
        duration: float,
    ) -> list[Any]:
        clips: list[Any] = []
        bottom_margin = max(60, getattr(self.config, "image_padding_bottom", 240) // 4)
        for cue in art.tts.cues:
            if cue.start >= duration:
                continue
            end = min(cue.end, duration)
            d = max(0.05, end - cue.start)
            sub_img = render_subtitle(style, cue.text)
            if sub_img is None:
                continue
            arr = to_numpy(sub_img)
            sub_clip = ImageClip(arr, duration=d, transparent=True)
            y = style.height - sub_img.size[1] - bottom_margin
            sub_clip = _set_position(sub_clip, ("center", y))
            sub_clip = _set_start(sub_clip, cue.start)
            clips.append(sub_clip)
        return clips

    def _build_reveal_clips(
        self,
        scene: Scene,
        *,
        duration: float,
        style: OverlayStyle,
    ) -> list[Any]:
        """按 ``scene.reveal_points`` 的顺序，分时间窗叠加左上角要点面板。"""
        points = [p.strip() for p in scene.reveal_points if p.strip()]
        if not points:
            return []

        panel_w = min(640, max(320, style.width // 3))
        panel_h = min(420, max(200, style.height // 3))
        margin_x = 40
        margin_y = max(140, getattr(self.config, "image_padding_top", 160) - 20)

        step = duration / len(points)
        clips: list[Any] = []
        for idx in range(len(points)):
            start = idx * step
            end = duration if idx == len(points) - 1 else (idx + 1) * step
            text = f"{scene.title}\n" + "\n".join(
                f"- {line}" for line in points[: idx + 1]
            )
            panel = _render_reveal_panel(
                text,
                width=panel_w,
                height=panel_h,
                font=style.font,
                title_font_size=max(28, style.subtitle_font_size),
                body_font_size=max(22, int(style.subtitle_font_size * 0.7)),
            )
            arr = np.array(panel)
            clip = ImageClip(arr, duration=end - start, transparent=True)
            clip = _set_position(clip, (margin_x, margin_y))
            clip = _set_start(clip, start)
            clip = _set_end(clip, end)
            clips.append(clip)
        return clips


def _render_reveal_panel(
    text: str,
    *,
    width: int,
    height: int,
    font: str,
    title_font_size: int,
    body_font_size: int,
) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 165))
    draw = ImageDraw.Draw(image)
    title_font = _overlay_load_font(font, title_font_size)
    body_font = _overlay_load_font(font, body_font_size)
    lines = text.split("\n")
    y = 18
    for idx, line in enumerate(lines):
        f = title_font if idx == 0 else body_font
        draw.text((20, y), line, fill=(255, 255, 255, 255), font=f)
        y += title_font_size + 8 if idx == 0 else body_font_size + 6
        if y > height - body_font_size:
            break
    return image
