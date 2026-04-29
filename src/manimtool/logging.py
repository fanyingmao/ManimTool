"""统一日志入口（loguru）。所有模块只通过 `from manimtool.logging import logger` 使用。"""

from __future__ import annotations

import sys

from loguru import logger

_configured = False


def setup_logging(level: str = "INFO") -> None:
    """幂等地配置 loguru。CLI 与 pipeline 入口处调用一次即可。"""
    global _configured
    if _configured:
        return
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
        ),
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    _configured = True


__all__ = ["logger", "setup_logging"]
