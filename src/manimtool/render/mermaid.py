"""Mermaid 渲染器（骨架）。

实现要点（TODO cursor）：
    - 把 `scene.mermaid` 写入 `<output_dir>/<scene_id>.mmd`
    - 调用 `mmdc -i input.mmd -o output.png -w W -H H -t THEME -b BG -s SCALE`
    - 校验输出文件存在且非空
    - 失败时抛 `RenderError`，附带 stderr
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from manimtool.errors import RenderError
from manimtool.logging import logger
from manimtool.render.base import BaseRenderer
from manimtool.schemas import RenderedScene, Scene


class MermaidRenderer(BaseRenderer):
    def render(self, scene: Scene, output_dir: Path) -> RenderedScene:
        cli = self.config.mermaid.cli
        if shutil.which(cli) is None:
            raise RenderError(
                f"未找到 mermaid-cli ({cli})。请先安装：npm i -g @mermaid-js/mermaid-cli"
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        mmd_path = output_dir / f"{scene.id}.mmd"
        png_path = output_dir / f"{scene.id}.png"
        mmd_path.write_text(scene.mermaid, encoding="utf-8")

        cmd = [
            cli,
            "-i", str(mmd_path),
            "-o", str(png_path),
            "-t", self.config.mermaid.theme,
            "-b", self.config.mermaid.background,
            "-w", str(self.config.mermaid.width),
            "-H", str(self.config.mermaid.height),
            "-s", str(self.config.mermaid.scale),
        ]
        logger.debug(f"mmdc 命令: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RenderError(f"mermaid 渲染失败: {e.stderr}") from e

        if not png_path.exists() or png_path.stat().st_size == 0:
            raise RenderError(f"渲染产物缺失或为空: {png_path}")

        return RenderedScene(
            scene_id=scene.id,
            image_path=png_path,
            width=self.config.mermaid.width,
            height=self.config.mermaid.height,
        )
