"""Anthropic Claude 客户端实现（骨架）。

TODO(cursor):
    - 调用 `anthropic` SDK 的 `messages.create`
    - System prompt 作为 system 字段传入
    - User 消息要求只输出 JSON
    - 用 tenacity 重试，并对 `json.JSONDecodeError` / Pydantic 校验失败做一次"修复重试"
"""

from __future__ import annotations

from manimtool.errors import LLMError
from manimtool.llm.base import BaseLLM
from manimtool.schemas import Storyboard


class AnthropicLLM(BaseLLM):
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        raise LLMError("AnthropicLLM.generate_storyboard 尚未实现，请由 cursor 完成")
