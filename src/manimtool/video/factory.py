"""视频合成器工厂。当前默认使用 MoviePy 实现，FFmpeg 实现作为可选高性能后端。"""

from __future__ import annotations

from manimtool.schemas import VideoConfig
from manimtool.video.base import BaseComposer


def get_composer(config: VideoConfig, *, backend: str = "moviepy") -> BaseComposer:
    if backend == "moviepy":
        from manimtool.video.moviepy_composer import MoviePyComposer

        return MoviePyComposer(config)
    if backend == "ffmpeg":
        from manimtool.video.ffmpeg_composer import FFmpegComposer

        return FFmpegComposer(config)
    raise ValueError(f"未知 video backend: {backend}")
