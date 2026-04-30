"""基于 FFmpeg 命令行的视频合成器。

实现要点：
    - 每个 scene 单独生成 mp4 段：背景画布 + Mermaid 图 + 顶部进度条
      + 字幕（SRT 烧录）+ 可选场景淡入淡出 / Ken Burns 缩放 / 要点 reveal
    - 用 concat demuxer 合并所有片段
    - 适合服务器/无 GUI 环境，无需 MoviePy
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from manimtool.errors import VideoComposeError
from manimtool.logging import logger
from manimtool.schemas import SceneArtifact, SubtitleCue, VideoArtifact
from manimtool.video.base import BaseComposer
from manimtool.video.codec_util import effective_video_codec
from manimtool.video.overlays import (
    ChapterMeta,
    OverlayStyle,
    composite_image_on_canvas,
    hex_to_rgb,
    render_progress_bar_layout,
)


def _resolve_ffmpeg() -> str:
    bin_path = shutil.which("ffmpeg")
    if bin_path:
        return bin_path
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return str(get_ffmpeg_exe())
    except Exception as e:
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


def _write_reveal_srt(
    path: Path,
    title: str,
    reveal_points: list[str],
    duration: float,
) -> None:
    """根据 ``Scene.reveal_points`` 写一份"标题 + 渐进显示要点"的 SRT。"""
    points = [p.strip() for p in reveal_points if p.strip()]
    safe_title = f"【{title}】"
    cues: list[tuple[float, float, str]] = []
    if not points:
        cues.append((0.0, duration, safe_title))
    else:
        step = duration / len(points)
        for idx in range(len(points)):
            start = idx * step
            end = duration if idx == len(points) - 1 else (idx + 1) * step
            shown = "\n".join(f"- {line}" for line in points[: idx + 1])
            cues.append((start, end, f"{safe_title}\n{shown}"))

    lines: list[str] = []
    for i, (start, end, text) in enumerate(cues, start=1):
        lines.extend(
            [
                str(i),
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                text,
                "",
            ]
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _ffmpeg_escape_subtitle_path(path: Path) -> str:
    """ffmpeg subtitles filter 中 ':' 与单引号需要转义。"""
    s = path.as_posix()
    return s.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


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

        srt_path: Path | None = None
        if self.config.subtitle_enabled and art.tts.cues:
            srt_path = work / f"subs_{idx:03d}.srt"
            _write_srt(art.tts.cues, srt_path)

        reveal_srt_path: Path | None = None
        if art.scene.reveal_points:
            reveal_srt_path = work / f"reveal_{idx:03d}.srt"
            _write_reveal_srt(
                reveal_srt_path,
                title=art.scene.title,
                reveal_points=art.scene.reveal_points,
                duration=duration,
            )

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

        bar_path: Path | None = None
        bar_box: tuple[int, int, int, int] | None = None
        if style.progress_bar_enabled:
            bar_img, bar_box = render_progress_bar_layout(style, chapters, idx)
            bar_path = work / f"bar_{idx:03d}.png"
            bar_img.save(bar_path)
            inputs.extend(["-loop", "1", "-i", str(bar_path)])

        filter_parts: list[str] = []
        last_label = "[0:v]"

        # 可选：Ken Burns 轻微缩放，避免画面完全静止
        if getattr(self.config, "motion_enabled", False):
            zoom_speed = max(0.0, float(getattr(self.config, "motion_zoom_speed", 0.0006)))
            if zoom_speed > 0:
                total_frames = max(1, int(duration * fps))
                filter_parts.append(
                    f"{last_label}zoompan="
                    f"z='min(zoom+{zoom_speed:.6f},1.12)':"
                    "x='iw/2-(iw/zoom/2)':"
                    "y='ih/2-(ih/zoom/2)':"
                    f"d={total_frames}:s={width}x{height}:fps={fps}[zoom]"
                )
                last_label = "[zoom]"

        if bar_path is not None and bar_box is not None:
            x0, y0, x1, h = bar_box
            seg_x0, seg_x1 = self._segment_x_range(chapters, idx, x0, x1)
            seg_w = seg_x1 - seg_x0
            color_hex = "{:02x}{:02x}{:02x}".format(*hex_to_rgb(style.progress_bar_color))
            filter_parts.append(
                f"{last_label}[2:v]overlay=x=0:y=0[bg1]"
            )
            last_label = "[bg1]"
            fill_w_expr = f"max(0\\,min({seg_w}\\,t/{duration:.6f}*{seg_w}))"
            filter_parts.append(
                f"{last_label}drawbox=x={seg_x0}:y={y0}:"
                f"w='{fill_w_expr}':h={h}:color=0x{color_hex}@1.0:t=fill[bg2]"
            )
            last_label = "[bg2]"

        # 场景淡入淡出
        fade_d = max(0.0, float(getattr(self.config, "scene_fade_duration", 0.0)))
        fade_d = min(fade_d, duration / 3) if duration > 0 else 0
        if fade_d > 0:
            fade_out_start = max(duration - fade_d, 0)
            filter_parts.append(
                f"{last_label}fade=t=in:st=0:d={fade_d:.3f},"
                f"fade=t=out:st={fade_out_start:.3f}:d={fade_d:.3f}[faded]"
            )
            last_label = "[faded]"

        # reveal_points：在画面上方区域显示渐进要点（独立 SRT，置顶对齐）
        if reveal_srt_path is not None:
            reveal_str = _ffmpeg_escape_subtitle_path(reveal_srt_path)
            reveal_font = max(16, int(self.config.subtitle_font_size * 0.55 * 288 / max(height, 1)))
            reveal_filter = (
                f"subtitles='{reveal_str}':"
                f"original_size={width}x{height}:"
                f"force_style='Fontsize={reveal_font},Alignment=7,"
                "PrimaryColour=&H00FFFFFF&,OutlineColour=&HC8000000&,BackColour=&HC8000000&,"
                "BorderStyle=3,Outline=4,Shadow=0,MarginL=40,MarginV=160,Spacing=1'"
            )
            filter_parts.append(f"{last_label}{reveal_filter}[withrev]")
            last_label = "[withrev]"

        if srt_path:
            srt_str = _ffmpeg_escape_subtitle_path(srt_path)
            # ASS Fontsize 单位是 PlayResY（默认 288）下的像素；目标视频高度 1080
            # 时，等价像素 ≈ Fontsize * height / 288。
            target_px = max(28, int(self.config.subtitle_font_size * 0.65))
            font_size = max(12, int(target_px * 288 / max(height, 1)))
            target_margin_px = max(50, self.config.image_padding_bottom // 3)
            margin_v = max(20, int(target_margin_px * 288 / max(height, 1)))
            sub_filter = (
                f"subtitles='{srt_str}':"
                f"original_size={width}x{height}:"
                f"force_style='Fontsize={font_size},Alignment=2,"
                "PrimaryColour=&H00FFFFFF&,OutlineColour=&HC8000000&,BackColour=&HC8000000&,"
                f"BorderStyle=3,Outline=4,Shadow=0,MarginV={margin_v},Spacing=1'"
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
                effective_video_codec(self.config),
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                self.config.audio_codec,
                "-preset",
                "veryfast",
                "-shortest",
                "-t",
                f"{duration:.3f}",
                str(out_seg),
            ]
        )
        logger.debug(f"ffmpeg scene[{idx}]: {' '.join(cmd)}")
        self._run(cmd)
        return out_seg

    @staticmethod
    def _segment_x_range(
        chapters: list[ChapterMeta], current_index: int, x0: int, x1: int
    ) -> tuple[int, int]:
        durations = [max(c.duration, 0.001) for c in chapters]
        total = sum(durations)
        cum = 0.0
        for i, d in enumerate(durations):
            frac = d / total
            seg_x0 = x0 + cum * (x1 - x0)
            seg_x1 = x0 + (cum + frac) * (x1 - x0)
            if i == current_index:
                return int(round(seg_x0)), int(round(seg_x1))
            cum += frac
        return x0, x1

    def _run(self, cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise VideoComposeError(
                f"ffmpeg 调用失败: {e.stderr[:1500] if e.stderr else e}"
            ) from e
