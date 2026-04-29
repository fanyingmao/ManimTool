"""Edge-TTS 客户端（骨架）。

实现要点（TODO cursor）：
    - 使用 `edge_tts.Communicate(text, voice, rate, volume, pitch)`
    - 通过 `await communicate.save(audio_path)` 写出 mp3
    - 同时调用 `communicate.stream()` 抓取 WordBoundary 事件，写出 SRT 字幕
    - 用 `imageio_ffmpeg` 或 `mutagen` 探测时长（不要再读一遍音频）
    - 同步入口包装：`asyncio.run(_async_synthesize(...))`
"""

from __future__ import annotations

from pathlib import Path

from manimtool.errors import TTSError
from manimtool.schemas import Scene, TTSResult
from manimtool.tts.base import BaseTTS


class EdgeTTS(BaseTTS):
    def synthesize(self, scene: Scene, output_dir: Path) -> TTSResult:
        raise TTSError("EdgeTTS.synthesize 尚未实现，请由 cursor 完成")
