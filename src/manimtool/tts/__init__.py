"""TTS 模块：旁白文本 → 音频文件 + 时长信息。"""

from manimtool.tts.base import BaseTTS
from manimtool.tts.factory import get_tts

__all__ = ["BaseTTS", "get_tts"]
