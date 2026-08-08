# 网页子应用部署文档（Caddy + systemd + DNS）

本文档是 BotEro 网页端在 VPS 上的部署参考。6 个子域（`gallery`、`guestbook`、`profile`、`trpg`、`alarms`、`activities`）由**单进程** `webapp` 承载：1 个 uvicorn 进程注册 6 个 APIRouter，页面 `/` 按 Host 头分发，Caddy 统一反代到 8765。

## 1. DNS

6 个子域 A 记录指向 VPS 公网 IP：

| 子域 | 记录类型 | 说明 |
|------|---------|------|
| `gallery.littlero.tech` | A | 已有记录，无需改动 |
| `guestbook.littlero.tech` | A | |
| `profile.littlero.tech` | A | |
| `trpg.littlero.tech` | A | |
| `alarms.littlero.tech` | A | |
| `activities.littlero.tech` | A | |

若其他服务（狼人杀、MC 地图等）也部署在同机，照此模式追加 `@` 子域即可。

## 2. Caddyfile

现成配置文件：`scripts/Caddyfile`（仓库内，部署路径 `/home/dore/onebot/Bot_Ero`）。导航主页为根域 `littlero.tech` 静态托管，6 个子域**统一反代到单进程 `127.0.0.1:8765`**（Caddy `reverse_proxy` 默认透传原 Host 头，`webapp` 按 Host 分发首页）：

```caddyfile
littlero.tech {
	root * /home/dore/onebot/Bot_Ero/homepage
	file_server
}

gallery.littlero.tech {
	reverse_proxy 127.0.0.1:8765
}

guestbook.littlero.tech {
	reverse_proxy 127.0.0.1:8765
}

profile.littlero.tech {
	reverse_proxy 127.0.0.1:8765
}

trpg.littlero.tech {
	reverse_proxy 127.0.0.1:8765
}

alarms.littlero.tech {
	reverse_proxy 127.0.0.1:8765
}

activities.littlero.tech {
	reverse_proxy 127.0.0.1:8765
}
```

> **注意**：旧路径（如 `/guestbook/`、`/trpg/` 等子路径）**不提供重定向**，直接失效。入口一律走各子域首页。

## 3. systemd

单 unit 模板已入库（`scripts/botero-web.service`），部署路径已配为 `/home/dore/onebot/Bot_Ero`：

```ini
[Unit]
Description=BotEro Web (gallery/profile/trpg/guestbook/alarms/activities)
After=network.target

[Service]
WorkingDirectory=/home/dore/onebot/Bot_Ero
Environment=BOTERO_DB_PATH=/home/dore/onebot/Bot_Ero/data.db
Environment=BOTERO_AUTH_SALT=CHANGE_ME
# 换盐时把旧盐加进来，旧密钥仍有效：BOTERO_AUTH_SALT_OLD=旧盐值
Environment=BOTERO_GALLERY_PORT=8765
ExecStart=/usr/bin/python3 -m webapp
Restart=always

[Install]
WantedBy=multi-user.target
```

部署步骤（模板已在 `scripts/`，先替换盐值再安装）：

```bash
cd /home/dore/onebot/Bot_Ero/scripts
sed -i 's/CHANGE_ME/<你的随机盐值>/' botero-web.service
cp botero-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now botero-web
```

> 生成随机盐：`openssl rand -base64 24`。
>
> **换盐无感迁移**：若此前已用旧盐发过密钥，把旧盐值配到 `BOTERO_AUTH_SALT_OLD`（逗号分隔可多个），旧密钥继续有效，无需群友重新 `/图库密钥`；之后新发的密钥用新盐。

### 从 6 进程迁移

旧部署是 6 个独立 unit（`botero-gallery`/`botero-guestbook`/`botero-profile`/`botero-trpg`/`botero-alarms`/`botero-activities`）。切换为单进程：

```bash
systemctl disable --now botero-gallery botero-guestbook botero-profile botero-trpg botero-alarms botero-activities
systemctl enable --now botero-web
caddy reload   # 新 Caddyfile（6 子域统一反代 8765）
```

> 生产盐值直接沿用旧 unit 的 `BOTERO_AUTH_SALT` 环境注入方式，无密钥迁移成本。

### 一键启停脚本

仓库提供 `scripts/botero-services.sh`（Ubuntu，需 root 或 sudo），管理 `botero-web`：

```bash
./scripts/botero-services.sh start    # 启动
./scripts/botero-services.sh stop     # 停止
./scripts/botero-services.sh restart  # 重启
./scripts/botero-services.sh status   # 查看状态
```

## 4. 环境变量清单

全部 `BOTERO_*` 变量（定义于 `core/config.py`，bot 与 webapp 共用）：

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `BOTERO_DB_PATH` | `<仓库>/data.db` | SQLite 数据库路径 |
| `BOTERO_IMAGE_ROOT` | `<仓库>/server_data/record_images` | 打卡图片存储目录 |
| `BOTERO_TRPG_CHARS_ROOT` | `<仓库>/server_data/trpg_chars` | TRPG 角色卡目录 |
| `BOTERO_USER_SETTINGS_ROOT` | `<仓库>/server_data/user_settings` | 用户设置目录 |
| `BOTERO_ACTIVITY_ROOT` | `<仓库>/server_data/activity_archive` | 活动存档目录 |
| `BOTERO_GALLERY_HOST` | `0.0.0.0` | webapp 监听地址 |
| `BOTERO_GALLERY_PORT` | `8765` | webapp 监听端口 |
| `BOTERO_GALLERY_URL` | `https://gallery.littlero.tech` | 个人中心等引用图库媒体/缩略图的基地址 |
| `BOTERO_ONEBOT_HTTP` | `http://192.168.0.103:3000` | OneBot HTTP 地址，用于拉取 QQ 昵称 |
| `BOTERO_ONEBOT_TOKEN` | `123456` | OneBot HTTP 访问令牌 |
| `BOTERO_GROUP_ID` | `296470819` | 默认群号 |
| `BOTERO_THUMB_CACHE` | `<仓库>/server_data/thumb_cache` | 缩略图缓存目录 |
| `BOTERO_THUMB_MAX_WIDTH` | `480` | 缩略图最大宽度 |
| `BOTERO_THUMB_MAX_HEIGHT` | `720` | 缩略图最大高度 |
| `BOTERO_THUMB_QUALITY` | `82` | 缩略图 JPEG 质量 |
| `BOTERO_AUTH_SALT` | `BotEro-Gallery-ChangeMe` | 登录密钥盐（生产环境必须修改为随机值；修改后旧密钥失效） |
| `BOTERO_AUTH_SALT_OLD` | 空 | 历史盐列表（逗号分隔）。换盐时把旧盐加进来，旧密钥继续有效，实现无感迁移 |
| `BOTERO_CHECKIN_MAX_IMAGES` | `9` | 网页打卡单次最大图片数 |
| `BOTERO_CHECKIN_MAX_BYTES` | `10485760` | 网页打卡单图最大字节数 |

## 5. 导航主页

`homepage/entries.json` 是主页（入口页）**唯一**的入口维护点：增删子应用入口、改 `url`、改展示名称/描述/徽标都在此文件完成，无需改动 `index.html`。子应用自身入口链接也一律指向对应子域。

## 6. 启动顺序与验证

1. 首次部署：`git clone` 仓库到 VPS（如 `/home/dore/onebot/Bot_Ero`），配置 DNS 与 Caddyfile；
2. 更新代码：`git pull` 后重启服务；
3. 启动：`./scripts/botero-services.sh start`（首次部署先 `enable --now botero-web` 设为开机自启）；
4. 验证：依次访问 6 个子域根路径，均应返回 HTTP 200 且内容为对应页面：
   ```bash
   for d in gallery guestbook profile trpg alarms activities; do
     echo "$d: $(curl -s -o /dev/null -w '%{http_code}' https://$d.littlero.tech)"
   done
   ```
   `ps` 中 uvicorn 应只剩 1 个 web 进程。

## 7. 已知限制

- **登录态跨域共享**：登录密钥经根域 cookie（`botero_key`，`.littlero.tech`）+ localStorage 双写，6 个子域首次访问任一域登录后其余域免重复登录（共享 `core/web/static/auth.js` 处理）。
- **SQLite 两写者**：`data.db` 仅剩 bot（`main.py`）与 webapp 两个写者，均为 WAL + `busy_timeout=5000`；高并发写场景（如打卡高峰期）仍可能偶发 `database is locked`，出现时重试即可。
