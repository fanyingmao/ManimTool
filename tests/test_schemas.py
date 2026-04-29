"""Schema 单元测试：保证数据契约稳定。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from manimtool.schemas import Scene, Storyboard


def test_scene_strips_mermaid_fence() -> None:
    s = Scene(
        id="s1",
        title="T",
        narration="N",
        mermaid="```mermaid\nflowchart LR\n  A-->B\n```",
    )
    assert not s.mermaid.startswith("```")
    assert "flowchart" in s.mermaid


def test_scene_id_pattern() -> None:
    with pytest.raises(ValidationError):
        Scene(id="Invalid-ID", title="T", narration="N", mermaid="flowchart LR\n  A-->B")


def test_storyboard_requires_at_least_one_scene(sample_scene: Scene) -> None:
    with pytest.raises(ValidationError):
        Storyboard(title="t", scenes=[])
    sb = Storyboard(title="t", scenes=[sample_scene])
    assert sb.scenes[0].id == "intro"
