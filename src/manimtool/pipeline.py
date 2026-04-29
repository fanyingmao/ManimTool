"""端到端流水线：主题 → 视频。

约束：
    - 每个阶段产物落盘到 `<output_dir>/<run_id>/` 下，便于断点重跑
    - 任何阶段失败应抛出对应子异常，pipeline 不吞错
    - 不要在此处直接调用第三方 SDK，全部走工厂
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from manimtool.config import load_config
from manimtool.llm import get_llm
from manimtool.logging import logger, setup_logging
from manimtool.render import get_renderer
from manimtool.schemas import (
    AppConfig,
    SceneArtifact,
    Storyboard,
    VideoArtifact,
)
from manimtool.tts import get_tts
from manimtool.video import get_composer


def _new_run_dir(root: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_pipeline(
    topic: str,
    *,
    config: AppConfig | None = None,
    storyboard: Storyboard | None = None,
    video_backend: str = "moviepy",
) -> VideoArtifact:
    """执行完整流水线。

    Args:
        topic: 视频主题（自然语言）。
        config: 已装配好的 AppConfig；为空则从默认位置加载。
        storyboard: 跳过 LLM 步骤直接传入 Storyboard（用于调试/缓存）。
        video_backend: 'moviepy' 或 'ffmpeg'。
    """
    cfg = config or load_config()
    setup_logging(cfg.project.log_level)
    run_dir = _new_run_dir(cfg.project.output_dir)
    logger.info(f"运行目录: {run_dir}")

    # Stage 1: LLM
    if storyboard is None:
        logger.info("[1/4] 调用 LLM 生成 storyboard")
        storyboard = get_llm(cfg.llm).generate_storyboard(topic)
    sb_path = run_dir / "storyboard.json"
    sb_path.write_text(
        json.dumps(storyboard.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Stage 2: 渲染
    logger.info("[2/4] 渲染图表")
    renderer = get_renderer(cfg.render)
    render_dir = run_dir / "frames"
    rendered = [renderer.render(s, render_dir) for s in storyboard.scenes]

    # Stage 3: TTS
    logger.info("[3/4] 合成语音")
    tts = get_tts(cfg.tts)
    audio_dir = run_dir / "audio"
    audios = [tts.synthesize(s, audio_dir) for s in storyboard.scenes]

    artifacts = [
        SceneArtifact(scene=s, rendered=r, tts=a)
        for s, r, a in zip(storyboard.scenes, rendered, audios, strict=True)
    ]

    # Stage 4: 合成视频
    logger.info("[4/4] 合成视频")
    composer = get_composer(cfg.video, backend=video_backend)
    output_path = run_dir / f"{storyboard.title}.mp4"
    artifact = composer.compose(storyboard.title, artifacts, output_path)
    artifact.storyboard_path = sb_path
    logger.success(f"完成：{artifact.video_path}")
    return artifact
