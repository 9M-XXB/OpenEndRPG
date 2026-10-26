# OpenEndRPG · 完全开放式RPG

**一个"只提供开头"的文字冒险游戏：任务、NPC、事件——后续的一切内容，全部由 LLM 根据你的输入即时生成。**

纯终端交互，无美术、无预设剧情树；剧情长度不设上限，靠世界状态账本与滚动摘要保证长线连贯。

> 想法与调研笔记（中文）：本项目是"完全开放式RPG"想法的最小原型。原型设计沿用三条研究结论：**叙事归 LLM、状态归确定性代码**（Song et al. 2024, [arXiv:2409.06949](https://arxiv.org/abs/2409.06949)）、**两级滚动记忆**（Zhou et al. 2023, [arXiv:2305.13304](https://arxiv.org/abs/2305.13304)）、**常驻 NPC 记忆流**（Park et al. 2023, [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)）。

## 玩法核心

- **开局只有一段序章**：黑曜王座上的大魔王苏醒，村长交给你一柄祖传短剑——之后世界没有任何预设内容。
- **自由输入驱动**：每回合输入任意行动（自然语言），游戏主持人（LLM）生成本回合**后果叙事**与 **2–4 条下一步建议**（建议仅供快速选择，随时可以无视它自由发挥）。
- **一天规则**：除非你明确要求跳时间（如"三天后"），每回合只推进"一天以内"的游戏时间——剧情以天为单位徐徐展开。
- **命运骰**：每回合暗掷一枚 d20（意外挫折 / 平淡进展 / 小机遇 / 重要转机 / 命运大事件五档倾向）注入生成，同样的输入会有不同的走向；`/reroll` 可换骰重演本回合。
- **无限剧情**：世界账本（事实 / NPC / 物品 / 时间）由确定性代码合并入档，滚动剧情摘要 + 最近回合原文注入上下文，每回合自动存档。

## 快速开始

```bash
git clone https://github.com/9M-XXB/OpenEndRPG.git
cd OpenEndRPG
python3 rpg.py        # 首次运行自动进入 API 配置向导
```

依赖：Python 3.10+ 与 `httpx`（`pip install httpx`；可选 `pip install rich` 获得更好的排版，缺失时自动降级为纯文本）。

## 支持的 API（14 预设 × 3 类协议，零 SDK 依赖）

| 协议 | 预设 |
|---|---|
| OpenAI 兼容 | OpenAI / DeepSeek / Kimi(Moonshot) / 智谱 GLM / 通义 Qwen / OpenRouter / Groq / SiliconFlow / **Ollama 本地** / LM Studio 本地 / 自定义端点（vLLM、one-api、中转均可） |
| Anthropic | Claude |
| Google | Gemini |
| 离线 | Mock（免 key，脚本化剧情，用于测试与演示） |

首次运行向导：选服务商 → base_url（回车用默认）→ API key → 模型（自动在线拉取列表选择）→ 测试对话 → 保存到 `config.json`。随时 `python3 rpg.py config` 重新配置。

> **隐私**：API key 只保存在本机 `config.json`（已被 `.gitignore` 排除）；`config.example.json` 是字段模板。

## 游戏内命令

| 命令 | 作用 |
|---|---|
| `/help` | 帮助 |
| `/status` | 查看世界账本（天数/地点/事实/NPC/物品/摘要） |
| `/roll` | 查看上回合命运骰 |
| `/reroll` | 撤销本回合，换骰重演 |
| `/suggestions` | 重显上回合建议 |
| `/save` · `/quit` · `/config` | 手动存档 · 存档退出 · 重配 API |

直接输入 `1`/`2`/`3` 可快速采用上回合建议；其余一切输入都是你的行动。

## 项目结构

```
OpenEndRPG/
├── rpg.py       # 入口：主菜单、API 配置向导
├── engine.py    # 游戏主循环、命令、快照重掷
├── llm.py       # 三类协议客户端、14 预设、SSE 流式、JSON 解析与自修复
├── state.py     # 存档读写、世界账本确定性合并、时间推进
├── prompts.py   # GM 系统规则、序章、命运骰表、上下文组装
├── ui.py        # rich/plain 双模式渲染（打字机效果）
├── config.example.json
└── saves/       # 存档目录（运行时生成，不入库）
```

每回合流程：玩家输入 → 深拷贝快照 → 掷命运骰 → LLM 输出严格 JSON（叙事 + 时间增量 + 状态增量 + 滚动摘要 + 建议，失败自动带错误重试修复）→ **确定性代码**校验并合并状态 → 打字机呈现叙事与建议 → 自动存档。

## 路线图

- [ ] 真实 API 实测与每服务商调优（温度/最大 token）
- [ ] 两段式生成：先定状态、再流式生成叙事（llm.py 已内置 SSE 流式能力）
- [ ] 关键 NPC 常驻记忆（记忆流 + 反思），路人即席生成
- [ ] 生成内容准入管线（筛选/重写循环），对冲小模型任务合格率低的问题
- [ ] 更丰富的表现层（ASCII 场景框、立绘级图像生成）

## 归属

由 ZCode（编码智能体，模型 GLM-5.3-Flash）设计与编写（2026-10）；产品哲学上的近亲：AI Dungeon、1001 Nights、Generative Agents。
