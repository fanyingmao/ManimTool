from __future__ import annotations

import json

import pytest

from manimtool.errors import LLMError
from manimtool.llm.anthropic_client import AnthropicLLM
from manimtool.llm.openai_client import OpenAILLM
from manimtool.schemas import LLMConfig


def test_openai_generate_storyboard_success(monkeypatch) -> None:
    payload = {
        "title": "测试视频",
        "summary": "概要",
        "scenes": [
            {
                "id": "intro",
                "title": "开场",
                "narration": "你好",
                "mermaid": "flowchart LR\nA-->B",
                "duration_hint": None,
            }
        ],
    }

    class _Resp:
        class _Choice:
            class _Msg:
                content = json.dumps(payload, ensure_ascii=False)

            message = _Msg()

        choices = [_Choice()]  # noqa: RUF012

    class _Completions:
        @staticmethod
        def create(**kwargs):
            return _Resp()

    class _Client:
        class chat:  # noqa: N801 - 模拟 OpenAI SDK 的小写命名
            completions = _Completions()

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr("manimtool.llm.openai_client.OpenAI", lambda **_: _Client())
    llm = OpenAILLM(LLMConfig(provider="openai", retries=0))
    sb = llm.generate_storyboard("主题")
    assert sb.title == "测试视频"
    assert sb.scenes[0].id == "intro"


def test_anthropic_generate_storyboard_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    llm = AnthropicLLM(LLMConfig(provider="anthropic", retries=0))
    with pytest.raises(LLMError):
        llm.generate_storyboard("主题")
