"""自定义异常类。模块边界抛错时统一使用这些类型，便于 CLI 层归类处理。"""

from __future__ import annotations


class ManimToolError(Exception):
    """所有自定义异常基类。"""


class ConfigError(ManimToolError):
    """配置加载或校验失败。"""


class LLMError(ManimToolError):
    """LLM 调用或输出解析失败。"""


class RenderError(ManimToolError):
    """图表渲染失败（mermaid-cli 报错等）。"""


class TTSError(ManimToolError):
    """TTS 合成失败。"""


class VideoComposeError(ManimToolError):
    """视频合成失败。"""
