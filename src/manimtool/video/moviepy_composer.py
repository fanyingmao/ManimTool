"""基于 MoviePy 的合成器（骨架）。

实现要点（TODO cursor）：
    - 每个 scene 用 ImageClip 配合 AudioFileClip，duration = TTSResult.duration
    - 居中排版图片到目标分辨率（保持比例 + 透明背景叠加）
    - 顶部叠加 scene.title 文字（TextClip）
    - 底部叠加字幕（如启用）
    - 场景间 `crossfadein` 实现 fade 转场
    - 最终 `concatenate_videoclips(method="compose")` 输出 mp4
"""

from __future__ import annotations

from pathlib import Path

from manimtool.errors import VideoComposeError
from manimtool.schemas import SceneArtifact, VideoArtifact
from manimtool.video.base import BaseComposer


class MoviePyComposer(BaseComposer):
    def compose(
        self,
        title: str,
        artifacts: list[SceneArtifact],
        output_path: Path,
    ) -> VideoArtifact:
        raise VideoComposeError("MoviePyComposer.compose 尚未实现，请由 cursor 完成")
