"""pytest 共享夹具。"""

from __future__ import annotations

from pathlib import Path

import pytest

from manimtool.schemas import Scene, Storyboard


@pytest.fixture
def sample_scene() -> Scene:
    return Scene(
        id="intro",
        title="测试场景",
        narration="这是一个用于测试的旁白。",
        mermaid="flowchart LR\n  A[开始] --> B[结束]",
    )


@pytest.fixture
def sample_storyboard(sample_scene: Scene) -> Storyboard:
    return Storyboard(title="测试视频", summary="一个示例", scenes=[sample_scene])


@pytest.fixture
def tmp_run_dir(tmp_path: Path) -> Path:
    p = tmp_path / "run"
    p.mkdir()
    return p
