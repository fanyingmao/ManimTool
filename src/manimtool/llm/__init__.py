"""LLM 模块：将自然语言主题转换为 Storyboard。

公开入口：
    - `BaseLLM`：抽象基类
    - `get_llm(config)`：工厂函数，按 provider 实例化
"""

from manimtool.llm.base import BaseLLM
from manimtool.llm.factory import get_llm

__all__ = ["BaseLLM", "get_llm"]
