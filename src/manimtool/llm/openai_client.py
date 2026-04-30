"""OpenAI / 兼容 OpenAI 协议的 LLM 客户端实现。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from manimtool.errors import LLMError
from manimtool.llm.base import BaseLLM
from manimtool.logging import logger
from manimtool.schemas import Storyboard

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "prompts" / "system_zh.md"
)


def _system_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return "You are a helpful assistant."


class OpenAILLM(BaseLLM):
    def generate_storyboard(self, topic: str, *, extra_instruction: str = "") -> Storyboard:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise LLMError("未安装 openai SDK，请 `pip install openai`") from e

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("缺少 OPENAI_API_KEY 环境变量")

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL"),
            timeout=self.config.timeout_seconds,
        )

        sys = _system_prompt()
        user = f"主题：{topic}"
        if extra_instruction:
            user += f"\n附加要求：{extra_instruction}"

        last_err: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=self.config.model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": sys},
                        {"role": "user", "content": user},
                    ],
                )
                content = resp.choices[0].message.content or "{}"
                data = json.loads(content)
                return Storyboard.model_validate(data)
            except Exception as e:
                last_err = e
                logger.warning(
                    f"OpenAI 调用失败（第 {attempt + 1}/{self.config.retries + 1} 次）：{e}"
                )
        raise LLMError(f"OpenAI 调用最终失败: {last_err}") from last_err
