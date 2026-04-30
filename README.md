# ManimTool

> AI 驱动的自动化视频生成工具：
> **LLM（GPT/Claude）/ HTML 文章 → Mermaid 图表 → Edge-TTS 旁白 → FFmpeg / MoviePy 合成 1080p 教学视频。**

## 视频效果

- **同步显示**：每一节的 Mermaid 图按 TTS 旁白时长精确驻留，"读到对应内容才出现对应内容"
- **章节进度条**：视频顶部展示所有章节标签 + 当前章节高亮 + 整片进度条
- **同步字幕**：底部按 edge-tts 的 WordBoundary 时间戳生成字幕，可烧录到画面（可选 SRT 外挂）
- **场景转场**：moviepy 后端支持 fade 过渡，整体观感更接近正式科普视频

## 功能流水线

```
内容来源（任选其一）:
  · 主题（自然语言）  ── LLM ──► Storyboard
  · 图文 HTML 文章                  │
                                   ▼
                          ┌──────────────────┐
            ┌───────────►│  Mermaid 渲染图   │──┐
   Storyboard            └──────────────────┘  │
            │             ┌──────────────────┐ │
            └───────────►│  Edge-TTS + SRT   │─┴─► Compose ─► mp4
                          └──────────────────┘
```

## 快速开始

### 1. 环境准备

```bash
# Python ≥ 3.10
python -m venv .venv && source .venv/bin/activate

# 安装项目（开发模式）
make dev

# 系统级依赖
npm i -g @mermaid-js/mermaid-cli   # 提供 mmdc
sudo apt install -y ffmpeg          # 或随 imageio-ffmpeg 自动下载
```

### 2. 配置密钥

```bash
cp .env.example .env
# 编辑 .env：填入 OPENAI_API_KEY 或 ANTHROPIC_API_KEY
```

### 3. 一行生成视频

```bash
# 主题 → LLM → 视频
manimtool generate --topic "二叉树的中序遍历"

# HTML 文章 → 视频（推荐：完全可控、不依赖 LLM 调用）
manimtool from-html --html examples/ai_intelligence_article.html --backend ffmpeg
# 产物输出到 ./output/<时间戳>/<标题>.mp4
```

### 4. 仅调试某一阶段

```bash
manimtool storyboard --topic "快速排序" --output sb.json    # 仅生成脚本
manimtool compose --storyboard sb.json                       # 跳过 LLM，直接合成
manimtool from-html --html article.html --save-storyboard sb.json
```

### 5. HTML 文章作为视频脚本

把一篇 HTML 文章包成一组分镜：每个 `<section data-scene-id="...">`
里放 `<h2>` 标题、`<p data-role="narration">` 旁白与 `<pre class="mermaid">` 图表
即可。完整示例见 [`examples/ai_intelligence_article.html`](./examples/ai_intelligence_article.html)。

```html
<section data-scene-id="overview" data-duration-hint="14">
  <h2>一、什么是人工智能</h2>
  <p data-role="narration">人工智能是让机器具备感知、学习、推理与决策能力的综合学科…</p>
  <pre class="mermaid">
flowchart TB
  A([感知层]) --> B([认知层]) --> C([行动层])
  </pre>
</section>
```

### 6. 视频后端选择

| 后端 | 速度 | 转场 | 备注 |
|---|---|---|---|
| `ffmpeg` | 快（~30s 出 100s 视频） | ✓ 单镜淡入淡出 | 纯命令行，烧录 SRT，进度条用 drawbox 动态绘制；支持 Ken Burns 缩放与 reveal_points |
| `moviepy` | 慢（~3min 出 100s 视频） | ✓ 镜间 fade | Python 端合成，叠加更灵活；支持镜头间 crossfade |

```bash
manimtool from-html --html article.html --backend ffmpeg   # 默认快后端
manimtool from-html --html article.html --backend moviepy  # 带 fade 转场
```

## 项目结构

```
src/manimtool/
  schemas.py      # 数据契约（Pydantic）
  config.py       # 配置装配
  pipeline.py     # 流水线编排
  cli.py          # CLI 入口
  article/        # HTML 文章 → Storyboard
  llm/            # LLM provider（OpenAI / Anthropic）
  render/         # 图表渲染（Mermaid）
  tts/            # 语音合成（Edge-TTS）+ SRT 字幕
  video/          # 视频合成（MoviePy / FFmpeg）+ 进度条 / 字幕渲染
configs/          # 默认 YAML 配置 + 提示词
examples/
  storyboard.example.json
  ai_intelligence_article.html   # 6 章 AI 主题图文，可直接生成视频
tests/                             # 单元测试
docs/ARCHITECTURE.md               # 架构与开发约束
```

## 开发约束（必读）

- **类型完备**：所有公共函数需带类型注解，`mypy --strict` 必须通过
- **数据契约**：跨模块数据用 `manimtool.schemas` 中的 Pydantic 模型，禁用裸 `dict`
- **可插拔**：通过工厂函数实例化 provider；新增 provider 不改业务代码
- **错误显式**：抛出 `manimtool.errors.*`，禁止吞异常
- **副作用集中**：IO 仅出现在 provider 内部
- **统一日志**：只用 `from manimtool.logging import logger`

更多详情见 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)。

## 常用命令

```bash
make dev      # 安装开发依赖
make lint     # ruff 检查
make format   # 自动格式化
make type     # mypy 类型检查
make test     # 跑测试
make clean    # 清理产物
```

## License

MIT

## LLM 格式要求
你是 ManimTool 的脚本生成器。请把我提供的正文改写为教学视频分镜 JSON。

严格要求：
1) 只输出 JSON，不要 markdown，不要解释，不要代码围栏。
2) 顶层必须是：
{
  "title": "string",
  "summary": "string",
  "scenes": [ ... ]
}
3) scenes 至少 3 个，每个元素必须包含：
- id: 蛇形英文唯一标识，匹配 ^[a-z][a-z0-9_]*$
- title: 中文标题，尽量 <= 20 字
- narration: 口播文案，1~120 字，通俗自然
- mermaid: 可直接渲染的 Mermaid 源码（不要 ```mermaid 围栏）
- duration_hint: 数字秒或 null
- reveal_points: 可选，长度 <= 8 的字符串数组，按讲解节奏依次出现的要点文案；若不需要分步展示可省略或留空
4) narration 与 mermaid 语义一致，避免空泛。
5) mermaid 优先用 flowchart LR，保证语法正确可渲染。
6) 如果信息不足，允许合理补全，但不要编造明显错误事实。
7) 输出必须能被 json.loads 解析。

请基于以下正文生成：

【长文原文粘贴这里】