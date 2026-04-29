# ManimTool 架构设计

## 1. 总览

ManimTool 把"主题描述 → 教学视频"的过程拆成 4 个解耦阶段，
通过统一的 Pydantic Schema 在阶段之间流转数据。

```text
┌──────────┐   topic    ┌──────────┐ Storyboard ┌──────────┐ RenderedScene
│   CLI    │ ─────────► │   LLM    │ ─────────► │  Render  │ ─────────────┐
└──────────┘            └──────────┘            └──────────┘              │
                                                                          ▼
                                                                    ┌──────────┐
                                                                    │   TTS    │
                                                                    └────┬─────┘
                                                                         │ TTSResult
                                                                         ▼
                                                                    ┌──────────┐
                                                                    │  Video   │ ─► mp4
                                                                    │ Compose  │
                                                                    └──────────┘
```

## 2. 模块职责（单一职责，禁止跨界）

| 模块 | 输入 | 输出 | 关键约束 |
|---|---|---|---|
| `manimtool.llm` | `topic: str` | `Storyboard` | provider 可插拔；输出必须通过 Pydantic 校验 |
| `manimtool.render` | `Scene` | `RenderedScene`（PNG 路径） | 仅渲染，不做排版；失败抛 `RenderError` |
| `manimtool.tts` | `Scene` | `TTSResult`（音频 + 时长） | 必须返回精确时长，供视频对齐 |
| `manimtool.video` | `list[SceneArtifact]` | `VideoArtifact` | 时长以 TTS 为准；不调用 LLM/TTS |
| `manimtool.pipeline` | 上述全部 | `VideoArtifact` | 仅做编排，不实现业务逻辑 |
| `manimtool.cli` | argv | exit code | 只做参数解析与 IO，不写业务 |

## 3. 数据契约

唯一的真理之源是 [`src/manimtool/schemas.py`](../src/manimtool/schemas.py)。
**任何跨模块函数签名都必须使用其中的模型，禁止使用裸 `dict`。**

核心模型：

- `Scene`：一个分镜（id / title / narration / mermaid / duration_hint）
- `Storyboard`：LLM 一次输出的完整脚本
- `RenderedScene` / `TTSResult` / `SceneArtifact`：阶段产物
- `VideoArtifact`：流水线最终产物
- `AppConfig` 及子配置：运行时配置

## 4. 配置体系

加载顺序（优先级 高 → 低）：

1. 函数参数 `overrides`
2. 环境变量（参考 `.env.example`）
3. YAML 文件（默认 `configs/default.yaml`）
4. 模型默认值

`load_config()` 是唯一入口；CLI、pipeline 都必须通过它装配 `AppConfig`。

## 5. 错误处理

- 所有自定义异常统一继承 `manimtool.errors.ManimToolError`
- 模块内部错误 → 抛出对应子类（`LLMError`/`RenderError`/`TTSError`/`VideoComposeError`）
- CLI 层捕获并输出友好提示；pipeline 层不做吞没

## 6. 日志

- 唯一日志器：`from manimtool.logging import logger`
- 入口处通过 `setup_logging(level)` 幂等初始化
- 禁止业务模块直接 `print`

## 7. 目录约定

```
src/manimtool/
  llm/         # LLM provider 及工厂
  render/      # 图表渲染（mermaid，未来可扩展）
  tts/         # 语音合成
  video/       # 视频合成（moviepy / ffmpeg）
  pipeline.py  # 流水线编排
  cli.py       # 命令行
  config.py    # 配置装配
  schemas.py   # 数据契约
  logging.py   # 日志
  errors.py    # 异常
configs/
  default.yaml
  prompts/
tests/
examples/
docs/
```

## 8. 扩展指南

### 新增 LLM provider
1. 在 `src/manimtool/llm/` 下新建 `<name>_client.py`，继承 `BaseLLM`
2. 在 `factory.py` 中加分支
3. 更新 `LLMConfig.provider` Literal、`.env.example`、文档

### 新增渲染引擎（如 PlantUML / D2）
1. 在 `render/` 下新建实现，继承 `BaseRenderer`
2. 扩展 `RenderConfig.engine`
3. 在 factory 注册

### 新增视频后端
1. 继承 `BaseComposer`，实现 `compose()`
2. 在 `video.factory.get_composer` 注册 backend 名

## 9. 开发约束（重要）

读这一节即可知道在本仓库中应该怎么写代码：

1. **类型提示完整**：所有公共函数必须有完整的类型注解，`mypy --strict` 必须通过
2. **Pydantic 模型**：跨模块数据传输必须用 Schema；不要用裸 `dict`
3. **依赖注入**：模块通过工厂获得依赖；禁止在 `__init__` 中读取全局环境变量
4. **可测试性**：每个 provider 实现都需要至少一个单元测试（mock 外部调用）
5. **副作用集中**：网络/文件 IO 只允许出现在 provider 实现内部，pipeline/schemas 不允许
6. **失败显式**：禁止 `except Exception: pass`；必须包装为本项目的 `*Error`
7. **配置只读**：运行期不要修改 `AppConfig` 字段
8. **路径用 `pathlib.Path`**：禁止裸字符串拼接路径
9. **异步边界清晰**：`edge-tts` 的 async 调用必须在 provider 内部用 `asyncio.run` 包装为同步接口
10. **Lint/Format**：提交前执行 `make lint format type test`

## 10. 外部依赖清单

| 依赖 | 用途 | 安装 |
|---|---|---|
| Python ≥ 3.10 | 运行时 | - |
| `mermaid-cli`（npm） | 图表渲染 | `npm i -g @mermaid-js/mermaid-cli` |
| `ffmpeg` | 视频合成 | `apt install ffmpeg` 或随 `imageio-ffmpeg` 自动下载 |
| OpenAI / Anthropic API Key | LLM | 配置到环境变量 |

## 11. 待 Cursor 完成的实现清单

按 **从底向上、可单独验证** 的顺序：

1. `tts/edge_tts_client.py::EdgeTTS.synthesize`（最容易独立验证）
2. `render/mermaid.py::MermaidRenderer.render`（已有骨架，补错误处理与 SVG 路径选项）
3. `llm/openai_client.py::OpenAILLM.generate_storyboard`
4. `llm/anthropic_client.py::AnthropicLLM.generate_storyboard`
5. `video/moviepy_composer.py::MoviePyComposer.compose`
6. `video/ffmpeg_composer.py::FFmpegComposer.compose`（可选）
7. 端到端测试：`tests/test_pipeline_e2e.py`（带 mock）

每完成一项：

- 补充 `tests/test_<module>.py`（mock 外部依赖）
- 跑通 `make lint type test`
- 在 `examples/` 下放一个最小可运行示例
