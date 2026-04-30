"""render_profile / MoviePy 有效合成参数。"""

from __future__ import annotations

from manimtool.schemas import VideoConfig
from manimtool.video.moviepy_composer import _moviepy_effective_params


def test_normal_profile_uses_config_resolution() -> None:
    cfg = VideoConfig(
        resolution=(1920, 1080),
        fps=30,
        render_profile="normal",
        progress_segments_per_second=2.0,
    )
    w, h, fps, trans, td, seg, preset = _moviepy_effective_params(cfg)
    assert (w, h) == (1920, 1080)
    assert fps == 30
    assert seg == 2.0
    assert trans == "fade"


def test_draft_profile_lowers_resolution_and_fps() -> None:
    cfg = VideoConfig(
        resolution=(1920, 1080),
        fps=30,
        render_profile="draft",
        transition="fade",
        transition_duration=0.5,
        progress_segments_per_second=4.0,
        encode_preset="medium",
    )
    w, h, fps, trans, td, seg, preset = _moviepy_effective_params(cfg)
    assert (w, h) == (1280, 720)
    assert fps == 24
    assert trans == "none"
    assert td == 0.0
    assert seg <= 0.5
    assert preset == "veryfast"
