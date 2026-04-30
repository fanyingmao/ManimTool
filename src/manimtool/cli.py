"""命令行入口：``manimtool ...``。

子命令：
    generate       端到端：主题 → 视频
    storyboard     仅生成 storyboard.json（调试 LLM）
    from-html      用 HTML 文章作为 storyboard 来源生成视频
    compose        给定中间产物目录，仅合成视频
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from manimtool.config import load_config
from manimtool.logging import setup_logging
from manimtool.pipeline import run_pipeline
from manimtool.schemas import Storyboard

app = typer.Typer(add_completion=False, help="ManimTool: AI 自动化视频生成工具")


@app.command()
def generate(
    topic: Annotated[str, typer.Option("--topic", "-t", help="视频主题")],
    config: Annotated[Path | None, typer.Option("--config", "-c", help="自定义配置文件")] = None,
    backend: Annotated[str, typer.Option("--backend", help="视频合成后端: moviepy | ffmpeg")] = "moviepy",
) -> None:
    """根据主题端到端生成视频。"""
    cfg = load_config(config)
    setup_logging(cfg.project.log_level)
    artifact = run_pipeline(topic, config=cfg, video_backend=backend)
    rprint(f"[green]视频已生成：[/green]{artifact.video_path}")


@app.command()
def storyboard(
    topic: Annotated[str, typer.Option("--topic", "-t")],
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("storyboard.json"),
) -> None:
    """仅调用 LLM 生成 storyboard.json。"""
    from manimtool.llm import get_llm

    cfg = load_config(config)
    setup_logging(cfg.project.log_level)
    sb = get_llm(cfg.llm).generate_storyboard(topic)
    output.write_text(json.dumps(sb.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    rprint(f"[green]storyboard 已写入：[/green]{output}")


@app.command("from-html")
def from_html(
    html: Annotated[Path, typer.Option("--html", "-H", help="包含分镜的 HTML 文章")],
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    backend: Annotated[str, typer.Option("--backend")] = "moviepy",
    save_storyboard: Annotated[
        Path | None,
        typer.Option("--save-storyboard", help="同时把解析后的 storyboard 写到该路径"),
    ] = None,
) -> None:
    """直接以一篇 HTML 文章作为视频的 storyboard 来源。

    HTML 中每个 ``<section data-scene-id="...">`` 节会成为一个分镜。
    """
    from manimtool.article import load_storyboard_from_html

    cfg = load_config(config)
    setup_logging(cfg.project.log_level)
    sb = load_storyboard_from_html(html)
    if save_storyboard:
        save_storyboard.write_text(
            json.dumps(sb.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rprint(f"[cyan]已保存 storyboard：[/cyan]{save_storyboard}")
    artifact = run_pipeline(sb.title, config=cfg, storyboard=sb, video_backend=backend)
    rprint(f"[green]视频已生成：[/green]{artifact.video_path}")


@app.command()
def compose(
    storyboard_path: Annotated[Path, typer.Option("--storyboard", "-s")],
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    backend: Annotated[str, typer.Option("--backend")] = "moviepy",
) -> None:
    """读取本地 storyboard.json 重新跑后续阶段。"""
    cfg = load_config(config)
    setup_logging(cfg.project.log_level)
    sb = Storyboard.model_validate_json(storyboard_path.read_text(encoding="utf-8"))
    artifact = run_pipeline(sb.title, config=cfg, storyboard=sb, video_backend=backend)
    rprint(f"[green]视频已生成：[/green]{artifact.video_path}")


if __name__ == "__main__":
    app()
