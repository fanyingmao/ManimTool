"""TTS 工厂。"""

from __future__ import annotations

from manimtool.errors import ConfigError
from manimtool.schemas import TTSConfig
from manimtool.tts.base import BaseTTS


def get_tts(config: TTSConfig) -> BaseTTS:
    if config.provider == "edge":
        from manimtool.tts.edge_tts_client import EdgeTTS

        return EdgeTTS(config)
    raise ConfigError(f"未知 TTS provider: {config.provider}")
