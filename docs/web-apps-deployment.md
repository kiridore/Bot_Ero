# 网页子应用部署文档（Caddy + systemd + DNS）

本文档是 BotEro 网页子应用在 VPS 上的部署参考，覆盖全部 6 个子域：`gallery`、`guestbook`、`profile`、`trpg`、`alarms`、`activities`。

## 1. DNS

6 个子域 A 记录指向 VPS 公网 IP（`gallery` 保留现有记录，其余 5 个为新增）：

| 子域 | 记录类型 | 说明 |
|------|---------|------|
| `gallery.littlero.com` | A | 已有记录，无需改动 |
| `guestbook.littlero.com` | A | 新增 |
| `profile.littlero.com` | A | 新增 |
| `trpg.littlero.com` | A | 新增 |
| `alarms.littlero.com` | A | 新增 |
| `activities.littlero.com` | A | 新增 |

若其他服务（狼人杀、MC 地图等）也部署在同机，照此模式追加 `@` 子域即可。

## 2. Caddyfile

每段配置一个子域反代到对应本地端口：

```caddyfile
gallery.littlero.com {
	reverse_proxy 127.0.0.1:8765
}

guestbook.littlero.com {
	reverse_proxy 127.0.0.1:8766
}

profile.littlero.com {
	reverse_proxy 127.0.0.1:8767
}

trpg.littlero.com {
	reverse_proxy 127.0.0.1:8768
}

alarms.littlero.com {
	reverse_proxy 127.0.0.1:8769
}

activities.littlero.com {
	reverse_proxy 127.0.0.1:8770
}
```

> **注意**：拆分后旧路径（如 `/guestbook/`、`/trpg/` 等子路径）**不再重定向**，直接失效。入口一律走各子域首页。

## 3. systemd

每个子应用一个 unit。以 `guestbook.service` 为完整示例：

```ini
[Unit]
Description=BotEro Guestbook
After=network.target

[Service]
WorkingDirectory=/opt/BotEro
Environment=BOTERO_DB_PATH=/opt/BotEro/data.db
Environment=BOTERO_AUTH_SALT=<与图库一致的盐值>
Environment=BOTERO_GALLERY_PORT=8766
ExecStart=/usr/bin/python3 -m guestbook
Restart=always

[Install]
WantedBy=multi-user.target
```

其余 5 个按端口/模块名类推（仅改 Description、端口环境变量、ExecStart 模块名）：

| 服务 | ExecStart | BOTERO_GALLERY_PORT | 说明 |
|------|-----------|---------------------|------|
| `guestbook` | `python3 -m guestbook` | 8766 | 完整示例见上 |
| `profile` | `python3 -m profile` | 8767 | |
| `trpg` | `python3 -m trpg` | 8768 | |
| `alarms` | `python3 -m alarms` | 8769 | |
| `activities` | `python3 -m activities` | 8770 | |
| `checkin_gallery` | `python3 -m checkin_gallery` | 8765 | 保留原名；Task 12 图库改名后为 `python3 -m gallery` |

部署步骤：

```bash
cp guestbook.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now guestbook
```

## 4. 环境变量清单

全部 `BOTERO_*` 变量（定义于 `core/config.py`，bot 与全部子应用共用）：

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `BOTERO_DB_PATH` | `<仓库>/data.db` | SQLite 数据库路径 |
| `BOTERO_IMAGE_ROOT` | `<仓库>/server_data/record_images` | 打卡图片存储目录 |
| `BOTERO_TRPG_CHARS_ROOT` | `<仓库>/server_data/trpg_chars` | TRPG 角色卡目录 |
| `BOTERO_USER_SETTINGS_ROOT` | `<仓库>/server_data/user_settings` | 用户设置目录 |
| `BOTERO_ACTIVITY_ROOT` | `<仓库>/server_data/activity_archive` | 活动存档目录 |
| `BOTERO_GALLERY_HOST` | `0.0.0.0` | 子应用监听地址 |
| `BOTERO_GALLERY_PORT` | `8765` | 子应用监听端口（每服务按上表设置） |
| `BOTERO_ONEBOT_HTTP` | `http://192.168.0.103:3000` | OneBot HTTP 地址，用于拉取 QQ 昵称 |
| `BOTERO_ONEBOT_TOKEN` | `123456` | OneBot HTTP 访问令牌 |
| `BOTERO_GROUP_ID` | `296470819` | 默认群号 |
| `BOTERO_THUMB_CACHE` | `<仓库>/server_data/thumb_cache` | 缩略图缓存目录 |
| `BOTERO_THUMB_MAX_WIDTH` | `480` | 缩略图最大宽度 |
| `BOTERO_THUMB_MAX_HEIGHT` | `720` | 缩略图最大高度 |
| `BOTERO_THUMB_QUALITY` | `82` | 缩略图 JPEG 质量 |
| `BOTERO_AUTH_SALT` | `BotEro-Gallery-ChangeMe` | 登录密钥盐（生产环境必须修改，且各子应用保持一致） |
| `BOTERO_CHECKIN_MAX_IMAGES` | `9` | 网页打卡单次最大图片数 |
| `BOTERO_CHECKIN_MAX_BYTES` | `10485760` | 网页打卡单图最大字节数 |

## 5. 导航主页

`homepage/entries.json` 是主页（入口页）**唯一**的入口维护点：增删子应用入口、改 `url`、改展示名称/描述/徽标都在此文件完成，无需改动 `index.html`。子应用自身入口链接（图库的"留言簿"等）也一律指向对应子域。

## 6. 启动顺序与验证

1. 首次部署：`git clone` 仓库到 VPS（如 `/opt/BotEro`），配置 DNS 与 Caddyfile；
2. 更新代码：`git pull` 后重启受影响服务；
3. 启动：`systemctl start guestbook profile trpg alarms activities checkin_gallery`（或逐个 `enable --now`）；
4. 验证：依次访问 6 个子域根路径，均应返回 HTTP 200：
   `curl -s -o /dev/null -w "%{http_code}\n" https://gallery.littlero.com`（每个子域一次）。

## 7. 已知限制

- **登录状态按域名隔离**：登录态存于浏览器 localStorage，按域名隔离。首次访问每个子域都需重新登录，属预期行为。
- **SQLite 多进程**：全部子应用共享 `data.db`（WAL 模式支持多进程并发读写），但高并发写场景（如打卡高峰期）仍可能偶发 `database is locked`，出现时重试即可。
