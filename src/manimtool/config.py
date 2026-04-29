"""配置装配：YAML 文件 + 环境变量 → AppConfig。

优先级（高 → 低）：
    1. 显式传入的覆盖字典 (overrides)
    2. 环境变量（参考 .env.example）
    3. YAML 配置文件（默认 configs/default.yaml）
    4. 模型默认值
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from manimtool.schemas import AppConfig

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _from_env() -> dict[str, Any]:
    """从环境变量构造 partial 配置树。仅映射常用字段。"""
    env: dict[str, Any] = {"project": {}, "llm": {}, "tts": {}, "render": {"mermaid": {}}}
    if v := os.getenv("LLM_PROVIDER"):
        env["llm"]["provider"] = v
    if v := os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL"):
        env["llm"]["model"] = v
    if v := os.getenv("TTS_PROVIDER"):
        env["tts"]["provider"] = v
    if v := os.getenv("TTS_VOICE"):
        env["tts"]["voice"] = v
    if v := os.getenv("TTS_RATE"):
        env["tts"]["rate"] = v
    if v := os.getenv("TTS_VOLUME"):
        env["tts"]["volume"] = v
    if v := os.getenv("MERMAID_CLI_BIN"):
        env["render"]["mermaid"]["cli"] = v
    if v := os.getenv("MERMAID_THEME"):
        env["render"]["mermaid"]["theme"] = v
    if v := os.getenv("RENDER_BACKGROUND"):
        env["render"]["mermaid"]["background"] = v
    if v := os.getenv("OUTPUT_DIR"):
        env["project"]["output_dir"] = v
    if v := os.getenv("CACHE_DIR"):
        env["project"]["cache_dir"] = v
    if v := os.getenv("LOG_LEVEL"):
        env["project"]["log_level"] = v
    return env


def load_config(
    path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """装配 AppConfig 实例。"""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    raw = _deep_merge(raw, _from_env())
    if overrides:
        raw = _deep_merge(raw, overrides)
    return AppConfig.model_validate(raw)
