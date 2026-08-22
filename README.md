# BotEro（小埃同学）

基于 **OneBot v11 协议** 的 QQ 群聊机器人（WebSocket 连接 NapCat / Lagrange / LLOneBot 等服务端），事件驱动 + 插件架构；附带单进程 FastAPI Web 应用（`webapp`），在单一根域 `littlero.tech` 下按路径提供时间线社区主页与图库、议事厅、周报等 11 个功能模块，全站登录门控。

## 功能概览

**群聊机器人（47 个已注册插件，按功能包划分）**

| 功能包 | 内容 |
|--------|------|
| 基础包 | 打卡（含图片）、补卡、撤回打卡、周/全量打卡统计、年度档案卡、积分排行榜 |
| 基础扩展包 | 抽奖/抽卡、积分商店、全员发币、称号系统、周常任务、仙人彩 |
| 休闲娱乐 | FF14 新闻推送、群闹钟、骰子、塔罗占卜、随机参考图、召唤应答 |
| 匿名游戏 | 谁是卧底（群聊建房间，私聊匿名发言/投票） |
| 跑团 | DND5E 车卡（网页端编辑）、万能骰子、跑团记录 |
| 群管理工具 | 群精华、@全体转发、代撤回、群头衔 |
| 系统 | 菜单、插件/功能包管理、系统状态、自动更新、自动备份、好友自动同意、开机播报/欢迎消息、消息日志、兑换码、网页登录密钥、群活动、议事厅通知、小埃周报 |

**Web 应用（单进程 `webapp`）**：时间线社区主页 + 打卡图库、个人中心（主页/打卡/商店/称号/设置）、跑团车卡、留言簿、闹钟、活动归档、直播间（SRS HTTP-FLV）、议事厅（长文/公告/投票/评论）、工具箱、小埃周报；全站登录门控。

## 快速开始

### 机器人

```bash
pip install -r requirements.txt                # 依赖（websocket-client / requests / Pillow / GitPython / jieba 等）
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
| `littlero.tech/` | 时间线社区主页（登录可见；侧边栏功能导航 + 无限滚动时间线，入口维护于 `webapp/timeline/entries.json`） |
| `littlero.tech/gallery` | 打卡图库（瀑布流 + 缩略图/原图） |
| `littlero.tech/guestbook` | 留言簿 |
| `littlero.tech/profile` | 个人中心（`/profile/checkin` 打卡、`/profile/shop` 商店、`/profile/settings` 设置） |
| `littlero.tech/trpg` | 跑团车卡（`/trpg/char/{uid}/{cid}` 角色查看） |
| `littlero.tech/alarms` | 闹钟 |
| `littlero.tech/activities` | 活动归档（`/activities/{id}` 详情） |
| `littlero.tech/live` | 直播间（SRS HTTP-FLV，mpegts.js 播放；观众列表，登录显示昵称） |
| `littlero.tech/forum` | 议事厅（`/forum/{id}` 详情、`/forum/new` 发帖、`/forum/tags` 标签；长文/公告/投票/评论） |
| `littlero.tech/tools` | 工具箱（链接收藏卡片） |
| `littlero.tech/weekly` | 小埃周报（最新期重定向，`/weekly/{week_key}` 报纸详情页） |
| `littlero.tech/login` | 登录页（门控白名单内，未登录可访问） |
| `littlero.tech/api/*` | API（`/api/auth/login`、`/api/checkins`、`/api/me/*` 等，全局唯一） |
| `littlero.tech/static/*` `/shared/*` | 静态资源 |
| `littlero.tech/thumb/*` `/media/*` `/archive/*` | 打卡图 / 活动作品媒体 |

登录：全站登录门控——白名单（`/login`、`/api/auth/login`、静态与 `/api/timeline/events*`）外，未登录访问页面 302 → `/login?next=…`、API/媒体 401；密钥即 token（HMAC），向机器人私聊 `/图库密钥` 获取，凭证为 `Authorization: Bearer` 头或根域 cookie `botero_key`，全站单 origin 共享登录态。

## 架构

```
OneBot 服务端 ──WebSocket──> main.py ──> 每事件新线程 → plugin_pool 遍历 plugin_registry
                                              └─ plugin.match() → plugin.handle()

littlero.tech ──Caddy 反代──> webapp（单进程 FastAPI, 8765）
   ├── / 时间线社区主页（登录可见，webapp/static/timeline.html）
   ├── 11 个功能模块（webapp/gallery|guestbook|profile|trpg|alarms|activities|live|timeline|forum|tools|weekly，各含 APIRouter）
   └── /api /static /shared /thumb /media /archive（根路径）

core/（共享层）── bot 与 webapp 共用：config / auth / database_manager / onebot_client /
                 character_store / user_settings / trpg / web/static / gen_image
data.db（SQLite WAL）── bot 与 webapp 两个写者
```

要点：
- bot 进程无 `async`/`await`，同步 + threading 模型（webapp/FastAPI 的路由/中间件用 `async`）
- 打卡周边界为周一 08:00（`core/utils.get_monday_to_monday`）
- 多 worker 不可用（多进程 SQLite 写竞争），webapp 保持单进程单 worker

## 目录结构

```
core/        bot 与 web 共享核心（config/auth/db/trpg/character_store/user_settings/web/static…）
plugins/     47 个已注册插件（每插件一个文件夹，activity/redeem_shop/weekly_quest 内含多个插件）
webapp/      Web 单进程入口：app.py（认证+时间线主页+router include+mount）、11 功能模块、
             timeline/（Event Server + entries.json）、static/（静态文件）、requirements.txt
scripts/     systemd unit（botero-web.service）、Caddyfile、botero-services.sh、
             botero.env（环境变量单一来源，bot 启动加载、webapp 经 systemd EnvironmentFile 注入）
specs/       权威约束文档（SDD，改代码前必读对应规范）
kb/          知识库分主题（QUICK_REFERENCE / PLUGIN_CATALOG / GAMEPLAY / CONVENTIONS /
             OPERATIONS / DATABASE）
docs/        部署文档（web-apps-deployment.md 等）
test/        ad-hoc 测试脚本（python test/<name>.py）
server_data/ 运行时数据（record_images / thumb_cache / trpg_chars / user_settings / activity_archive）
```

## 配置

- 硬编码值（无配置文件）：WS `ws://127.0.0.1:3001` / token `123456`（`main.py`）、默认群 `296470819`、超管 `[1057613133]`、Bot QQ `3915014383`（`core/`）
- 环境变量：全部 `BOTERO_*`（定义于 `core/config.py`，部署值单一来源 `scripts/botero.env`），关键项：`BOTERO_DB_PATH`、`BOTERO_AUTH_SALT`、`BOTERO_GALLERY_HOST/PORT`、`BOTERO_IMAGE_ROOT`、`BOTERO_ONEBOT_HTTP/TOKEN`、`BOTERO_GROUP_ID`
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
