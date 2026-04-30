from __future__ import annotations

from pathlib import Path

from manimtool.schemas import Scene, TTSConfig
from manimtool.tts.edge_tts_client import EdgeTTS


def test_edge_tts_synthesize_writes_audio_and_subtitle(tmp_path: Path, monkeypatch) -> None:
    class _FakeCommunicate:
        def __init__(self, **kwargs):
            self._events = [
                {"type": "audio", "data": b"abc"},
                {
                    "type": "WordBoundary",
                    "offset": 0,
                    "duration": 5_000_000,
                    "text": "你好",
                },
            ]

        async def stream(self):
            for event in self._events:
                yield event

    monkeypatch.setattr("manimtool.tts.edge_tts_client.edge_tts.Communicate", _FakeCommunicate)
    scene = Scene(id="intro", title="t", narration="你好", mermaid="flowchart LR\nA-->B")
    tts = EdgeTTS(TTSConfig())
    result = tts.synthesize(scene, tmp_path)

    assert result.audio_path.exists()
    assert result.duration > 0
    assert result.subtitle_path is not None
    assert result.subtitle_path.exists()
