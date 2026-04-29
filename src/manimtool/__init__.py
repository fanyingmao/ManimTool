"""ManimTool: AI 驱动的自动化视频生成工具。

公开 API 仅限以下符号；内部模块（带下划线前缀）不属于稳定接口。
"""

from manimtool.schemas import Scene, Storyboard, VideoArtifact

__version__ = "0.1.0"
__all__ = ["Scene", "Storyboard", "VideoArtifact", "__version__"]
