"""渲染器工厂。"""

from __future__ import annotations

from manimtool.errors import ConfigError
from manimtool.render.base import BaseRenderer
from manimtool.schemas import RenderConfig


def get_renderer(config: RenderConfig) -> BaseRenderer:
    if config.engine == "mermaid":
        from manimtool.render.mermaid import MermaidRenderer

        return MermaidRenderer(config)
    raise ConfigError(f"未知 render engine: {config.engine}")
