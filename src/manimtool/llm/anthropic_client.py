"""Anthropic Claude 客户端实现。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from manimtool.errors import LLMError
from manimtool.llm.base import BaseLLM
from manimtool.logging import logger
from manimtool.schemas import Storyboard

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "prompts" / "system_zh.md"
)

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _system_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return "You are a helpful assistant."


class AnthropicLLM(BaseLLM):
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise LLMError("未安装 anthropic SDK，请 `pip install anthropic`") from e

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("缺少 ANTHROPIC_API_KEY 环境变量")

        client = anthropic.Anthropic(api_key=api_key, timeout=self.config.timeout_seconds)
        sys = _system_prompt()
        user = f"主题：{topic}\n请只输出 JSON。"
        if extra_instruction:
            user += f"\n附加要求：{extra_instruction}"

        last_err: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                resp = client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=sys,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(
                    getattr(b, "text", "") for b in resp.content if hasattr(b, "text")
                )
                m = _JSON_BLOCK.search(text)
                payload = m.group(0) if m else text
                return Storyboard.model_validate(json.loads(payload))
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning(
                    f"Anthropic 调用失败（第 {attempt + 1}/{self.config.retries + 1} 次）：{e}"
                )
        raise LLMError(f"Anthropic 调用最终失败: {last_err}") from last_err
