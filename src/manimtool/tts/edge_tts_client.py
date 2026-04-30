"""Edge-TTS 客户端（骨架）。

实现要点（TODO cursor）：
    - 使用 `edge_tts.Communicate(text, voice, rate, volume, pitch)`
    - 通过 `await communicate.save(audio_path)` 写出 mp3
    - 同时调用 `communicate.stream()` 抓取 WordBoundary 事件，写出 SRT 字幕
    - 用 `imageio_ffmpeg` 或 `mutagen` 探测时长（不要再读一遍音频）
    - 同步入口包装：`asyncio.run(_async_synthesize(...))`
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import edge_tts

from manimtool.errors import TTSError
from manimtool.schemas import Scene, TTSResult
from manimtool.tts.base import BaseTTS


class EdgeTTS(BaseTTS):
    def synthesize(self, scene: Scene, output_dir: Path) -> TTSResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / f"{scene.id}.mp3"
        subtitle_path = output_dir / f"{scene.id}.srt"

        async def _async_synthesize() -> tuple[float, bool]:
            communicate = edge_tts.Communicate(
                text=scene.narration,
                voice=self.config.voice,
                rate=self.config.rate,
                volume=self.config.volume,
                pitch=self.config.pitch,
            )
            audio_data = bytearray()
            max_end_seconds = 0.0
            subtitle_lines: list[str] = []
            subtitle_index = 1

            async for chunk in communicate.stream():
                chunk_type = chunk.get("type")
                if chunk_type == "audio":
                    audio_data.extend(chunk["data"])
                elif chunk_type == "WordBoundary":
                    offset_sec = float(chunk["offset"]) / 10_000_000
                    duration_sec = float(chunk["duration"]) / 10_000_000
                    max_end_seconds = max(max_end_seconds, offset_sec + duration_sec)
                    start = _format_srt_time(offset_sec)
                    end = _format_srt_time(offset_sec + duration_sec)
                    text = str(chunk["text"]).strip()
                    if text:
                        subtitle_lines.extend([str(subtitle_index), f"{start} --> {end}", text, ""])
                        subtitle_index += 1

            if not audio_data:
                raise TTSError("Edge-TTS 未返回音频数据")

            audio_path.write_bytes(bytes(audio_data))
            subtitle_text = "\n".join(subtitle_lines).strip()
            has_subtitle = bool(subtitle_text.strip())
            if has_subtitle:
                subtitle_path.write_text(subtitle_text, encoding="utf-8")

            # 必须以真实音频时长为准，避免出现旁白未结束就切场。
            probed_duration = _probe_audio_duration(audio_path)
            if probed_duration is not None and probed_duration > 0:
                duration = probed_duration
            else:
                # ffprobe 不可用时，退回到 WordBoundary；再兜底文本估算。
                duration = (
                    max_end_seconds if max_end_seconds > 0 else max(1.0, len(scene.narration) * 0.12)
                )
            return duration, has_subtitle

        try:
            duration, has_subtitle = asyncio.run(_async_synthesize())
        except Exception as exc:
            if isinstance(exc, TTSError):
                raise
            raise TTSError(f"Edge-TTS 合成失败: {exc}") from exc

        return TTSResult(
            scene_id=scene.id,
            audio_path=audio_path,
            duration=duration,
            subtitle_path=subtitle_path if has_subtitle else None,
        )


def _format_srt_time(seconds: float) -> str:
    total_ms = max(int(seconds * 1000), 0)
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _probe_audio_duration(audio_path: Path) -> float | None:
    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin is None:
        return None
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        value = float(result.stdout.strip())
        return value if value > 0 else None
    except Exception:
        return None
