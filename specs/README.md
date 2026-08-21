# BotEro SDD 约束文档体系

## 目的

这些文档是 BotEro 项目开发的**权威参考**。设计目标：

1. **AI 可消费** — 结构化约束、显式规则、代码示例、反模式清单
2. **人类可维护** — 代码变更时同步更新对应规范
3. **单一事实来源** — 消除"只在原作者脑中"的隐式知识

## 使用方式

### 对 AI 开发

修改任何模块前，先查阅对应规范。文档中的 `Constraint:` 章节是硬性规则，`MUST` / `MUST NOT` 不可违反。

### 对人类开发者

- 新功能开发 → 先读 `plugins.md` + `conventions.md`
- 数据库变更 → 先读 `database.md`
- 架构理解 → 先读 `architecture.md`

## 文档地图

| 文档 | 领域 | 何时查阅 |
|------|------|---------|
| [`plugins.md`](plugins.md) | 插件开发契约 | 新增/修改插件 |
| [`conventions.md`](conventions.md) | 编码约定与隐式知识 | 任何开发 |
| [`database.md`](database.md) | 数据库 Schema 与访问 | 数据库变更 |
| [`architecture.md`](architecture.md) | 系统架构与事件流 | 理解系统 |
| [`onebot-protocol.md`](onebot-protocol.md) | OneBot v11 协议 | 消息收发 |
| [`plugin-catalog.md`](plugin-catalog.md) | 全部插件注册表 | 查重、了解现有功能 |
| [`llm-subsystem.md`](llm-subsystem.md) | LLM 子系统（已弃用） | 了解遗留设计，勿新增依赖 |
| [`web-gallery.md`](web-gallery.md) | Web 应用（单进程 webapp：11 模块 + 全站登录门控） | Web 端开发 |
| [`image-generation.md`](image-generation.md) | 图片生成 | 热度图/档案卡 |
| [`timeline-protocol.md`](timeline-protocol.md) | 社区时间线事件协议 | 时间线事件发送/接收 |

> `llms.txt` 不是 spec：它是 LLOneBot 上游文档索引的镜像（编辑 OneBot 协议代码前按 `onebot-protocol.md` §权威上游文档 fetch 对应单页）。

## 阅读顺序（新开发者）

1. [`CLAUDE.md`](../CLAUDE.md) — 项目概述（快速入门）
2. [`architecture.md`](architecture.md) — 理解系统结构
3. [`conventions.md`](conventions.md) — 了解编码规则
4. [`plugins.md`](plugins.md) — 学会写插件
5. 按需阅读域特定文档

## 维护规则

### 代码-规范耦合

**代码变更必须在同一 commit 中更新对应规范：**

| 变更类型 | 需更新的规范 |
|---------|------------|
| 新增插件 | `plugin-catalog.md` |
| 修改插件行为 | `plugins.md`（若契约变化） |
| 新增/修改指令 | `plugins/menu/bot_menu_text.py` + `plugin-catalog.md` |
| 数据库表/列变更 | `database.md` |
| 新的编码约定 | `conventions.md` |
| 修改事件流/架构 | `architecture.md` |
| 新增依赖 | `conventions.md`（依赖章节） |

### 规范格式约定

- 每条约束以 `## Constraint:` 开头
- `MUST` / `MUST NOT` 表示硬性要求
- `CAN` / `SHOULD` 表示建议
- 代码示例使用 fenced code blocks 标注语言
- 表格用于参考数据，列表用于规则
- 每个文件头包含交叉引用和最后更新日期
- 反模式以 `## 反模式` 或 `DO NOT` 明确标注

### 审查检查清单

提交 PR 前确认：
- [ ] 是否修改了插件行为？→ 更新 `plugins.md` 或 `plugin-catalog.md`
- [ ] 是否修改了数据库？→ 更新 `database.md`
- [ ] 是否引入了新模式？→ 更新 `conventions.md`
- [ ] 是否修改了消息格式？→ 更新 `onebot-protocol.md`
- [ ] 是否新增了指令？→ 更新 `BOT_MENU_TEXT`

## AI-First 设计原则

这些文档在设计时遵循以下原则：

1. **约束显式化** — AI 无法推断隐式规则，每条规则必须明确写出
2. **反模式可见** — 列出常见错误（而非期望 AI 从上下文中学习）
3. **结构化优先** — 表格和列表优于叙述段落
4. **可搜索** — 一致的章节标题（`Constraint:`, `MUST`, `MUST NOT`）便于 grep
5. **代码示例** — 展示正确做法，而非仅描述
6. **交叉引用** — 每个文档链接到相关文档，形成知识图谱
