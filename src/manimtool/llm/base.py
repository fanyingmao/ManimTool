"""LLM 客户端抽象基类。

约束：
    - 所有 provider 实现必须继承 `BaseLLM` 并实现 `generate_storyboard`。
    - 输出必须是合法的 `Storyboard` 实例（已通过 Pydantic 校验）。
    - 失败时抛出 `manimtool.errors.LLMError`，禁止吞异常。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from manimtool.schemas import LLMConfig, Storyboard

DEFAULT_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "prompts" / "system_zh.md"
)


class BaseLLM(ABC):
    """LLM 客户端基类。"""

    def __init__(self, config: LLMConfig, system_prompt: str | None = None) -> None:
        self.config = config
        self._system_prompt = system_prompt or self._load_default_prompt()

    @staticmethod
    def _load_default_prompt() -> str:
        if DEFAULT_SYSTEM_PROMPT_PATH.exists():
            return DEFAULT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return "You are a helpful assistant."

    @abstractmethod
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        """根据主题生成完整 Storyboard。"""
        raise NotImplementedError
