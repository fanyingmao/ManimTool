from __future__ import annotations

from pathlib import Path

import pytest

from manimtool.errors import VideoComposeError
from manimtool.schemas import (
    RenderedScene,
    Scene,
    SceneArtifact,
    TTSResult,
    VideoConfig,
)
from manimtool.video.ffmpeg_composer import FFmpegComposer


def _artifact(tmp_path: Path) -> SceneArtifact:
    img = tmp_path / "a.png"
    aud = tmp_path / "a.mp3"
    img.write_bytes(b"png")
    aud.write_bytes(b"mp3")
    scene = Scene(id="intro", title="t", narration="n", mermaid="flowchart LR\nA-->B")
    return SceneArtifact(
        scene=scene,
        rendered=RenderedScene(scene_id="intro", image_path=img, width=100, height=100),
        tts=TTSResult(scene_id="intro", audio_path=aud, duration=1.2),
    )


def test_ffmpeg_composer_requires_binary(tmp_path: Path, monkeypatch) -> None:
    """没有 ffmpeg 也没有 imageio_ffmpeg 时应抛 VideoComposeError。"""
    monkeypatch.setattr("manimtool.video.ffmpeg_composer.shutil.which", lambda _: None)

    def _raise(*_a, **_kw):
        raise VideoComposeError("no ffmpeg available")

    monkeypatch.setattr(
        "manimtool.video.ffmpeg_composer._resolve_ffmpeg", _raise
    )
    composer = FFmpegComposer(VideoConfig())
    with pytest.raises(VideoComposeError):
        composer.compose("t", [_artifact(tmp_path)], tmp_path / "out.mp4")
