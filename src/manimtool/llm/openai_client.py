"""OpenAI / 兼容 OpenAI 协议的 LLM 客户端实现（骨架）。

TODO(cursor):
    - 调用 `openai` 官方 SDK 的 `chat.completions.create`
    - 通过 `response_format={"type": "json_object"}` 强制 JSON 输出
    - 使用 tenacity 实现 `config.retries` 次重试
    - 解析后用 `Storyboard.model_validate_json` 校验
"""

from __future__ import annotations

import json
import os

from openai import OpenAI
from pydantic import ValidationError
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from manimtool.errors import LLMError
from manimtool.llm.base import BaseLLM
from manimtool.schemas import Storyboard


class OpenAILLM(BaseLLM):
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise LLMError("缺少 OPENAI_API_KEY，无法调用 OpenAI")

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.config.timeout_seconds)
        prompt = f"主题：{topic}\n请严格只输出 JSON。"
        if extra_instruction.strip():
            prompt = f"{prompt}\n附加要求：{extra_instruction.strip()}"

        @retry(
            stop=stop_after_attempt(self.config.retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            reraise=True,
        )
        def _call() -> Storyboard:
            resp = client.chat.completions.create(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )
            content = resp.choices[0].message.content
            if not content:
                raise LLMError("OpenAI 返回空内容")
            try:
                payload = json.loads(content)
                return Storyboard.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise LLMError(f"OpenAI 输出解析失败: {exc}") from exc

        try:
            return _call()
        except RetryError as exc:
            raise LLMError(f"OpenAI 调用重试后仍失败: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMError(f"OpenAI 调用失败: {exc}") from exc
