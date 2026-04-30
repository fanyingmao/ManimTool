"""基于 MoviePy 的合成器（骨架）。

实现要点（TODO cursor）：
    - 每个 scene 用 ImageClip 配合 AudioFileClip，duration = TTSResult.duration
    - 居中排版图片到目标分辨率（保持比例 + 透明背景叠加）
    - 顶部叠加 scene.title 文字（TextClip）
    - 底部叠加字幕（如启用）
    - 场景间 `crossfadein` 实现 fade 转场
    - 最终 `concatenate_videoclips(method="compose")` 输出 mp4
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

from manimtool.errors import VideoComposeError
from manimtool.schemas import SceneArtifact, VideoArtifact
from manimtool.video.base import BaseComposer


class MoviePyComposer(BaseComposer):
    def compose(
        self,
        title: str,
        artifacts: list[SceneArtifact],
        output_path: Path,
    ) -> VideoArtifact:
        if not artifacts:
            raise VideoComposeError("没有可合成的场景")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        width, height = self.config.resolution
        clips: list[CompositeVideoClip] = []
        opened_audios: list[AudioFileClip] = []
        overlay_clips: list[ImageClip] = []

        try:
            for artifact in artifacts:
                duration = max(artifact.tts.duration, 0.1)
                bg = ColorClip(size=(width, height), color=(14, 17, 23)).with_duration(duration)
                img = (
                    ImageClip(str(artifact.rendered.image_path))
                    .with_duration(duration)
                    .resized(height=height)
                    .with_position("center")
                )
                scene_overlays = _build_scene_overlays(
                    artifact.scene.title,
                    artifact.scene.reveal_points,
                    width=width,
                    height=height,
                    duration=duration,
                )
                overlay_clips.extend(scene_overlays)
                base = CompositeVideoClip([bg, img, *scene_overlays], size=(width, height))
                audio = AudioFileClip(str(artifact.tts.audio_path)).with_duration(duration)
                opened_audios.append(audio)
                clip = base.with_audio(audio)

                clips.append(clip)

            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile(
                str(output_path),
                fps=self.config.fps,
                codec=self.config.codec,
                audio_codec=self.config.audio_codec,
                logger=None,
            )
            total_duration = sum(a.tts.duration for a in artifacts)
            return VideoArtifact(
                title=title,
                video_path=output_path,
                duration=total_duration,
                scenes=artifacts,
            )
        except Exception as exc:
            raise VideoComposeError(f"MoviePy 合成失败: {exc}") from exc
        finally:
            for clip in clips:
                clip.close()
            for audio in opened_audios:
                audio.close()
            for overlay in overlay_clips:
                overlay.close()


def _build_scene_overlays(
    title: str,
    reveal_points: list[str],
    *,
    width: int,
    height: int,
    duration: float,
) -> list[ImageClip]:
    overlays: list[ImageClip] = []
    points = [p.strip() for p in reveal_points if p.strip()]
    if not points:
        text = f"{title}\n- 继续讲解当前要点"
        overlays.append(
            _text_clip(text, panel_width=min(900, width - 80), panel_height=min(360, height - 120))
            .with_duration(duration)
            .with_position((40, 40))
        )
        return overlays

    step = duration / len(points)
    for idx in range(len(points)):
        start = idx * step
        end = duration if idx == len(points) - 1 else (idx + 1) * step
        text = f"{title}\n" + "\n".join(f"- {line}" for line in points[: idx + 1])
        overlays.append(
            _text_clip(text, panel_width=min(980, width - 80), panel_height=min(420, height - 120))
            .with_start(start)
            .with_end(end)
            .with_position((40, 40))
        )
    return overlays


def _text_clip(text: str, *, panel_width: int, panel_height: int) -> ImageClip:
    image = Image.new("RGBA", (panel_width, panel_height), (0, 0, 0, 165))
    draw = ImageDraw.Draw(image)
    title_font = _load_font(42)
    body_font = _load_font(32)
    lines = text.split("\n")
    y = 18
    for idx, line in enumerate(lines):
        font = title_font if idx == 0 else body_font
        draw.text((20, y), line, fill=(255, 255, 255, 255), font=font)
        y += 50 if idx == 0 else 40
        if y > panel_height - 40:
            break
    return ImageClip(np.array(image))


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("PingFang.ttc", "Arial Unicode.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
