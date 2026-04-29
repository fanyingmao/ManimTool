"""配置加载测试。"""

from __future__ import annotations

from pathlib import Path

from manimtool.config import load_config


def test_load_default_config() -> None:
    cfg = load_config()
    assert cfg.llm.provider in {"openai", "anthropic"}
    assert cfg.tts.voice.startswith("zh-CN")
    assert cfg.video.fps > 0


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("TTS_VOICE", "zh-CN-YunxiNeural")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    cfg = load_config()
    assert cfg.tts.voice == "zh-CN-YunxiNeural"
    assert cfg.project.log_level == "DEBUG"


def test_overrides_take_priority() -> None:
    cfg = load_config(overrides={"video": {"fps": 60}})
    assert cfg.video.fps == 60


def test_custom_yaml_path(tmp_path: Path) -> None:
    yaml_path = tmp_path / "c.yaml"
    yaml_path.write_text("llm:\n  model: gpt-test\n", encoding="utf-8")
    cfg = load_config(yaml_path)
    assert cfg.llm.model == "gpt-test"
