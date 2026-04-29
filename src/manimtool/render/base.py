"""渲染器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from manimtool.schemas import RenderConfig, RenderedScene, Scene


class BaseRenderer(ABC):
    def __init__(self, config: RenderConfig) -> None:
        self.config = config

    @abstractmethod
    def render(self, scene: Scene, output_dir: Path) -> RenderedScene:
        """渲染单个 scene。返回 `RenderedScene`，失败时抛 `RenderError`。"""
        raise NotImplementedError
