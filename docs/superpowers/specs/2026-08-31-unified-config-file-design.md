# 统一配置文件 config.yaml — 设计文档

- 日期：2026-08-31
- 状态：已与用户逐节确认通过
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-08-31-unified-config-file.md`

## 背景与问题

配置现状三处分裂：

1. **`scripts/botero.env` + `core/config.py`**：~30 个 `BOTERO_*` 环境变量（路径、盐、token、端口等），但 env 文件本身被 git 跟踪，真实值仍在仓库里
2. **纯硬编码**：Bot QQ、超管 QQ、昵称、默认群、WS 地址/token、双数据路径、docker 卷路径、下载代理（2 处）散落在 `core/base.py`、`core/context.py`、`main.py`、`core/utils.py`、`plugins/random_reference`
3. **绕过 config.py 的直接 `os.environ` 读取**：`core/character_store.py`、`core/user_settings.py`、`webapp/live/app.py`、`webapp/tools/icon.py`（且前两者与 config.py 存在重复默认值）

用户诉求：一套完整的、不通过环境变量读取的配置文件，全部设置归类到一处；真实值退出仓库。

## 目标

- 单一 `config.yaml`（YAML 格式，允许引入 PyYAML 依赖）承载全部部署可变配置
- 配置值流转采用「常量面不动」方案：`core/config.py` import 时加载 YAML、对外暴露与现状同名的模块级常量；`core/base.py`、`core/context.py`、`main.py` 等取值点改为从 config 取值但保留原有变量名——36 个 `core.config` importer 与各插件 import 零改动
- 真实配置文件不进 git，仓库只提交 `config.example.yaml` 模板
- `BOTERO_*` 环境变量机制整体退役（唯一例外见下）

## 非目标

- 玩法数值（补卡费用、称号上限、抽奖概率等）不进配置——权威在 `kb/GAMEPLAY.md`，避免双事实来源
- `BOTERO_VERSION` 留在代码中（代码发布身份，随 CHANGELOG 走）
- 算法常量（API 超时、周边界偏移、`PAGE_SIZE_*`、`REMEDY_MARKER`）不动
- 不做热重载、不做多环境 profile（本机/生产 = 两份不同值的同一格式文件）

## ① 文件与加载

- 位置：项目根 `config.yaml`；模板 `config.example.yaml`（占位值 + 每键中文注释）随仓库提交
- 依赖：PyYAML，只允许 `yaml.safe_load`；加入 `requirements.txt` 与 `webapp/requirements.txt`
- 路径解析：环境变量 `BOTERO_CONFIG`（**唯一保留的环境变量，仅用于定位配置文件本身**，不用于读取配置值）→ 缺省 `PROJECT_ROOT / "config.yaml"`
- 文件不存在：启动即退出（`SystemExit`），提示 `cp config.example.yaml config.yaml` 后填值
- 必填键缺失：启动即退出，报错精确到 `bot.qq` 形式的键路径
- 可选键：代码内默认值
- 统一 `encoding="utf-8"` 读取（中文注释）
- QQ 号做显式类型转换（`str(bot.qq)` / `int`），防 YAML 猜错类型（`"3915014383"` 必须加引号保持 str）

## ② YAML 结构与键→常量映射

### 结构（11 节）

```yaml
bot:
  qq: "3915014383"                # 必填，str
  nickname: 小埃同学               # 必填
  super_users: [1057613133]       # 必填，list[int]
  default_group: 296470819        # 必填，int
  ws_url: ws://127.0.0.1:3001     # 必填
  ws_token: "123456"              # 必填，str
  download_proxy: http://127.0.0.1:7890   # 可选，默认无代理
  llonebot_data_path: /app/llonebot/server_data   # 必填（OneBot API 路径）
  python_data_path: ./server_data  # 必填（Python I/O 路径）
  onebot_qq_volume: ""            # 可选，仅 docker 部署用，默认空
onebot:
  http_url: http://192.168.0.103:3000   # 必填
  token: "123456"                        # 必填，str
paths:    # 全部可选，默认 PROJECT_ROOT 下的现有布局
  db: data.db
  message_log_db: server_data/message_log.db
  images: server_data/record_images
  trpg_chars: server_data/trpg_chars
  user_settings: server_data/user_settings
  activity: server_data/activity_archive
  forum_images: server_data/forum_images
webapp:
  host: 0.0.0.0    # 可选
  port: 8765       # 可选
auth:
  salt: ChangeMe           # 必填
  old_salts: []            # 可选，list[str]
timeline:
  url: http://127.0.0.1:8765   # 必填
  token: ChangeMe              # 必填，str
weekly:
  web_base_url: https://littlero.tech   # 可选
  notify: true                           # 可选
uploads:
  checkin_max_images: 9       # 可选
  checkin_max_bytes: 10485760     # 可选（10MB）
  forum_image_max_bytes: 10485760 # 可选
thumbs:
  cache_dir: server_data/thumb_cache   # 可选
  max_width: 480    # 可选
  max_height: 720   # 可选
  jpeg_quality: 82  # 可选
live:
  flv_url: https://live.littlero.tech/live/livestream.flv   # 可选
tools:
  icon_proxy: ""   # 可选，空 = 不走代理
```

### 必填规则

`bot` 全节（除 `download_proxy`、`onebot_qq_volume`）、`onebot` 全节、`auth.salt`、`timeline.token` 为必填；其余可选带默认。

### 键 → `core/config.py` 常量映射（常量名保持现状不变）

| YAML 键 | 常量（所在模块） | 类型 |
|---------|-----------------|------|
| bot.qq | `BOT_QQ`（config 新增；`core/base.py` 同名 re-export） | str |
| bot.nickname | `NICKNAME`（config 新增；`core/base.py` re-export） | str |
| bot.super_users | `SUPER_USER`（config 新增；`core/base.py` re-export） | list[int] |
| bot.default_group | `DEFAULT_GROUP_ID`（config 新增；`core/context.py` 同名 re-export）；**同时赋给现有 `GROUP_ID`**（合并两个旧名） | int |
| bot.ws_url / bot.ws_token | `WS_URL` / `WS_TOKEN`（config 新增；`main.py` 局部变量改从 config 取） | str |
| bot.download_proxy | `DOWNLOAD_PROXY`（config 新增；`core/utils.py`、`plugins/random_reference` 消费） | str |
| bot.llonebot_data_path / bot.python_data_path / bot.onebot_qq_volume | `LLONEBOT_DATA_PATH` / `PYTHON_DATA_PATH` / `ONEBOT_QQ_VOLUME`（config 新增；`core/context.py` 同名小写模块属性 re-export，**保留可 patch 性**） | str |
| onebot.http_url / onebot.token | `ONEBOT_HTTP_URL` / `ONEBOT_TOKEN` | str |
| paths.db | `DB_PATH` | Path |
| paths.message_log_db | `MESSAGE_LOG_DB_PATH` | Path |
| paths.images | `IMAGE_ROOT` | Path |
| paths.trpg_chars | `TRPG_CHARS_ROOT` | Path |
| paths.user_settings | `USER_SETTINGS_ROOT` | Path |
| paths.activity | `ACTIVITY_ROOT` | Path |
| paths.forum_images | `FORUM_IMAGES_ROOT` | Path |
| webapp.host / webapp.port | `HOST` / `PORT` | str / int |
| auth.salt / auth.old_salts | `AUTH_SALT` / `AUTH_SALT_OLD` | str / list[str] |
| timeline.url / timeline.token | `TIMELINE_URL` / `TIMELINE_TOKEN` | str |
| weekly.web_base_url / weekly.notify | `WEB_BASE_URL` / `WEEKLY_NOTIFY_ENABLED` | str / bool |
| uploads.checkin_max_images / checkin_max_bytes | `CHECKIN_MAX_IMAGES` / `CHECKIN_MAX_BYTES` | int |
| uploads.forum_image_max_bytes | `FORUM_IMAGE_MAX_BYTES` | int |
| thumbs.cache_dir / max_width / max_height / jpeg_quality | `THUMB_CACHE_DIR`（Path）/ `THUMB_MAX_WIDTH` / `THUMB_MAX_HEIGHT` / `THUMB_JPEG_QUALITY` | Path / int |
| live.flv_url | `LIVE_FLV_URL` | str |
| tools.icon_proxy | `ICON_PROXY`（None = 无代理） | str\|None |

留在 `core/config.py` 不进 YAML：`PROJECT_ROOT`、`BOTERO_VERSION`、`PAGE_SIZE_DEFAULT`、`PAGE_SIZE_MAX`、`REMEDY_MARKER`。

## ③ 代码改动面

| 文件 | 改动 |
|------|------|
| `core/config.py` | 重写：YAML 加载 + 必填校验 + 类型转换；对外常量名全部不变 + 新增上表常量 |
| `core/base.py` | `NICKNAME`/`SUPER_USER`/`BOT_QQ` 改为从 `core.config` 取值赋名（插件 `from core.base import BOT_QQ` 等 import 面不变） |
| `core/context.py` | `llonebot_data_path`/`python_data_path`/`onebot_qq_volume`/`DEFAULT_GROUP_ID` 改从 config 取值；**保留模块属性形式**（测试大量 patch 它们） |
| `main.py` | `WS_URL`/`token` 从 config 取；**删除文件顶部 env 注入块** |
| `core/utils.py`、`plugins/random_reference/__init__.py` | 下载代理改用 `config.DOWNLOAD_PROXY`（无值时直连） |
| `core/character_store.py`、`core/user_settings.py` | 根路径改 import `core.config` 的 `TRPG_CHARS_ROOT`/`USER_SETTINGS_ROOT`（消灭重复默认值） |
| `webapp/live/app.py` | `LIVE_FLV_URL` 改 import config |
| `webapp/tools/icon.py` | `PROXY` 改 import `config.ICON_PROXY` |
| `webapp/__main__.py` | 删除 `--db`/`--images` 参数（import 冻结后 set env 从未生效，kb/CONVENTIONS 已知陷阱）；保留 `--host`/`--port` |
| `scripts/botero.env` | `git rm`，真实值迁入各环境 `config.yaml` |
| `scripts/botero-web.service` | 删除 `EnvironmentFile=` 行（webapp 直接读 `config.yaml`） |
| `.gitignore` | 增加 `config.yaml` |

## ④ 测试与部署

- `test/conftest.py`：删除现有 env 重定向块 → 改为生成临时 `config.yaml`（全部路径键指向会话临时目录、必填键填测试值）+ 设 `BOTERO_CONFIG` 指向它，仍在任何 core import 之前执行
- `test/scripts/check_*.py` 以子进程起 webapp 的套件：子进程环境传 `BOTERO_CONFIG` 指向 conftest 生成的临时配置（计划阶段逐个核对现状）
- 现有直接 patch `context.python_data_path` 等模块属性的测试不受影响（属性形式保留）
- VPS 迁移：`cp config.example.yaml config.yaml` 填真实值；systemd unit 更新后 `daemon-reload`；bot 与 webapp 继续共用同一 `config.yaml`（盐单一来源原则不变）
- 本机迁移：同上；现有 `scripts/botero.env` 内容并入 `config.yaml` 后删除

## ⑤ 文档同步（同 commit）

| 文档 | 改动 |
|------|------|
| `kb/QUICK_REFERENCE.md` | 项目身份段指向 `config.yaml`；硬编码常量表改为 config.yaml 键表；常用路径段注明可用配置覆盖 |
| `kb/OPERATIONS.md` | `BOTERO_*` 环境变量表 → YAML 键说明 + `BOTERO_CONFIG` 说明 |
| `AGENTS.md` / `CLAUDE.md` | toolchain 段：`scripts/botero.env` 描述改为 `config.yaml` |
| `docs/web-apps-deployment.md` | EnvironmentFile、换盐、环境变量表全部改为 config.yaml 口径 |
| `kb/CONVENTIONS.md` | 删除「--db 启动参数不生效」陷阱条目（参数已删）；环境变量陷阱改为配置文件口径 |
| `CHANGELOG.md` + `core/config.py::BOTERO_VERSION` | 新 `[minor]` 节（配置方式变更是运维可见变更） |

## 验收标准

1. 全代码库 `grep os.environ` 仅剩：`BOTERO_CONFIG` 定位、`core/gen_image/fonts.py` 的 `WINDIR`（系统变量，非配置）
2. `grep "127.0.0.1:7890\|1057613133\|3915014383\|296470819\|3001\|小埃同学"` 在 `core/`、`plugins/`、`webapp/`、`main.py`、`config.example.yaml` 之外零命中（测试与文档除外）
3. `pytest` 全量回归通过
4. 无 `config.yaml` 时 `python main.py` 与 `python -m webapp` 均拒绝启动并给出复制模板提示
5. `git ls-files` 不含 `config.yaml` 与 `scripts/botero.env`
