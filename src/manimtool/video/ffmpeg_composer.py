"""基于 FFmpeg 命令行的合成器（骨架，可选高性能后端）。

实现要点（TODO cursor）：
    - 为每个 scene 生成单段 mp4：`ffmpeg -loop 1 -i img.png -i audio.mp3 -shortest -t DUR ...`
    - 用 concat demuxer 合并所有片段
    - 通过 -vf drawtext 叠加标题/字幕（或外挂 SRT）
    - 必要时启用 -hwaccel 加速
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from manimtool.errors import VideoComposeError
from manimtool.schemas import SceneArtifact, VideoArtifact
from manimtool.video.base import BaseComposer


class FFmpegComposer(BaseComposer):
    def compose(
        self,
        title: str,
        artifacts: list[SceneArtifact],
        output_path: Path,
    ) -> VideoArtifact:
        if not artifacts:
            raise VideoComposeError("没有可合成的场景")
        if shutil.which("ffmpeg") is None:
            raise VideoComposeError("未找到 ffmpeg，可改用 --backend moviepy")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = output_path.parent / ".segments"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        segment_paths: list[Path] = []
        width, height = self.config.resolution
        drawtext_available = _ffmpeg_has_filter("drawtext")

        try:
            for idx, artifact in enumerate(artifacts):
                seg_path = tmp_dir / f"{idx:03d}.mp4"
                reveal_path = tmp_dir / f"{idx:03d}_reveal.srt"
                duration = max(artifact.tts.duration, 0.1)
                fade_duration = min(self.config.scene_fade_duration, duration / 3)
                _write_reveal_srt(
                    reveal_path=reveal_path,
                    title=artifact.scene.title,
                    reveal_points=artifact.scene.reveal_points,
                    duration=duration,
                )
                vf = (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
                )
                if self.config.motion_enabled:
                    vf = (
                        f"{vf},zoompan="
                        f"z='min(zoom+{self.config.motion_zoom_speed},1.12)':"
                        "x='iw/2-(iw/zoom/2)':"
                        "y='ih/2-(ih/zoom/2)':"
                        f"d=1:s={width}x{height}:fps={self.config.fps}"
                    )
                if fade_duration > 0:
                    fade_out_start = max(duration - fade_duration, 0)
                    vf = (
                        f"{vf},fade=t=in:st=0:d={fade_duration:.3f},"
                        f"fade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f}"
                    )
                if self.config.title_enabled and drawtext_available:
                    scene_title = _ffmpeg_escape_text(artifact.scene.title)
                    vf = (
                        f"{vf},drawtext=text='{scene_title}':"
                        "fontcolor=white:fontsize=52:"
                        "x=(w-text_w)/2:y=60:"
                        "alpha='if(lt(t,0.8),t/0.8,1)'"
                    )
                elif self.config.title_enabled:
                    # drawtext 不可用时，使用字幕层实现标题和要点渐进展示。
                    reveal_subtitle_path = _ffmpeg_escape_path(reveal_path.resolve())
                    vf = f"{vf},subtitles={reveal_subtitle_path}"
                if self.config.subtitle_enabled and artifact.tts.subtitle_path and artifact.tts.subtitle_path.exists():
                    subtitle_path = _ffmpeg_escape_path(artifact.tts.subtitle_path.resolve())
                    vf = f"{vf},subtitles={subtitle_path}"
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(artifact.rendered.image_path),
                    "-i",
                    str(artifact.tts.audio_path),
                    "-t",
                    f"{duration:.3f}",
                    "-vf",
                    vf,
                    "-r",
                    str(self.config.fps),
                    "-c:v",
                    self.config.codec,
                    "-c:a",
                    self.config.audio_codec,
                    "-shortest",
                    str(seg_path),
                ]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                segment_paths.append(seg_path)

            concat_file = tmp_dir / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{p.resolve()}'" for p in segment_paths),
                encoding="utf-8",
            )
            merge_cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ]
            subprocess.run(merge_cmd, check=True, capture_output=True, text=True)
            return VideoArtifact(
                title=title,
                video_path=output_path,
                duration=sum(a.tts.duration for a in artifacts),
                scenes=artifacts,
            )
        except subprocess.CalledProcessError as exc:
            raise VideoComposeError(f"FFmpeg 合成失败: {exc.stderr}") from exc
        except Exception as exc:
            raise VideoComposeError(f"FFmpeg 合成失败: {exc}") from exc


def _ffmpeg_escape_path(path: Path) -> str:
    # ffmpeg subtitles filter 中 ':' 和单引号需要转义。
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _ffmpeg_escape_text(text: str) -> str:
    # drawtext 字符串最常见转义：反斜杠、单引号、冒号、百分号。
    return (
        text.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
        .replace("%", r"\%")
    )


def _ffmpeg_has_filter(filter_name: str) -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            check=True,
            capture_output=True,
            text=True,
        )
        return filter_name in result.stdout
    except Exception:
        return False


def _write_reveal_srt(
    reveal_path: Path,
    title: str,
    reveal_points: list[str],
    duration: float,
) -> None:
    cues: list[tuple[float, float, str]] = []
    safe_title = f"【{title}】"
    points = [p.strip() for p in reveal_points if p.strip()]
    if not points:
        cues.append((0.0, duration, safe_title))
    else:
        step = duration / len(points)
        for idx, _ in enumerate(points):
            start = idx * step
            end = duration if idx == len(points) - 1 else (idx + 1) * step
            shown = "\n".join(f"- {line}" for line in points[: idx + 1])
            cues.append((start, end, f"{safe_title}\n{shown}"))

    lines: list[str] = []
    for idx, (start, end, text) in enumerate(cues, start=1):
        lines.extend(
            [
                str(idx),
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
                text,
                "",
            ]
        )
    reveal_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _format_srt_time(seconds: float) -> str:
    total_ms = max(int(seconds * 1000), 0)
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
