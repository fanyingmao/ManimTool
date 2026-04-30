"""HTML → Storyboard 解析测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from manimtool.article import load_storyboard_from_html
from manimtool.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_HTML = REPO_ROOT / "examples" / "ai_intelligence_article.html"


def test_loads_example_article() -> None:
    sb = load_storyboard_from_html(EXAMPLE_HTML)
    assert sb.title.startswith("人工智能")
    assert len(sb.scenes) == 6
    ids = [s.id for s in sb.scenes]
    assert ids == [
        "overview",
        "machine_learning",
        "deep_learning",
        "transformer",
        "agent",
        "future",
    ]
    s0 = sb.scenes[0]
    assert s0.title.startswith("一、")
    assert "感知" in s0.narration
    assert "flowchart" in s0.mermaid


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_storyboard_from_html(tmp_path / "missing.html")


def test_html_without_section_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.html"
    p.write_text("<html><body><p>nothing</p></body></html>", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_storyboard_from_html(p)


def test_html_with_section_but_no_mermaid_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.html"
    p.write_text(
        '<section data-scene-id="a"><h2>T</h2><p data-role="narration">N</p></section>',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_storyboard_from_html(p)
