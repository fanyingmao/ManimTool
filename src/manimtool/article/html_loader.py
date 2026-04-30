"""把"图文文章"形式的 HTML 解析为 ``Storyboard``。

为了避免引入额外依赖（如 BeautifulSoup），实现使用 ``html.parser`` 标准库。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from manimtool.errors import ConfigError
from manimtool.schemas import Scene, Storyboard

_TAG_STRIP_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_tags(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_STRIP_RE.sub("", html)).strip()


def _decode_entities(text: str) -> str:
    import html as _html

    return _html.unescape(text)


class _SectionCollector(HTMLParser):
    """收集 ``<section data-scene-id>`` 内部的原始 HTML 与关键字段。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._section_depth = 0
        self._current_attrs: dict[str, str] = {}
        self._current_html: list[str] = []
        self.sections: list[tuple[dict[str, str], str]] = []
        self.title: str = ""
        self.summary: str = ""
        self._in_h1 = False
        self._in_summary = False
        self._h1_buf: list[str] = []
        self._summary_buf: list[str] = []

    def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {k: (v or "") for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = self._attrs_to_dict(attrs)
        if tag == "section" and "data-scene-id" in a:
            if self._section_depth == 0:
                self._current_attrs = a
                self._current_html = []
            self._section_depth += 1
        if self._section_depth > 0:
            self._current_html.append(self.get_starttag_text() or "")
        if tag == "h1" and self._section_depth == 0:
            self._in_h1 = True
        if a.get("data-role") == "summary" and self._section_depth == 0:
            self._in_summary = True

    def handle_endtag(self, tag: str) -> None:
        if self._section_depth > 0:
            self._current_html.append(f"</{tag}>")
            if tag == "section":
                self._section_depth -= 1
                if self._section_depth == 0:
                    self.sections.append((self._current_attrs, "".join(self._current_html)))
                    self._current_attrs = {}
                    self._current_html = []
        if tag == "h1":
            self._in_h1 = False
            if self._h1_buf and not self.title:
                self.title = "".join(self._h1_buf).strip()
        if tag in {"p", "div"} and self._in_summary:
            self._in_summary = False
            if self._summary_buf and not self.summary:
                self.summary = " ".join("".join(self._summary_buf).split())
            self._summary_buf = []

    def handle_data(self, data: str) -> None:
        if self._section_depth > 0:
            self._current_html.append(data)
        if self._in_h1:
            self._h1_buf.append(data)
        if self._in_summary:
            self._summary_buf.append(data)


def _extract_attribute(html: str, tag: str, attr: str, value: str) -> list[str]:
    """提取 ``<tag ... attr="value" ...>...</tag>`` 包裹的内层文本/HTML 列表。

    简单实现，不支持嵌套同名标签。
    """
    pattern = re.compile(
        rf'<{tag}\b[^>]*\b{re.escape(attr)}\s*=\s*"{re.escape(value)}"[^>]*>(.*?)</{tag}>',
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.findall(html)


def _extract_first_text(html: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return _strip_tags(_decode_entities(m.group(1)))


def _extract_pre_mermaid(html: str) -> str | None:
    m = re.search(
        r'<pre[^>]*class="[^"]*mermaid[^"]*"[^>]*>(.*?)</pre>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        inner = m.group(1)
    else:
        m2 = re.search(
            r'<pre[^>]*data-role="diagram"[^>]*>(.*?)</pre>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not m2:
            return None
        inner = m2.group(1)
    return _decode_entities(inner).strip()


def load_storyboard_from_html(path: str | Path) -> Storyboard:
    """从 HTML 文件构造 ``Storyboard``。"""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"HTML 文件不存在: {p}")
    raw = p.read_text(encoding="utf-8")

    parser = _SectionCollector()
    parser.feed(raw)
    parser.close()

    if not parser.sections:
        raise ConfigError(
            f"未在 {p} 中发现 <section data-scene-id=...> 节，无法构造 storyboard"
        )

    scenes: list[Scene] = []
    for attrs, html in parser.sections:
        scene_id = attrs.get("data-scene-id", "").strip()
        if not scene_id:
            continue
        title = _extract_first_text(html, "h2") or _extract_first_text(html, "h3") or scene_id

        narrations = _extract_attribute(html, "p", "data-role", "narration")
        if not narrations:
            narrations = _extract_attribute(html, "div", "data-role", "narration")
        narration_text = (
            _strip_tags(_decode_entities(narrations[0])) if narrations else ""
        )
        if not narration_text:
            first_p = _extract_first_text(html, "p")
            narration_text = first_p or ""

        mermaid = _extract_pre_mermaid(html)
        if not mermaid:
            continue

        duration_hint_raw = attrs.get("data-duration-hint")
        try:
            duration_hint = float(duration_hint_raw) if duration_hint_raw else None
        except ValueError:
            duration_hint = None

        scenes.append(
            Scene(
                id=scene_id,
                title=title[:40],
                narration=narration_text[:600] or "（缺少旁白）",
                mermaid=mermaid,
                duration_hint=duration_hint,
            )
        )

    if not scenes:
        raise ConfigError(f"{p} 中没有有效的 scene（缺少 mermaid 块）")

    return Storyboard(
        title=parser.title or p.stem,
        summary=parser.summary,
        scenes=scenes,
    )
