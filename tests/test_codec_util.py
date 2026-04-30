"""effective_video_codec 解析测试。"""

from __future__ import annotations

import sys

from manimtool.schemas import VideoConfig
from manimtool.video.codec_util import effective_video_codec


def test_encode_device_cpu_uses_config_codec() -> None:
    cfg = VideoConfig(codec="libx264", encode_device="cpu")
    assert effective_video_codec(cfg) == "libx264"


def test_encode_device_nvidia() -> None:
    cfg = VideoConfig(encode_device="nvidia")
    assert effective_video_codec(cfg) == "h264_nvenc"


def test_encode_device_apple_on_darwin() -> None:
    cfg = VideoConfig(encode_device="apple")
    if sys.platform == "darwin":
        assert effective_video_codec(cfg) == "h264_videotoolbox"
    else:
        assert effective_video_codec(cfg) == "libx264"
