"""Edge-TTS 客户端实现。

将 ``scene.narration`` 合成为 mp3 音频，同时利用 ``edge-tts`` 的
``WordBoundary`` 事件构造逐字字幕，落盘为 SRT，并返回精确时长。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from manimtool.errors import TTSError
from manimtool.logging import logger
from manimtool.schemas import Scene, SubtitleCue, TTSResult
from manimtool.tts.base import BaseTTS


def _format_srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3600 * 1000)
    minutes, millis = divmod(millis, 60 * 1000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_srt(cues: list[SubtitleCue], path: Path) -> None:
    lines: list[str] = []
    for idx, cue in enumerate(cues, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_srt_timestamp(cue.start)} --> {_format_srt_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _detect_audio_duration(path: Path) -> float:
    """优先用 mutagen，其次回退到 imageio_ffmpeg/ffprobe。"""
    try:
        from mutagen.mp3 import MP3

        info = MP3(str(path)).info
        return float(info.length)
    except Exception:
        pass

    try:
        import json
        import subprocess

        from imageio_ffmpeg import get_ffmpeg_exe

        ffprobe = get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
        out = subprocess.check_output(cmd, text=True)
        return float(json.loads(out)["format"]["duration"])
    except Exception as e:
        raise TTSError(f"无法检测音频时长: {path} ({e})") from e


def _chunk_narration(text: str, max_chars: int = 28) -> list[str]:
    """把整段旁白切成短句，便于字幕滚动显示。

    策略：
        1. 先按强标点（句号/问号等）切成"句"
        2. 句内若仍长，按软标点（中文逗号、顿号）切成"短语"
        3. 把过短的相邻短语合并到接近 ``max_chars``，避免出现单独 1-2 字的孤行
        4. 仍然超长的纯文本（无标点）按字符硬切，但容忍 ``max_chars * 1.5``
    """
    if not text.strip():
        return []
    hard_seps = "。！？!?；;\n"
    soft_seps = "，,、 "

    def _split(s: str, seps: str) -> list[str]:
        parts: list[str] = []
        buf = ""
        for ch in s:
            buf += ch
            if ch in seps and buf.strip():
                parts.append(buf.strip())
                buf = ""
        if buf.strip():
            parts.append(buf.strip())
        return parts

    sentences = _split(text, hard_seps)

    final: list[str] = []
    for sent in sentences:
        if len(sent) <= max_chars:
            final.append(sent)
            continue
        sub_phrases = _split(sent, soft_seps)
        merged: list[str] = []
        cur = ""
        for p in sub_phrases:
            if not cur:
                cur = p
            elif len(cur) + len(p) <= max_chars:
                cur = cur + p
            else:
                merged.append(cur)
                cur = p
        if cur:
            merged.append(cur)
        for m in merged:
            if len(m) <= int(max_chars * 1.5):
                final.append(m)
                continue
            buf = ""
            for ch in m:
                buf += ch
                if len(buf) >= max_chars:
                    final.append(buf)
                    buf = ""
            if buf:
                final.append(buf)
    return [c.strip() for c in final if c.strip()]


def _cues_from_word_boundaries(
    boundaries: list[tuple[float, float, str]],
    chunks: list[str],
) -> list[SubtitleCue]:
    """根据 WordBoundary 时间戳，把字符聚合成与 chunks 对齐的字幕条。

    boundaries: list of (offset_seconds, duration_seconds, text)
    """
    if not boundaries or not chunks:
        return []

    cues: list[SubtitleCue] = []
    bi = 0
    for chunk in chunks:
        target = "".join(chunk.split())
        if not target:
            continue
        start = boundaries[bi][0]
        consumed = ""
        end = start
        while bi < len(boundaries) and len(consumed) < len(target):
            off, dur, txt = boundaries[bi]
            consumed += "".join(txt.split())
            end = off + dur
            bi += 1
        cues.append(SubtitleCue(start=start, end=end, text=chunk))
    return cues


class EdgeTTS(BaseTTS):
    def synthesize(self, scene: Scene, output_dir: Path) -> TTSResult:
        try:
            return asyncio.run(self._async_synthesize(scene, output_dir))
        except TTSError:
            raise
        except Exception as e:
            raise TTSError(f"edge-tts 合成失败 (scene={scene.id}): {e}") from e

    async def _async_synthesize(self, scene: Scene, output_dir: Path) -> TTSResult:
        try:
            import edge_tts
        except ImportError as e:  # pragma: no cover - 依赖缺失
            raise TTSError("未安装 edge-tts，请 `pip install edge-tts`") from e

        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / f"{scene.id}.mp3"
        srt_path = output_dir / f"{scene.id}.srt"

        communicate = edge_tts.Communicate(
            text=scene.narration,
            voice=self.config.voice,
            rate=self.config.rate,
            volume=self.config.volume,
            pitch=self.config.pitch,
        )

        boundaries: list[tuple[float, float, str]] = []
        with audio_path.open("wb") as f:
            async for chunk in communicate.stream():
                ctype = chunk.get("type")
                if ctype == "audio":
                    f.write(chunk["data"])
                elif ctype == "WordBoundary":
                    offset = float(chunk.get("offset", 0)) / 1e7
                    duration = float(chunk.get("duration", 0)) / 1e7
                    text = str(chunk.get("text", ""))
                    boundaries.append((offset, duration, text))

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise TTSError(f"edge-tts 未输出音频: {audio_path}")

        duration = _detect_audio_duration(audio_path)

        chunks = _chunk_narration(scene.narration)
        cues = _cues_from_word_boundaries(boundaries, chunks)
        if not cues and chunks:
            per = duration / max(len(chunks), 1)
            cues = [
                SubtitleCue(start=i * per, end=(i + 1) * per, text=c)
                for i, c in enumerate(chunks)
            ]
        if cues:
            cues[-1] = SubtitleCue(start=cues[-1].start, end=duration, text=cues[-1].text)
            _write_srt(cues, srt_path)
        else:
            srt_path = None  # type: ignore[assignment]

        logger.debug(
            f"TTS 完成 scene={scene.id} duration={duration:.2f}s cues={len(cues)}"
        )
        return TTSResult(
            scene_id=scene.id,
            audio_path=audio_path,
            duration=duration,
            subtitle_path=srt_path,
            cues=cues,
        )
