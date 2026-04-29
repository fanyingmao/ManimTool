"""基于 FFmpeg 命令行的合成器（骨架，可选高性能后端）。

实现要点（TODO cursor）：
    - 为每个 scene 生成单段 mp4：`ffmpeg -loop 1 -i img.png -i audio.mp3 -shortest -t DUR ...`
    - 用 concat demuxer 合并所有片段
    - 通过 -vf drawtext 叠加标题/字幕（或外挂 SRT）
    - 必要时启用 -hwaccel 加速
"""

from __future__ import annotations

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
        raise VideoComposeError("FFmpegComposer.compose 尚未实现，请由 cursor 完成")
