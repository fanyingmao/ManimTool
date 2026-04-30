"""基于 FFmpeg 命令行的视频合成器。

实现要点：
    - 每个 scene 单独生成 mp4 段：背景画布 + Mermaid 图 + 顶部进度条（多帧覆盖）+ 字幕（SRT 烧录）
    - 用 concat demuxer 合并所有片段
    - 适合服务器/无 GUI 环境，无需 MoviePy
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from manimtool.errors import VideoComposeError
from manimtool.logging import logger
from manimtool.schemas import SceneArtifact, SubtitleCue, VideoArtifact
from manimtool.video.base import BaseComposer
from manimtool.video.overlays import (
    ChapterMeta,
    OverlayStyle,
    composite_image_on_canvas,
    render_progress_bar,
)


def _resolve_ffmpeg() -> str:
    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        raise VideoComposeError("未找到 ffmpeg，请安装 ffmpeg 或 imageio-ffmpeg") from e


def _format_srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    h, millis = divmod(millis, 3600 * 1000)
    m, millis = divmod(millis, 60 * 1000)
    s, millis = divmod(millis, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def _write_srt(cues: list[SubtitleCue], path: Path) -> None:
    lines: list[str] = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(cue.start)} --> {_format_srt_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


class FFmpegComposer(BaseComposer):
    def compose(
        self,
        title: str,
        artifacts: list[SceneArtifact],
        output_path: Path,
    ) -> VideoArtifact:
        if not artifacts:
            raise VideoComposeError("artifacts 为空")

        ffmpeg = _resolve_ffmpeg()
        width, height = self.config.resolution
        fps = self.config.fps

        style = OverlayStyle(
            width=width,
            height=height,
            font=self.config.font,
            title_font_size=self.config.title_font_size,
            subtitle_font_size=self.config.subtitle_font_size,
            progress_bar_enabled=self.config.progress_bar_enabled,
            progress_bar_height=self.config.progress_bar_height,
            progress_bar_color=self.config.progress_bar_color,
            progress_bar_bg_color=self.config.progress_bar_bg_color,
            progress_bar_padding=self.config.progress_bar_padding,
            chapter_label_color=self.config.chapter_label_color,
            subtitle_box_color=self.config.subtitle_box_color,
            subtitle_box_opacity=self.config.subtitle_box_opacity,
            background_color=self.config.background_color,
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

        with tempfile.TemporaryDirectory(prefix="manimtool_ffmpeg_") as tmpdir:
            work = Path(tmpdir)
            seg_paths: list[Path] = []
            for idx, art in enumerate(artifacts):
                seg = self._render_scene(
                    ffmpeg=ffmpeg,
                    work=work,
                    idx=idx,
                    art=art,
                    chapters=chapters,
                    style=style,
                    fps=fps,
                )
                seg_paths.append(seg)

            concat_path = work / "concat.txt"
            concat_path.write_text(
                "\n".join(f"file '{p.as_posix()}'" for p in seg_paths) + "\n",
                encoding="utf-8",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                str(output_path),
            ]
            logger.debug(f"ffmpeg concat: {' '.join(cmd)}")
            self._run(cmd)

        return VideoArtifact(
            title=title,
            video_path=output_path,
            duration=total_duration,
            scenes=artifacts,
        )

    def _render_scene(
        self,
        *,
        ffmpeg: str,
        work: Path,
        idx: int,
        art: SceneArtifact,
        chapters: list[ChapterMeta],
        style: OverlayStyle,
        fps: int,
    ) -> Path:
        width, height = style.width, style.height
        duration = chapters[idx].duration

        bg_image = composite_image_on_canvas(
            (width, height),
            style.background_color,
            art.rendered.image_path,
            padding_top=self.config.image_padding_top,
            padding_bottom=self.config.image_padding_bottom,
        )
        bg_path = work / f"bg_{idx:03d}.png"
        bg_image.save(bg_path)

        bar_paths: list[tuple[float, Path]] = []
        if style.progress_bar_enabled:
            n_segments = max(2, int(round(duration * 4)))
            seg_dur = duration / n_segments
            for i in range(n_segments):
                t_mid = (i + 0.5) * seg_dur
                progress = t_mid / max(duration, 1e-3)
                bar = render_progress_bar(style, chapters, idx, progress)
                p = work / f"bar_{idx:03d}_{i:03d}.png"
                bar.save(p)
                bar_paths.append((i * seg_dur, p))

        srt_path: Path | None = None
        if self.config.subtitle_enabled and art.tts.cues:
            srt_path = work / f"subs_{idx:03d}.srt"
            _write_srt(art.tts.cues, srt_path)

        out_seg = work / f"scene_{idx:03d}.mp4"

        inputs: list[str] = [
            "-loop",
            "1",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(bg_path),
            "-i",
            str(art.tts.audio_path),
        ]
        for _, bp in bar_paths:
            inputs.extend(["-loop", "1", "-i", str(bp)])

        filter_parts: list[str] = []
        last_label = "[0:v]"
        for i, (start, _bp) in enumerate(bar_paths):
            in_label = f"[{2 + i}:v]"
            seg_dur = duration / len(bar_paths)
            end = start + seg_dur
            out_label = f"[v{i}]"
            filter_parts.append(
                f"{last_label}{in_label}overlay=x=(W-w)/2:y=0:"
                f"enable='between(t,{start:.3f},{end:.3f})'{out_label}"
            )
            last_label = out_label

        if srt_path:
            srt_str = srt_path.as_posix().replace(":", "\\:")
            sub_filter = (
                f"subtitles='{srt_str}':force_style="
                "'Fontsize=20,Alignment=2,PrimaryColour=&HFFFFFF&,OutlineColour=&H80000000&,"
                "BorderStyle=3,Outline=2,Shadow=0,MarginV=60'"
            )
            filter_parts.append(f"{last_label}{sub_filter}[vout]")
            last_label = "[vout]"

        filter_complex = ";".join(filter_parts) if filter_parts else None
        cmd = [ffmpeg, "-y", *inputs]
        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex, "-map", last_label])
        else:
            cmd.extend(["-map", "0:v"])
        cmd.extend(
            [
                "-map",
                "1:a",
                "-c:v",
                self.config.codec,
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                self.config.audio_codec,
                "-shortest",
                "-t",
                f"{duration:.3f}",
                str(out_seg),
            ]
        )
        logger.debug(f"ffmpeg scene[{idx}]: {' '.join(cmd)}")
        self._run(cmd)
        return out_seg

    def _run(self, cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise VideoComposeError(
                f"ffmpeg 调用失败: {e.stderr[:1500] if e.stderr else e}"
            ) from e


# 占位以保留与原导入兼容（未使用）
_ = (np, Image)
