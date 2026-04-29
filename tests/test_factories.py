"""工厂函数烟雾测试：确保按 provider 正确分派。"""

from __future__ import annotations

import pytest

from manimtool.errors import ConfigError
from manimtool.llm import get_llm
from manimtool.render import get_renderer
from manimtool.schemas import LLMConfig, RenderConfig, TTSConfig
from manimtool.tts import get_tts


def test_llm_factory_dispatch() -> None:
    llm = get_llm(LLMConfig(provider="openai"))
    assert llm.__class__.__name__ == "OpenAILLM"


def test_tts_factory_dispatch() -> None:
    tts = get_tts(TTSConfig(provider="edge"))
    assert tts.__class__.__name__ == "EdgeTTS"


def test_render_factory_dispatch() -> None:
    r = get_renderer(RenderConfig(engine="mermaid"))
    assert r.__class__.__name__ == "MermaidRenderer"


def test_unknown_provider_raises() -> None:
    cfg = LLMConfig(provider="openai")
    cfg.provider = "unknown"  # type: ignore[assignment]
    with pytest.raises(ConfigError):
        get_llm(cfg)
