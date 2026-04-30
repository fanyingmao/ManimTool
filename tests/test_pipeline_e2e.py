from __future__ import annotations

from pathlib import Path

from manimtool.pipeline import run_pipeline
from manimtool.schemas import (
    AppConfig,
    RenderedScene,
    Scene,
    Storyboard,
    TTSResult,
    VideoArtifact,
)


def test_pipeline_e2e_with_mocks(tmp_path: Path, monkeypatch) -> None:
    scene = Scene(id="intro", title="开场", narration="旁白", mermaid="flowchart LR\nA-->B")
    storyboard = Storyboard(title="测试视频", summary="s", scenes=[scene])
    cfg = AppConfig.model_validate({"project": {"output_dir": tmp_path}})

    class _Renderer:
        @staticmethod
        def render(s: Scene, output_dir: Path) -> RenderedScene:
            output_dir.mkdir(parents=True, exist_ok=True)
            p = output_dir / f"{s.id}.png"
            p.write_bytes(b"img")
            return RenderedScene(scene_id=s.id, image_path=p, width=100, height=100)

    class _TTS:
        @staticmethod
        def synthesize(s: Scene, output_dir: Path) -> TTSResult:
            output_dir.mkdir(parents=True, exist_ok=True)
            p = output_dir / f"{s.id}.mp3"
            p.write_bytes(b"aud")
            return TTSResult(scene_id=s.id, audio_path=p, duration=1.0)

    class _Composer:
        @staticmethod
        def compose(title: str, artifacts, output_path: Path):
            output_path.write_bytes(b"video")
            return VideoArtifact(title=title, video_path=output_path, duration=1.0, scenes=artifacts)

    monkeypatch.setattr("manimtool.pipeline.get_renderer", lambda _: _Renderer())
    monkeypatch.setattr("manimtool.pipeline.get_tts", lambda _: _TTS())
    monkeypatch.setattr("manimtool.pipeline.get_composer", lambda *_args, **_kwargs: _Composer())

    artifact = run_pipeline("主题", config=cfg, storyboard=storyboard)
    assert artifact.video_path.exists()
    assert artifact.storyboard_path is not None
    assert artifact.storyboard_path.exists()
