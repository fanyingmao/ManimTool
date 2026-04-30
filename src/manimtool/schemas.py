"""项目内贯穿全流程的数据契约（Schema）。

所有模块之间通过这些 Pydantic 模型交换数据，**不要**在模块边界传递自由 dict。
任何字段调整必须同步更新：
    - configs/prompts/*.md（提示词约定）
    - docs/ARCHITECTURE.md（架构文档）
    - tests/（夹具与回归测试）
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Scene(BaseModel):
    """单个分镜：一段旁白 + 一张图表。

    这是 LLM 输出 → 渲染 → TTS → 合成 全流程的最小单元。
    """

    id: str = Field(..., description="蛇形命名的英文唯一标识", pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(..., description="中文标题", max_length=40)
    narration: str = Field(..., description="旁白文稿（用于 TTS）", min_length=1, max_length=600)
    mermaid: str = Field(..., description="Mermaid 源码（不含围栏标记）", min_length=1)
    duration_hint: float | None = Field(
        default=None, description="建议时长（秒），最终以 TTS 实际时长为准", ge=0
    )
    reveal_points: list[str] = Field(
        default_factory=list,
        description="可选：按讲解节奏逐步展示的要点文案，按顺序出现",
        max_length=8,
    )

    @field_validator("mermaid")
    @classmethod
    def _strip_fence(cls, v: str) -> str:
        s = v.strip()
        if s.startswith("```"):
            lines = s.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()
        return s


class Storyboard(BaseModel):
    """LLM 一次生成的完整脚本：标题 + 多个分镜。"""

    title: str = Field(..., description="视频标题")
    summary: str = Field(default="", description="一句话概要")
    scenes: list[Scene] = Field(..., min_length=1)


class RenderedScene(BaseModel):
    """渲染阶段的产物。"""

    scene_id: str
    image_path: Path
    width: int
    height: int


class SubtitleCue(BaseModel):
    """单条字幕：用于 TTS WordBoundary 对齐与视频内字幕渲染。"""

    start: float = Field(..., ge=0, description="开始时间（秒）")
    end: float = Field(..., ge=0, description="结束时间（秒）")
    text: str = Field(..., min_length=1)


class TTSResult(BaseModel):
    """TTS 阶段的产物。"""

    scene_id: str
    audio_path: Path
    duration: float = Field(..., ge=0, description="音频时长（秒）")
    subtitle_path: Path | None = None
    cues: list[SubtitleCue] = Field(
        default_factory=list,
        description="按时间排序的字幕分段；为空时由合成器按 narration 整段显示",
    )


class SceneArtifact(BaseModel):
    """单个分镜的全部中间产物。"""

    scene: Scene
    rendered: RenderedScene
    tts: TTSResult


class VideoArtifact(BaseModel):
    """流水线最终产物。"""

    title: str
    video_path: Path
    duration: float
    scenes: list[SceneArtifact]
    storyboard_path: Path | None = None


# ----------------- 配置模型 -----------------


class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.4
    max_tokens: int = 4096
    timeout_seconds: int = 60
    retries: int = 2


class TTSConfig(BaseModel):
    provider: Literal["edge"] = "edge"
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


class MermaidConfig(BaseModel):
    cli: str = "mmdc"
    theme: Literal["default", "dark", "forest", "neutral"] = "default"
    background: str = "transparent"
    width: int = 1920
    height: int = 1080
    scale: int = 2


class RenderConfig(BaseModel):
    engine: Literal["mermaid"] = "mermaid"
    mermaid: MermaidConfig = Field(default_factory=MermaidConfig)


class VideoConfig(BaseModel):
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"
    background_color: str = "#0E1117"
    font: str = "Noto Sans CJK SC"
    font_size: int = 42
    title_font_size: int = 56
    subtitle_font_size: int = 38
    subtitle_enabled: bool = True
    transition: Literal["none", "fade", "slide"] = "fade"
    transition_duration: float = 0.5
    progress_bar_enabled: bool = Field(
        default=True,
        description="是否在视频顶部显示章节进度条 / 章节标签",
    )
    progress_bar_height: int = 14
    progress_bar_color: str = "#4C6EF5"
    progress_bar_bg_color: str = "#2B2F38"
    progress_bar_padding: int = 28
    chapter_label_color: str = "#FFFFFF"
    subtitle_box_color: str = "#000000"
    subtitle_box_opacity: float = 0.55
    image_padding_top: int = 160
    image_padding_bottom: int = 240
    motion_enabled: bool = Field(
        default=True,
        description="启用静态图轻微缩放，营造 Ken Burns 效果",
    )
    motion_zoom_speed: float = 0.0006
    scene_fade_duration: float = 0.4
    title_enabled: bool = True


class ProjectConfig(BaseModel):
    name: str = "manimtool"
    output_dir: Path = Path("./output")
    cache_dir: Path = Path("./.cache")
    log_level: str = "INFO"


class AppConfig(BaseModel):
    """应用顶层配置：由 `manimtool.config.load_config()` 装配。"""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
