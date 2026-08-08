# BotEro（小埃同学）

基于 **OneBot v11 协议** 的 QQ 群聊机器人（WebSocket 连接 NapCat / Lagrange / LLOneBot 等服务端），事件驱动 + 插件架构；附带单进程 FastAPI Web 应用（`webapp`），在单一根域 `littlero.tech` 下按路径提供导航主页与 6 个功能分区。

## 功能概览

**群聊机器人（43 个已注册插件，按功能包划分）**

| 功能包 | 内容 |
|--------|------|
| 基础包 | 打卡（含图片）、补卡、撤回打卡、周/全量打卡统计、年度档案卡、积分排行榜 |
| 基础扩展包 | 抽奖/抽卡、积分商店、全员发币、称号系统、周常任务、仙人彩 |
| 休闲娱乐 | FF14 新闻推送、群闹钟、骰子、塔罗占卜、随机参考图、召唤应答 |
| 匿名游戏 | 谁是卧底（群聊建房间，私聊匿名发言/投票） |
| 跑团 | DND5E 车卡（网页端编辑）、万能骰子、跑团记录 |
| 群管理工具 | 群精华、@全体转发、代撤回、群头衔 |
| 系统 | 菜单、插件/功能包管理、系统状态、自动更新、自动备份、好友自动同意 |

**Web 应用（单进程 `webapp`）**：导航主页 + 打卡图库、个人中心（主页/打卡/商店/称号/设置）、跑团车卡、留言簿、闹钟、活动归档、直播间（SRS HTTP-FLV）。

## 快速开始

### 机器人

```bash
pip install websocket-client requests Pillow   # 依赖
python main.py                                 # 连接 ws://127.0.0.1:3001
```

### Web 应用

```bash
pip install -r webapp/requirements.txt
python -m webapp                               # 默认 http://0.0.0.0:8765
```

## Web 访问结构

单一根域 `littlero.tech`，主页在根路径，各服务按路径分区（Caddy 全量反代 8765，无子域）：

| 访问地址 | 内容 |
|----------|------|
| `littlero.tech/` | 导航主页（卡片入口维护于 `webapp/homepage/entries.json`） |
| `littlero.tech/gallery` | 打卡图库（瀑布流 + 缩略图/原图） |
| `littlero.tech/guestbook` | 留言簿 |
| `littlero.tech/profile` | 个人中心（`/profile/checkin` 打卡、`/profile/shop` 商店、`/profile/settings` 设置） |
| `littlero.tech/trpg` | 跑团车卡（`/trpg/char/{uid}/{cid}` 角色查看） |
| `littlero.tech/alarms` | 闹钟 |
| `littlero.tech/activities` | 活动归档（`/activities/{id}` 详情） |
| `littlero.tech/live` | 直播间（SRS HTTP-FLV，flv.js 播放） |
| `littlero.tech/api/*` | API（`/api/auth/login`、`/api/checkins`、`/api/me/*` 等，全局唯一） |
| `littlero.tech/static/*` `/shared/*` | 静态资源 |
| `littlero.tech/thumb/*` `/media/*` `/archive/*` | 打卡图 / 活动作品媒体 |

登录：密钥即 token（HMAC），向机器人私聊 `/图库密钥` 获取，全站单 origin 共享登录态。

## 架构

```
OneBot 服务端 ──WebSocket──> main.py ──> 每事件新线程 → plugin_pool 遍历 plugin_registry
                                              └─ plugin.match() → plugin.handle()

littlero.tech ──Caddy 反代──> webapp（单进程 FastAPI, 8765）
   ├── / 主页（webapp/homepage/）
   ├── 7 个功能模块（webapp/gallery|guestbook|profile|trpg|alarms|activities|live，各含 APIRouter）
   └── /api /static /shared /thumb /media /archive（根路径）

core/（共享层）── bot 与 webapp 共用：config / auth / database_manager / onebot_client /
                 character_store / user_settings / trpg / web/static / gen_image
data.db（SQLite WAL）── bot 与 webapp 两个写者
```

要点：
- 无 `async`/`await`，同步 + threading 模型
- 打卡周边界为周一 08:00（`core/utils.get_monday_to_monday`）
- 多 worker 不可用（多进程 SQLite 写竞争），webapp 保持单进程单 worker

## 目录结构

```
core/        bot 与 web 共享核心（config/auth/db/trpg/character_store/user_settings/web/static…）
plugins/     43 个已注册插件（每插件一个文件夹）
webapp/      Web 单进程入口：app.py（认证+主页+router include+mount）、7 功能模块、
             homepage/（导航主页）、static/（25 个静态文件）、requirements.txt
scripts/     systemd unit（botero-web.service）、Caddyfile、botero-services.sh
specs/       权威约束文档（SDD，改代码前必读对应规范）
kb/          知识库分主题（QUICK_REFERENCE / PLUGIN_CATALOG / GAMEPLAY / CONVENTIONS /
             OPERATIONS / DATABASE）
docs/        部署文档（web-apps-deployment.md 等）
test/        ad-hoc 测试脚本（python test/<name>.py）
server_data/ 运行时数据（record_images / thumb_cache / trpg_chars / user_settings / activity_archive）
```

## 配置

- 硬编码值（无配置文件）：WS `ws://127.0.0.1:3001` / token `123456`（`main.py`）、默认群 `296470819`、超管 `[1057613133]`、Bot QQ `3915014383`（`core/`）
- 环境变量：全部 `BOTERO_*`（`core/config.py` 单一来源），关键项：`BOTERO_DB_PATH`、`BOTERO_AUTH_SALT`、`BOTERO_GALLERY_HOST/PORT`、`BOTERO_IMAGE_ROOT`、`BOTERO_ONEBOT_HTTP/TOKEN`、`BOTERO_GROUP_ID`
- 部署：见 [`docs/web-apps-deployment.md`](docs/web-apps-deployment.md)（systemd 单 unit + Caddy 反代）

## 测试

```bash
python test/test_activity_commands.py   # 活动系统
node test/test_auth_cookie.js           # Web 登录态（auth.js）
node test/test_nav_render.js            # 站点导航条渲染（nav.js）
# …其余见 test/ 目录
```

## 文档

- [`CLAUDE.md`](CLAUDE.md) — 项目概述与关键约定（新开发者入口）
- [`AGENTS.md`](AGENTS.md) — 代理/自动化操作约束
- [`specs/`](specs/) — 权威约束规范（plugins / web-gallery / database / architecture…）
- [`KNOWLEDGE_BASE.md`](KNOWLEDGE_BASE.md) — 知识库总索引（`kb/` 分主题）
