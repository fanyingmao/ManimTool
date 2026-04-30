"""Anthropic Claude 客户端实现（骨架）。

TODO(cursor):
    - 调用 `anthropic` SDK 的 `messages.create`
    - System prompt 作为 system 字段传入
    - User 消息要求只输出 JSON
    - 用 tenacity 重试，并对 `json.JSONDecodeError` / Pydantic 校验失败做一次"修复重试"
"""

from __future__ import annotations

import json
import os

from anthropic import Anthropic
from pydantic import ValidationError
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from manimtool.errors import LLMError
from manimtool.llm.base import BaseLLM
from manimtool.schemas import Storyboard


class AnthropicLLM(BaseLLM):
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("缺少 ANTHROPIC_API_KEY，无法调用 Anthropic")

        client = Anthropic(api_key=api_key, timeout=self.config.timeout_seconds)
        prompt = f"主题：{topic}\n请严格只输出 JSON。"
        if extra_instruction.strip():
            prompt = f"{prompt}\n附加要求：{extra_instruction.strip()}"

        @retry(
            stop=stop_after_attempt(self.config.retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            reraise=True,
        )
        def _call() -> Storyboard:
            resp = client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=self._system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks: list[str] = []
            for block in resp.content:
                if getattr(block, "type", "") == "text":
                    block_text = getattr(block, "text", "")
                    if isinstance(block_text, str):
                        text_blocks.append(block_text)
            content = "\n".join(text_blocks).strip()
            if not content:
                raise LLMError("Anthropic 返回空内容")
            try:
                payload = json.loads(content)
                return Storyboard.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise LLMError(f"Anthropic 输出解析失败: {exc}") from exc

        try:
            return _call()
        except RetryError as exc:
            raise LLMError(f"Anthropic 调用重试后仍失败: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMError(f"Anthropic 调用失败: {exc}") from exc
