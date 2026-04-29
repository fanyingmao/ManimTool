"""OpenAI / 兼容 OpenAI 协议的 LLM 客户端实现（骨架）。

TODO(cursor):
    - 调用 `openai` 官方 SDK 的 `chat.completions.create`
    - 通过 `response_format={"type": "json_object"}` 强制 JSON 输出
    - 使用 tenacity 实现 `config.retries` 次重试
    - 解析后用 `Storyboard.model_validate_json` 校验
"""

from __future__ import annotations

from manimtool.errors import LLMError
from manimtool.llm.base import BaseLLM
from manimtool.schemas import Storyboard


class OpenAILLM(BaseLLM):
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        raise LLMError("OpenAILLM.generate_storyboard 尚未实现，请由 cursor 完成")
