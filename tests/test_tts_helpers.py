"""TTS 字幕辅助函数测试（不真正调用 edge-tts 网络）。"""

from __future__ import annotations

from manimtool.tts.edge_tts_client import (
    _chunk_narration,
    _cues_from_word_boundaries,
    _format_srt_timestamp,
)


def test_format_srt_timestamp() -> None:
    assert _format_srt_timestamp(0) == "00:00:00,000"
    assert _format_srt_timestamp(1.234) == "00:00:01,234"
    assert _format_srt_timestamp(3661.5) == "01:01:01,500"


def test_chunk_narration_splits_by_punct() -> None:
    text = "这是第一句。这是第二句！第三句很短，但有逗号。"
    chunks = _chunk_narration(text)
    assert len(chunks) >= 3
    assert chunks[0].endswith("。")


def test_chunk_narration_handles_long_text() -> None:
    text = "一" * 100
    chunks = _chunk_narration(text, max_chars=30)
    assert all(len(c) <= 30 for c in chunks)


def test_chunk_narration_no_orphan_short_lines() -> None:
    text = "深度学习用层层堆叠的神经网络自动学习特征，再反复迭代。"
    chunks = _chunk_narration(text, max_chars=24)
    assert all(len(c) >= 4 for c in chunks)


def test_cues_from_word_boundaries_aligns_chunks() -> None:
    chunks = ["你好世界", "再见"]
    boundaries = [
        (0.0, 0.5, "你"),
        (0.5, 0.5, "好"),
        (1.0, 0.5, "世"),
        (1.5, 0.5, "界"),
        (2.0, 0.5, "再"),
        (2.5, 0.5, "见"),
    ]
    cues = _cues_from_word_boundaries(boundaries, chunks)
    assert len(cues) == 2
    assert cues[0].text == "你好世界"
    assert cues[0].start == 0.0
    assert cues[0].end == 2.0
    assert cues[1].text == "再见"
    assert cues[1].start == 2.0
    assert cues[1].end == 3.0
