"""LLM 工厂：根据配置实例化具体 provider。"""

from __future__ import annotations

from manimtool.errors import ConfigError
from manimtool.llm.base import BaseLLM
from manimtool.schemas import LLMConfig


def get_llm(config: LLMConfig) -> BaseLLM:
    if config.provider == "openai":
        from manimtool.llm.openai_client import OpenAILLM

        return OpenAILLM(config)
    if config.provider == "anthropic":
        from manimtool.llm.anthropic_client import AnthropicLLM

        return AnthropicLLM(config)
    raise ConfigError(f"未知 LLM provider: {config.provider}")
