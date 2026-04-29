"""视频合成模块：图片 + 音频 + 字幕 → mp4。"""

from manimtool.video.base import BaseComposer
from manimtool.video.factory import get_composer

__all__ = ["BaseComposer", "get_composer"]
