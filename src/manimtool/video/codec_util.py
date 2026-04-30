"""根据 VideoConfig 解析最终 ffmpeg 视频编码器（CPU / 硬件加速）。"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from manimtool.logging import logger

if TYPE_CHECKING:
    from manimtool.schemas import VideoConfig


def effective_video_codec(config: VideoConfig) -> str:
    """返回写入 mp4 时使用的 ``-c:v`` / MoviePy ``codec`` 名称。"""
    dev = getattr(config, "encode_device", "cpu")
    if dev == "apple":
        if sys.platform == "darwin":
            return "h264_videotoolbox"
        logger.warning("encode_device=apple 仅在 macOS 生效，已使用配置中的 codec")
        return config.codec
    if dev == "nvidia":
        return "h264_nvenc"
    return config.codec
