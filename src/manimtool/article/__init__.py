"""HTML 文章 → Storyboard 解析模块。

约定：每个 ``<section data-scene-id="...">`` 是一个分镜，需包含：
    - ``<h2>``：章节标题
    - 任何带 ``data-role="narration"`` 的元素：旁白
    - ``<pre class="mermaid">`` 或带 ``data-role="diagram"`` 的元素：Mermaid 源码
"""

from manimtool.article.html_loader import load_storyboard_from_html

__all__ = ["load_storyboard_from_html"]
