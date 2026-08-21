# 网页应用部署文档（Caddy + systemd + DNS）

本文档是 BotEro 网页端在 VPS 上的部署参考。11 个功能分区（`gallery`、`guestbook`、`profile`、`trpg`、`alarms`、`activities`、`live`、`timeline`、`forum`、`tools`、`weekly`）由**单进程 `webapp`**（端口 8765）承载，全部挂在**单一根域 `littlero.tech`** 下，按**路径分区**访问，不再需要任何子域。**全站登录门控（1.18.0 起）**：除白名单（`/login`、`/api/auth/login`、`/static`、`/shared`、`/api/timeline/events*`）外，未登录访问页面一律 302 重定向到 `/login?next=…`，API 与图片媒体返回 401；凭证支持 `Authorization: Bearer <key>` 头或根域 cookie `botero_key` 任一。

## 1. URL 方案

| 分区 | 路径 |
|------|------|
| 时间线主页 | `/`（登录可见；`webapp/static/timeline.html`，侧边栏导航数据 `webapp/timeline/entries.json`） |
| 议事厅 | `/forum` `/forum/{id}` `/forum/new` `/forum/tags`（长文/公告/投票/评论；详见 `docs/archive/superpowers/specs/2026-08-10-forum-design.md`） |
| 图库 | `/gallery` |
| 留言簿 | `/guestbook` |
| 个人中心 | `/profile`（`/profile/checkin` `/profile/shop` `/profile/settings`） |
| 跑团 | `/trpg`（`/trpg/char/{user_id}/{char_id}`） |
| 闹钟 | `/alarms` |
| 活动 | `/activities`（`/activities/{activity_id}`） |
| 直播 | `/live`（SRS HTTP-FLV 播放） |
| 工具箱 | `/tools`（链接收藏卡片） |
| 登录页 | `/login`（门控白名单内，未登录可访问；`next` 参数记住来源） |
| 周报 | `/weekly`（最新期重定向）`/weekly/{week_key}`（报纸详情页；API 为 `/api/weekly`） |
| API/静态/媒体 | `/api/*` `/static/*` `/shared/*` `/thumb/*` `/media/*` `/archive/*`（根路径，全局唯一） |

根域 `/` 为时间线社区主页（登录可见；`webapp/static/timeline.html`，数据 API `GET /api/timeline` 需登录密钥）。单 origin 下登录态天然共享（同源 localStorage），页面间跳转均为同源相对路径。

## 2. DNS

**仅需 `littlero.tech` 的 A 记录**（已有）。拆分阶段配置的 6 个子域 A 记录（`gallery`/`guestbook`/`profile`/`trpg`/`alarms`/`activities`）**可以删除**，不再被使用。

## 3. Caddyfile

现成配置文件：`scripts/Caddyfile`（仓库内，部署路径 `/home/dore/onebot/Bot_Ero`）。根域**全部流量**（导航主页、各分区页面、API/静态/媒体）统一反代到 `webapp`，由应用自行路由：

```caddyfile
littlero.tech {
	reverse_proxy 127.0.0.1:8765
}
```

> **注意**：旧子域 URL（如 `https://gallery.littlero.tech`）**不做重定向**，直接失效；书签/群链接统一改为 `https://littlero.tech/<分区>`。

## 4. systemd

单 unit 模板已入库（`scripts/botero-web.service`），部署路径已配为 `/home/dore/onebot/Bot_Ero`：

```ini
[Unit]
Description=BotEro Web (gallery/profile/trpg/guestbook/alarms/activities)
After=network.target

[Service]
WorkingDirectory=/home/dore/onebot/Bot_Ero
EnvironmentFile=/home/dore/onebot/Bot_Ero/scripts/botero.env
Environment=BOTERO_DB_PATH=/home/dore/onebot/Bot_Ero/data.db
Environment=BOTERO_GALLERY_PORT=8765
ExecStart=/usr/bin/python3 -m webapp
Restart=always

[Install]
WantedBy=multi-user.target
```

> **盐值单一来源**：`BOTERO_AUTH_SALT` 经 `EnvironmentFile` 从 `scripts/botero.env` 注入（bot 的 `main.py` 启动时也加载同一文件）。bot 生成密钥与 webapp 验证密钥**必须使用同一盐值**，改盐只改这一个文件。

部署步骤（模板已在 `scripts/`，确认盐值后安装）：

```bash
cd /home/dore/onebot/Bot_Ero/scripts
cp botero-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now botero-web
```

> 生成随机盐：`openssl rand -base64 24`。
>
> **换盐无感迁移**：若此前已用旧盐发过密钥，把旧盐值追加到 `scripts/botero.env` 的 `BOTERO_AUTH_SALT_OLD`（逗号分隔可多个），旧密钥继续有效，无需群友重新 `/图库密钥`；之后新发的密钥用新盐。

### 一键启停脚本

仓库提供 `scripts/botero-services.sh`（Ubuntu，需 root 或 sudo），管理 `botero-web`：

```bash
./scripts/botero-services.sh start    # 启动
./scripts/botero-services.sh stop     # 停止
./scripts/botero-services.sh restart  # 重启
./scripts/botero-services.sh status   # 查看状态
```

## 5. 环境变量清单

全部 `BOTERO_*` 变量（定义于 `core/config.py`，bot 与 webapp 共用；例外 `BOTERO_LIVE_FLV_URL` 定义于 `webapp/live/app.py`）：

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `BOTERO_DB_PATH` | `<仓库>/data.db` | SQLite 数据库路径 |
| `BOTERO_IMAGE_ROOT` | `<仓库>/server_data/record_images` | 打卡图片存储目录 |
| `BOTERO_TRPG_CHARS_ROOT` | `<仓库>/server_data/trpg_chars` | TRPG 角色卡目录 |
| `BOTERO_USER_SETTINGS_ROOT` | `<仓库>/server_data/user_settings` | 用户设置目录 |
| `BOTERO_ACTIVITY_ROOT` | `<仓库>/server_data/activity_archive` | 活动存档目录 |
| `BOTERO_GALLERY_HOST` | `0.0.0.0` | webapp 监听地址 |
| `BOTERO_GALLERY_PORT` | `8765` | webapp 监听端口 |
| `BOTERO_LIVE_FLV_URL` | `https://live.littlero.tech/live/livestream.flv` | 直播间 FLV 流地址（状态探测用）。webapp 与 SRS 同机时设为 `http://127.0.0.1:18080/live/livestream.flv`（直连本机，避免公网回环探测超时）；浏览器播放始终走公网地址（live.js 内置，不受此变量影响） |
| `BOTERO_ONEBOT_HTTP` | `http://192.168.0.103:3000` | OneBot HTTP 地址，用于拉取 QQ 昵称 |
| `BOTERO_ONEBOT_TOKEN` | `123456` | OneBot HTTP 访问令牌 |
| `BOTERO_GROUP_ID` | `296470819` | 默认群号 |
| `BOTERO_THUMB_CACHE` | `<仓库>/server_data/thumb_cache` | 缩略图缓存目录 |
| `BOTERO_THUMB_MAX_WIDTH` | `480` | 缩略图最大宽度 |
| `BOTERO_THUMB_MAX_HEIGHT` | `720` | 缩略图最大高度 |
| `BOTERO_THUMB_QUALITY` | `82` | 缩略图 JPEG 质量 |
| `BOTERO_AUTH_SALT` | `BotEro-Gallery-ChangeMe` | 登录密钥盐。**单一来源 `scripts/botero.env`**：bot（main.py 启动加载）与 webapp（systemd EnvironmentFile）共用，改盐只改该文件；生产建议改为随机值 |
| `BOTERO_AUTH_SALT_OLD` | 空 | 历史盐列表（逗号分隔，写于 `scripts/botero.env`）。换盐时把旧盐加进来，旧密钥继续有效，实现无感迁移 |
| `BOTERO_CHECKIN_MAX_IMAGES` | `9` | 网页打卡单次最大图片数 |
| `BOTERO_CHECKIN_MAX_BYTES` | `10485760` | 网页打卡单图最大字节数 |
| `BOTERO_FORUM_IMAGES_ROOT` | `<仓库>/server_data/forum_images` | 议事厅正文图片存储目录（公开读取，uuid 文件名不可枚举） |
| `BOTERO_FORUM_IMAGE_MAX_BYTES` | `10485760` | 议事厅正文单图最大字节数（JPG/PNG/WebP/GIF） |
| `BOTERO_TIMELINE_URL` | `http://127.0.0.1:8765` | Event Server 基地址（bot 插件发送时间线事件的目标） |
| `BOTERO_EVENT_TOKEN` | `BotEro-Timeline-ChangeMe` | 系统间事件令牌（bot 发送与 webapp 校验共用；**单一来源 `scripts/botero.env`**，生产建议改为随机值） |
| `BOTERO_MESSAGE_LOG_DB_PATH` | `<仓库>/server_data/message_log.db` | 群消息日志独立库路径（周报数据源，永久保留） |
| `BOTERO_WEB_BASE_URL` | `https://littlero.tech` | 周报群通知链接的 Web 基址 |
| `BOTERO_WEEKLY_NOTIFY` | `0` | 周报群通知开关（`1` 开启；首周测试期默认关闭） |

> 旧变量 `BOTERO_GALLERY_URL`（图库域基地址）已删除：单 origin 后媒体 URL 为同源根相对路径，无需跨域基地址。

时间线主页文件位于 `webapp/static/`（`timeline.html` + `timeline.js` + `timeline.css`），由 `webapp` 在根路径 `/` 提供，无需 Caddy 单独托管，**登录后可见**（数据 API `GET /api/timeline` 需登录密钥，未登录 401）。侧边栏功能导航数据源为 `webapp/timeline/entries.json`，是主页**唯一**的入口维护点：增删分区入口、改 `url`、改展示名称/描述都在此文件完成（含议事厅）。BotEro 分区入口的 `url` 为同源路径（`/gallery`、`/profile` 等）；第三方服务（狼人杀、MC 等）仍为完整外部 URL。侧边栏提供与全站一致的登录状态（`auth.js`）。

## 7. 事件发送方接入

事件发送方接入：bot 插件经 `core/timeline_client.py` 发送（`BOTERO_TIMELINE_URL` + `BOTERO_EVENT_TOKEN`，见第 5 节环境变量）；v1 发送方为打卡与周常任务，回滚联动删除。协议见 `specs/timeline-protocol.md`。

## 8. 启动顺序与验证

1. 首次部署：`git clone` 仓库到 VPS（如 `/home/dore/onebot/Bot_Ero`），配置 DNS 与 Caddyfile；
2. 更新代码：`git pull` 后重启服务；
3. 启动：`./scripts/botero-services.sh start`（首次部署先 `enable --now botero-web` 设为开机自启）；
4. 验证（**全站登录门控**下未登录应得到 302 → `/login`，带凭证应 200）：
   ```bash
   # 未登录：主页与各分区页面应返回 302（重定向到 /login）
   curl -s -o /dev/null -w "主页(未登录): %{http_code}\n" https://littlero.tech/
   for p in /gallery /guestbook /profile /trpg /alarms /activities /forum /tools /weekly; do
     echo "$p: $(curl -s -o /dev/null -w '%{http_code}' https://littlero.tech$p)"
   done
   # 带密钥（QQ 号 + 盐 → HMAC，见 /图库密钥）：应返回 200
   curl -s -o /dev/null -w "主页(已登录): %{http_code}\n" -H "Authorization: Bearer <登录密钥>" https://littlero.tech/
   ```
   `ps` 中 uvicorn 应只剩 1 个 web 进程。

## 9. 已知限制

- **单 origin 登录共享**：全部页面同源，登录态存于该 origin 的 localStorage，根域 cookie `botero_key` 是页面门控的导航凭据（页面跳转带不了 `Authorization` 头），任一分区登录后其余分区免重复登录；页内 fetch 401 由 `/shared/auth.js` 全局拦截并跳回 `/login`。
- **SQLite 两写者**：`data.db` 仅剩 bot（`main.py`）与 webapp 两个写者，均为 WAL + `busy_timeout=5000`；高并发写场景（如打卡高峰期）仍可能偶发 `database is locked`，出现时重试即可。
