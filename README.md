# ManimTool

> AI 驱动的自动化视频生成工具：
> **LLM（GPT/Claude）输出结构化脚本 → Mermaid 渲染图表 → Edge-TTS 合成语音 → FFmpeg/MoviePy 合成视频。**

## 功能流水线

```
主题 → [LLM] → Storyboard(JSON) → [Mermaid-CLI] → 图片
                                          ↘
                                            [Edge-TTS] → 音频 + 时长
                                          ↗
                                    → [Compose] → 教学视频 mp4
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
manimtool generate --topic "二叉树的中序遍历"
# 产物会输出到 ./output/<时间戳>/<标题>.mp4
```

### 4. 仅调试某一阶段

```bash
manimtool storyboard --topic "快速排序" --output sb.json   # 仅生成脚本
manimtool compose --storyboard sb.json                      # 跳过 LLM，直接合成
```

## 项目结构

```
src/manimtool/
  schemas.py      # 数据契约（Pydantic）
  config.py       # 配置装配
  pipeline.py     # 流水线编排
  cli.py          # CLI 入口
  llm/            # LLM provider（OpenAI / Anthropic）
  render/         # 图表渲染（Mermaid）
  tts/            # 语音合成（Edge-TTS）
  video/          # 视频合成（MoviePy / FFmpeg）
configs/          # 默认 YAML 配置 + 提示词
tests/            # 单元测试
examples/         # 样例 storyboard
docs/ARCHITECTURE.md  # 架构与开发约束
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
