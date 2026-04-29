"""视频合成器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from manimtool.schemas import SceneArtifact, VideoArtifact, VideoConfig


class BaseComposer(ABC):
    def __init__(self, config: VideoConfig) -> None:
        self.config = config

    @abstractmethod
    def compose(
        self,
        title: str,
        artifacts: list[SceneArtifact],
        output_path: Path,
    ) -> VideoArtifact:
        """把所有 SceneArtifact 拼成一个 mp4 文件。"""
        raise NotImplementedError
