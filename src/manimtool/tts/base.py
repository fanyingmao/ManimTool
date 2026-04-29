"""TTS 抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from manimtool.schemas import Scene, TTSConfig, TTSResult


class BaseTTS(ABC):
    def __init__(self, config: TTSConfig) -> None:
        self.config = config

    @abstractmethod
    def synthesize(self, scene: Scene, output_dir: Path) -> TTSResult:
        """把 scene.narration 合成为音频文件，返回包含时长的 `TTSResult`。"""
        raise NotImplementedError
