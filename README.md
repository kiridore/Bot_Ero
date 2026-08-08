# BotEro（小埃同学）

基于 **OneBot v11 协议** 的 QQ 群聊机器人（WebSocket 连接 NapCat / Lagrange / LLOneBot 等服务端），事件驱动 + 插件架构；附带一个单进程 FastAPI Web 应用（`webapp`）承载导航主页与 6 个功能分区。

## 运行

```bash
python main.py          # 机器人主进程（ws://127.0.0.1:3001）
python -m webapp        # Web 应用（默认 http://0.0.0.0:8765）
```

Web 端单一根域按路径分区（Caddy 全量反代 8765）：

| 路径 | 内容 |
|------|------|
| `/` | 导航主页（`webapp/homepage/`） |
| `/gallery` `/guestbook` `/profile` `/trpg` `/alarms` `/activities` | 6 个功能分区 |
| `/api/*` `/static/*` `/shared/*` `/thumb/*` `/media/*` `/archive/*` | API / 静态 / 媒体（根路径） |

## 结构

```
core/       bot 与 web 共享核心（config/auth/db/trpg/web static…）
plugins/    43 个已注册插件（每插件一个文件夹）
webapp/     Web 单进程入口 + 6 功能模块 + homepage/ + static/
scripts/    systemd unit（botero-web.service）、Caddyfile、服务脚本
specs/      权威约束文档（SDD）
kb/ + KNOWLEDGE_BASE.md   知识库
docs/       部署文档等
test/       ad-hoc 测试脚本（python test/<name>.py）
```

## 依赖

- 机器人：`websocket-client`、`requests`、`Pillow`
- Web：`webapp/requirements.txt`（fastapi、uvicorn、requests、Pillow、python-multipart）

## 文档

- [`CLAUDE.md`](CLAUDE.md) — 项目概述与关键约定（新开发者入口）
- [`specs/`](specs/) — 权威约束规范（改代码前必读对应规范）
- [`KNOWLEDGE_BASE.md`](KNOWLEDGE_BASE.md) — 知识库总索引（`kb/` 分主题）
- [`docs/web-apps-deployment.md`](docs/web-apps-deployment.md) — Web 端 VPS 部署
