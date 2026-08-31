# 统一配置文件 config.yaml 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用单一 `config.yaml`（YAML）取代全部 `BOTERO_*` 环境变量与代码硬编码配置，真实配置退出 git 仓库。

**Architecture:** `core/config.py` 在 import 时经 `yaml.safe_load` 加载配置文件并暴露与现状同名的模块级常量（常量面不动，36 个 importer 零改动）；`core/base.py`、`core/context.py`、`main.py` 等取值点改为从 config 取值但保留原变量名；唯一保留的环境变量 `BOTERO_CONFIG` 仅用于定位配置文件本身（测试与多环境部署用）。

**Tech Stack:** Python 3 / PyYAML（新增依赖，仅 `safe_load`）/ pytest

**Spec:** `docs/superpowers/specs/2026-08-31-unified-config-file-design.md`（键→常量映射表、必填规则、验收标准均以 spec 为准，本计划不重复论证）

## Global Constraints

- bot 进程禁止 `async`/`await`（本计划纯同步改写，不引入异步）
- 每个任务收尾门槛：`pytest` 全量回归通过（Windows 本机直接跑 `pytest`）
- commit 消息 MUST 中文 + Conventional Commits；一个任务 = 一个逻辑 commit
- `config.yaml` 永不入库（Task 4 加入 .gitignore 前，也不得 `git add`）
- PyYAML 只允许 `yaml.safe_load`；读取一律 `encoding="utf-8"`
- QQ 号显式类型转换：`bot.qq` → `str`（YAML 中必须带引号），`super_users` → `list[int]`，`default_group` → `int`
- 测试隔离铁律：任何测试代码不得读写真实 `data.db` / `server_data/`（靠 conftest 的 `BOTERO_CONFIG` 临时配置保证）
- 文档同步在 Task 5 集中完成（CHANGELOG + `BOTERO_VERSION` bump 同一 commit）

---

### Task 1: 配置源切换——config.py YAML 化 + 全部测试隔离迁移

**Files:**
- Modify: `core/config.py`（重写）
- Create: `config.example.yaml`
- Create: `test/test_config_loader.py`
- Create: `test/scripts/_env.py`（测试配置生成 helper）
- Modify: `test/conftest.py`
- Modify: `test/scripts/check_activities_api.py`、`check_forum_comment_threads_api.py`、`check_forum_edit_api.py`、`check_forum_poll.py`、`check_forum_views.py`、`check_timeline_privacy.py`、`check_timeline_unread.py`、`check_web_auth_guard.py`
- Modify: `test/test_auth_old_salt.py`、`test/test_webapp_api_suites.py`（docstring）
- Modify: `requirements.txt`、`webapp/requirements.txt`
- Create（**不入库**）: `config.yaml`（本机真实值）

**Interfaces:**
- Consumes: 无（首个任务）
- Produces: `core.config._load(path: Path) -> dict`（校验必填键，缺失 `sys.exit`）；`core.config` 全部常量（`BOT_QQ`/`NICKNAME`/`SUPER_USER`/`DEFAULT_GROUP_ID`/`GROUP_ID`/`WS_URL`/`WS_TOKEN`/`DOWNLOAD_PROXY`/`LLONEBOT_DATA_PATH`/`PYTHON_DATA_PATH`/`ONEBOT_QQ_VOLUME`/`LIVE_FLV_URL`/`ICON_PROXY` 新增，其余沿用旧名）；`test/scripts/_env.py::write_config(tmp_dir: str, **section_overrides) -> str`（Task 1 内部自用，后续任务不再碰测试）

**为什么这个任务必须一次完成：** `core/config.py` 停读环境变量的那一刻起，conftest 与 8 个 check 脚本的 env 隔离全部失效，测试会砸到真实 `data.db`。配置源切换与测试隔离迁移不可分割。

- [ ] **Step 1: 写失败的加载器测试**

创建 `test/test_config_loader.py`：

```python
"""config.yaml 加载器：必填校验、缺文件提示、默认值与类型转换。"""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REQUIRED_MINIMAL = """
bot:
  qq: "123456"
  nickname: 测试bot
  super_users: [1, 2]
  default_group: 42
  ws_url: ws://127.0.0.1:3001
  ws_token: "123456"
  llonebot_data_path: /tmp/onebot_data
  python_data_path: ./server_data
onebot:
  http_url: http://127.0.0.1:3000
  token: "123456"
auth:
  salt: test-salt
timeline:
  url: http://127.0.0.1:8765
  token: test-timeline-token
"""


def _write(tmp: str, content: str) -> str:
    p = Path(tmp) / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestLoad(unittest.TestCase):
    def test_missing_file_exits_with_hint(self):
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx:
                _load(Path(tmp) / "none.yaml")
            self.assertIn("config.example.yaml", str(ctx.exception))

    def test_missing_required_key_exits(self):
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            # 缺 bot.qq
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            del bad["bot"]["qq"]
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                _load(p)
            self.assertIn("bot.qq", str(ctx.exception))

    def test_empty_required_value_exits(self):
        from core.config import _load
        with tempfile.TemporaryDirectory() as tmp:
            bad = yaml.safe_load(REQUIRED_MINIMAL)
            bad["auth"]["salt"] = ""
            p = Path(tmp) / "config.yaml"
            p.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(SystemExit):
                _load(p)


class TestConstants(unittest.TestCase):
    """模块级常量：reload 后类型与默认值正确，退出时恢复 conftest 配置。"""

    def _reload_with(self, cfg_path: str):
        import os
        old = os.environ.get("BOTERO_CONFIG")
        os.environ["BOTERO_CONFIG"] = cfg_path
        import core.config as cfg
        try:
            importlib.reload(cfg)
            return cfg
        finally:
            if old is None:
                os.environ.pop("BOTERO_CONFIG", None)
            else:
                os.environ["BOTERO_CONFIG"] = old

    def test_types_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._reload_with(_write(tmp, REQUIRED_MINIMAL))
            try:
                self.assertEqual(cfg.BOT_QQ, "123456")          # str，非 int
                self.assertIsInstance(cfg.BOT_QQ, str)
                self.assertEqual(cfg.SUPER_USER, [1, 2])
                self.assertEqual(cfg.DEFAULT_GROUP_ID, 42)
                self.assertEqual(cfg.GROUP_ID, 42)              # 两旧名合并为一键
                self.assertEqual(cfg.WS_TOKEN, "123456")
                self.assertEqual(cfg.DOWNLOAD_PROXY, "")        # 可选默认无代理
                self.assertIsNone(cfg.ICON_PROXY)
                self.assertTrue(cfg.WEEKLY_NOTIFY_ENABLED)
                self.assertEqual(cfg.DB_PATH, cfg.PROJECT_ROOT / "data.db")
                self.assertEqual(
                    cfg.MESSAGE_LOG_DB_PATH, cfg.PROJECT_ROOT / "server_data" / "message_log.db"
                )
                self.assertEqual(cfg.CHECKIN_MAX_BYTES, 10 * 1024 * 1024)
                self.assertEqual(cfg.AUTH_SALT_OLD, [])
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)  # 恢复 conftest 临时配置

    def test_auth_old_salts_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = yaml.safe_load(REQUIRED_MINIMAL)
            raw["auth"]["old_salts"] = ["a", " b", "c"]  # YAML 原样保留空格
            cfg = self._reload_with(_write(tmp, yaml.safe_dump(raw, allow_unicode=True)))
            try:
                self.assertEqual(cfg.AUTH_SALT_OLD, ["a", " b", "c"])
            finally:
                import core.config as cfg2
                importlib.reload(cfg2)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test/test_config_loader.py -v`
Expected: FAIL/ERROR（`ImportError: cannot import name '_load'` 或 `ModuleNotFoundError: No module named 'yaml'`）

- [ ] **Step 3: 安装依赖并登记**

Run: `pip install PyYAML`

`requirements.txt` 在「机器人核心」小节末尾加一行（带注释新小节）：

```
# ---- 统一配置文件 (core/config.py) ----
PyYAML>=6.0
```

`webapp/requirements.txt` 追加：

```
# 统一配置文件
PyYAML>=6.0
```

- [ ] **Step 4: 重写 core/config.py**

完整新内容（保持 `BOTERO_VERSION = "1.31.0"` 不动，Task 5 再 bump）：

```python
"""BotEro 共享配置：bot 与全部 Web 子应用共用的 config.yaml 读取。

配置文件定位：环境变量 BOTERO_CONFIG（仅此一个用途）→ 缺省项目根 config.yaml。
文件不存在或必填键缺失时启动即退出；可选键在此处给默认值。
"""

import os
import sys
from pathlib import Path

import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 当前版本（单一来源，随 CHANGELOG.md 同步更新）
BOTERO_VERSION = "1.31.0"

CONFIG_PATH = Path(os.environ.get("BOTERO_CONFIG") or PROJECT_ROOT / "config.yaml")

# 必填键（点路径）。bot 节除 download_proxy / onebot_qq_volume 外全必填。
_REQUIRED = (
    "bot.qq", "bot.nickname", "bot.super_users", "bot.default_group",
    "bot.ws_url", "bot.ws_token", "bot.llonebot_data_path", "bot.python_data_path",
    "onebot.http_url", "onebot.token",
    "auth.salt",
    "timeline.url", "timeline.token",
)


def _load(path: Path) -> dict:
    if not path.is_file():
        sys.exit(
            f"未找到配置文件 {path}\n"
            f"请先复制模板并填写：cp config.example.yaml config.yaml"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for dotted in _REQUIRED:
        section, _, key = dotted.partition(".")
        value = (data.get(section) or {}).get(key)
        if value is None or value == "" or value == []:
            sys.exit(f"配置文件 {path} 缺少必填项 {dotted}")
    return data


_RAW = _load(CONFIG_PATH)


def _sec(name: str) -> dict:
    return _RAW.get(name) or {}


_bot = _sec("bot")
_onebot = _sec("onebot")
_paths = _sec("paths")
_auth = _sec("auth")
_timeline = _sec("timeline")
_weekly = _sec("weekly")
_uploads = _sec("uploads")
_thumbs = _sec("thumbs")


def _path_from(section: dict, key: str, default: Path) -> Path:
    raw = section.get(key)
    return Path(raw) if raw else default


def _path(key: str, default: Path) -> Path:
    return _path_from(_paths, key, default)


# —— bot 身份与连接（原 core/base.py、core/context.py、main.py 硬编码）——
BOT_QQ = str(_bot["qq"])
NICKNAME = str(_bot["nickname"])
SUPER_USER = [int(u) for u in _bot["super_users"]]
DEFAULT_GROUP_ID = int(_bot["default_group"])
GROUP_ID = DEFAULT_GROUP_ID  # webapp 侧旧名，两名一键
WS_URL = str(_bot["ws_url"])
WS_TOKEN = str(_bot["ws_token"])
DOWNLOAD_PROXY = str(_bot.get("download_proxy") or "")
LLONEBOT_DATA_PATH = str(_bot["llonebot_data_path"])
PYTHON_DATA_PATH = str(_bot["python_data_path"])
ONEBOT_QQ_VOLUME = str(_bot.get("onebot_qq_volume") or "")

# —— OneBot HTTP（NapCat / Lagrange 等），用于拉取 QQ 昵称 ——
ONEBOT_HTTP_URL = str(_onebot["http_url"])
ONEBOT_TOKEN = str(_onebot["token"])

# —— 数据路径（相对路径按项目根解析）——
DB_PATH = _path("db", PROJECT_ROOT / "data.db")
MESSAGE_LOG_DB_PATH = _path("message_log_db", PROJECT_ROOT / "server_data" / "message_log.db")
IMAGE_ROOT = _path("images", PROJECT_ROOT / "server_data" / "record_images")
TRPG_CHARS_ROOT = _path("trpg_chars", PROJECT_ROOT / "server_data" / "trpg_chars")
USER_SETTINGS_ROOT = _path("user_settings", PROJECT_ROOT / "server_data" / "user_settings")
ACTIVITY_ROOT = _path("activity", PROJECT_ROOT / "server_data" / "activity_archive")
FORUM_IMAGES_ROOT = _path("forum_images", PROJECT_ROOT / "server_data" / "forum_images")

# —— webapp 服务 ——
HOST = str(_sec("webapp").get("host") or "0.0.0.0")
PORT = int(_sec("webapp").get("port") or 8765)
PAGE_SIZE_DEFAULT = 40
PAGE_SIZE_MAX = 100

REMEDY_MARKER = "remedy_checkin"

# —— 登录密钥（QQ 号 + 盐 → HMAC → Base64）——
AUTH_SALT = str(_auth["salt"])
AUTH_SALT_OLD = [str(s) for s in (_auth.get("old_salts") or [])]

# —— 社区时间线 ——
TIMELINE_URL = str(_timeline["url"]).rstrip("/")
TIMELINE_TOKEN = str(_timeline["token"])

# —— 小埃周报 ——
WEB_BASE_URL = str(_weekly.get("web_base_url") or "https://littlero.tech").rstrip("/")
WEEKLY_NOTIFY_ENABLED = bool(_weekly.get("notify", True))

# —— 缩略图 ——
THUMB_CACHE_DIR = _path_from(_thumbs, "cache_dir", PROJECT_ROOT / "server_data" / "thumb_cache")
THUMB_MAX_WIDTH = int(_thumbs.get("max_width") or 480)
THUMB_MAX_HEIGHT = int(_thumbs.get("max_height") or 720)
THUMB_JPEG_QUALITY = int(_thumbs.get("jpeg_quality") or 82)

# —— 网页打卡上传 ——
CHECKIN_MAX_IMAGES = int(_uploads.get("checkin_max_images") or 9)
CHECKIN_MAX_BYTES = int(_uploads.get("checkin_max_bytes") or 10 * 1024 * 1024)
FORUM_IMAGE_MAX_BYTES = int(_uploads.get("forum_image_max_bytes") or 10 * 1024 * 1024)

# —— 直播 / 工具箱 ——
LIVE_FLV_URL = str(_sec("live").get("flv_url") or "https://live.littlero.tech/live/livestream.flv")
ICON_PROXY = _sec("tools").get("icon_proxy") or None  # None = 不走代理
```

（完整文件顺序：imports → `PROJECT_ROOT`/`BOTERO_VERSION`/`CONFIG_PATH` → `_REQUIRED` → `_load` → `_RAW = _load(CONFIG_PATH)` → `_sec` 与各节变量 → `_path_from`/`_path` → 按节常量，如上。`THUMB_CACHE_DIR` 用 `_path_from(_thumbs, ...)` 是因为 `cache_dir` 在 `thumbs` 节不在 `paths` 节。）

- [ ] **Step 5: 创建 config.example.yaml**

项目根，完整内容（真实占位值 + 每键中文注释）：

```yaml
# BotEro 统一配置文件 —— bot（main.py）与 webapp 共用，部署侧单一来源。
# 使用：cp config.example.yaml config.yaml 后填写真实值；本文件不进 git。
# 定位：默认项目根 config.yaml；可用环境变量 BOTERO_CONFIG 指向其他路径（仅此一个环境变量）。
# 修改后需重启对应进程生效。

bot:
  qq: "3915014383"            # Bot 的 QQ 号（必须加引号保持字符串）
  nickname: 小埃同学           # 机器人昵称
  super_users: [1057613133]   # 超级用户 QQ 号列表
  default_group: 296470819    # 默认群号（无群上下文时发送目标）
  ws_url: ws://127.0.0.1:3001   # OneBot v11 WebSocket 地址
  ws_token: "123456"            # WS 鉴权 token
  download_proxy: "http://127.0.0.1:7890"  # 图片下载代理；留空 "" 直连
  llonebot_data_path: /app/llonebot/server_data  # OneBot API 调用看到的路径（容器内）
  python_data_path: ./server_data               # Python 文件 I/O 用的路径
  onebot_qq_volume: ""      # docker 卷路径（裸机部署留空）

onebot:
  http_url: http://192.168.0.103:3000  # OneBot HTTP（拉取 QQ 昵称）
  token: "123456"

# 数据路径（可选，缺省即下列布局；相对路径按项目根解析）
paths:
  db: data.db
  message_log_db: server_data/message_log.db
  images: server_data/record_images
  trpg_chars: server_data/trpg_chars
  user_settings: server_data/user_settings
  activity: server_data/activity_archive
  forum_images: server_data/forum_images

webapp:
  host: 0.0.0.0
  port: 8765

auth:
  salt: ChangeMe-Random-Salt    # 登录密钥盐（HMAC）：bot 生成密钥与 webapp 验证共用
  old_salts: []                 # 换盐后把旧盐加进此列表，旧密钥继续有效（无感迁移）

timeline:
  url: http://127.0.0.1:8765   # Event Server 基地址
  token: ChangeMe-Timeline-Token  # 系统间事件令牌（与用户登录密钥不同）

weekly:
  web_base_url: https://littlero.tech  # 周报通知链接前缀
  notify: true                          # 周报出版通知（群消息 + 时间线事件）

uploads:
  checkin_max_images: 9
  checkin_max_bytes: 10485760       # 10MB
  forum_image_max_bytes: 10485760   # 10MB

thumbs:
  cache_dir: server_data/thumb_cache
  max_width: 480
  max_height: 720
  jpeg_quality: 82

live:
  flv_url: https://live.littlero.tech/live/livestream.flv

tools:
  icon_proxy: ""    # 工具箱图标抓取代理；留空不走代理
```

- [ ] **Step 6: 创建测试配置 helper `test/scripts/_env.py`**

```python
"""测试用 config.yaml 生成器：conftest 与 check_*.py 共用。

返回写入的配置文件路径。section_overrides 按节深合并覆盖默认值，例如：
    write_config(_tmp, paths={"db": _db}, timeline={"token": "test-timeline-token"})
"""


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def write_config(tmp_dir: str, **section_overrides) -> str:
    import os

    cfg = {
        "bot": {
            "qq": "3915014383", "nickname": "测试bot", "super_users": [1057613133],
            "default_group": 296470819, "ws_url": "ws://127.0.0.1:3001", "ws_token": "123456",
            "download_proxy": "",
            "llonebot_data_path": os.path.join(tmp_dir, "onebot_data"),
            "python_data_path": os.path.join(tmp_dir, "server_data"),
            "onebot_qq_volume": "",
        },
        # OneBot HTTP 指向必然拒绝连接的地址：昵称/头像解析立即失败降级
        "onebot": {"http_url": "http://127.0.0.1:1", "token": "123456"},
        "paths": {
            "db": os.path.join(tmp_dir, "data.db"),
            "message_log_db": os.path.join(tmp_dir, "message_log.db"),
            "images": os.path.join(tmp_dir, "record_images"),
            "trpg_chars": os.path.join(tmp_dir, "trpg_chars"),
            "user_settings": os.path.join(tmp_dir, "user_settings"),
            "activity": os.path.join(tmp_dir, "activity_archive"),
            "forum_images": os.path.join(tmp_dir, "forum_images"),
        },
        "thumbs": {"cache_dir": os.path.join(tmp_dir, "thumb_cache")},
        "auth": {"salt": "test-salt", "old_salts": []},
        "timeline": {"url": "http://127.0.0.1:8765", "token": "test-timeline-token"},
    }
    cfg = _merge(cfg, section_overrides)
    for sub in ("record_images", "trpg_chars", "user_settings", "activity_archive",
                "forum_images", "thumb_cache", "onebot_data", "server_data"):
        os.makedirs(os.path.join(tmp_dir, sub), exist_ok=True)
    path = os.path.join(tmp_dir, "config.yaml")
    with open(path, "w", encoding="utf-8") as f:
        import yaml
        yaml.safe_dump(cfg, f, allow_unicode=True)
    return path
```

- [ ] **Step 7: 重写 `test/conftest.py` 的隔离块**

把「数据路径安全隔离」到 `collect_ignore` 之前的全部内容替换为（保留文件头 docstring，并把 docstring 里 `BOTERO_*` 表述改为 `BOTERO_CONFIG` 临时配置口径）：

```python
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# —— 数据路径安全隔离（必须先于任何 core 导入执行）——
# 生成临时 config.yaml 并经 BOTERO_CONFIG 指向它，全部数据路径落在会话临时目录，
# 保证 pytest 回归永不触碰真实 data.db / server_data/。
_TMP_DIR = tempfile.mkdtemp(prefix="botero_pytest_")
sys.path.insert(0, str(PROJECT_ROOT / "test" / "scripts"))  # 复用 _env helper
from _env import write_config  # noqa: E402

os.environ["BOTERO_CONFIG"] = write_config(_TMP_DIR)
_DB_PATH = os.path.join(_TMP_DIR, "data.db")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database_manager import init_schema  # noqa: E402

# 会话级兜底库：进程内若有代码经 DbManager/core.config 触达默认库，落在此处且带全量 schema
_conn = sqlite3.connect(_DB_PATH)
init_schema(_conn, _conn.cursor())
_conn.commit()
_conn.close()

# LLM 子系统已弃用，test_llm.py 真实调用外部计费 API（需 DEEPSEEK_API_KEY 且有余额），
# 不纳入常规回归；仍可单独运行：python -m pytest test/test_llm.py
collect_ignore = ["test_llm.py"]
```

- [ ] **Step 8: 迁移 8 个 check 脚本**

每个脚本：删除 `os.environ["BOTERO_..."] = ...` 行，改为在**同一位置**（必须仍在任何 `core`/`webapp` import 之前）：

```python
from _env import write_config  # 同目录，sys.path[0] 已含 test/scripts

os.environ["BOTERO_CONFIG"] = write_config(_tmp, paths={"db": _db})
```

各脚本替换对照（`_tmp`/`_db` 沿用脚本内既有变量名）：

| 脚本 | write_config 参数 |
|------|------------------|
| `check_activities_api.py` | `write_config(_tmp, paths={"db": _db})` |
| `check_forum_comment_threads_api.py` | `write_config(_tmp, paths={"db": _db})` |
| `check_forum_edit_api.py` | `write_config(_tmp, paths={"db": _db})` |
| `check_forum_poll.py` | `write_config(_tmp, paths={"db": _db})` |
| `check_forum_views.py` | `write_config(_tmp, paths={"db": _db})` |
| `check_timeline_privacy.py` | `write_config(_tmp, paths={"db": _db, "user_settings": os.path.join(_tmp, "user_settings"), "images": os.path.join(_tmp, "record_images")}, thumbs={"cache_dir": os.path.join(_tmp, "thumb_cache")})`（onebot/token 用 helper 默认值即可，与原值一致） |
| `check_timeline_unread.py` | `write_config(_tmp, paths={"db": _db})`（onebot_http 与 timeline token 原=helper 默认值） |
| `check_web_auth_guard.py` | `write_config(_tmp, paths={"db": _db})` |

替换后自查每个脚本：`grep -n "BOTERO_\|os.environ" test/scripts/<脚本>.py`——只允许出现 `BOTERO_CONFIG` 一处；若脚本后文还读旧 env 值（预期没有），改读局部变量。

`test/test_webapp_api_suites.py` docstring 第 4 行 `BOTERO_DB_PATH` 改为 `BOTERO_CONFIG`（子进程各自生成独立临时配置）。

- [ ] **Step 9: 修 `test/test_auth_old_salt.py` 的 parsing 测试**

`test_salt_old_config_parsing` 整个方法替换为（YAML 列表原样保留，不再逗号切分）：

```python
    def test_salt_old_config_parsing(self):
        import importlib
        import os
        import tempfile
        from pathlib import Path
        from core import config
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "config.yaml"
            cfg_file.write_text(
                "auth:\n  salt: new-salt\n  old_salts: ['a', ' b', 'c']\n",
                encoding="utf-8",
            )
            old = os.environ.get("BOTERO_CONFIG")
            os.environ["BOTERO_CONFIG"] = str(cfg_file)
            try:
                importlib.reload(config)
                self.assertEqual(config.AUTH_SALT_OLD, ["a", " b", "c"])
            finally:
                if old is None:
                    os.environ.pop("BOTERO_CONFIG", None)
                else:
                    os.environ["BOTERO_CONFIG"] = old
                importlib.reload(config)
```

（其余三个 patch `core.auth.AUTH_SALT` 的测试不用动——它们 patch 的是 auth 模块属性，与配置来源无关。）

- [ ] **Step 10: 生成本机真实 config.yaml（不入库）**

`cp config.example.yaml config.yaml`，把本机真实值填入。真实值来源（当前生产值）：

| 键 | 值 |
|----|-----|
| bot.* 全节 | 与 example 相同即生产值（qq/nickname/super_users/default_group/ws_url/ws_token/download_proxy/llonebot_data_path/python_data_path 照抄） |
| onebot.http_url | `http://192.168.0.103:3000` |
| auth.salt | 取自现有 `scripts/botero.env` 的 `BOTERO_AUTH_SALT` |
| auth.old_salts | 若 `scripts/botero.env` 有 `BOTERO_AUTH_SALT_OLD`，按逗号拆成列表 |
| timeline.url / token | 取自 `scripts/botero.env` 的 `BOTERO_TIMELINE_URL` / `BOTERO_EVENT_TOKEN` |
| weekly.* | 若 botero.env 有对应覆盖值则填，否则删掉该节用默认 |

**绝不 `git add config.yaml`**（Task 4 才改 .gitignore，此前靠自觉）。

- [ ] **Step 11: 全量回归**

Run: `pytest`
Expected: 全部通过（含 test_config_loader.py 新增用例）

- [ ] **Step 12: 验收 grep**

Run: `grep -rn "BOTERO_" test/ --include="*.py" | grep -v BOTERO_CONFIG`
Expected: 零输出

Run: `grep -rn "os.environ" core/config.py`
Expected: 仅 `BOTERO_CONFIG` 一处

- [ ] **Step 13: Commit**

```bash
git add core/config.py config.example.yaml test/test_config_loader.py test/scripts/_env.py test/conftest.py test/scripts/check_activities_api.py test/scripts/check_forum_comment_threads_api.py test/scripts/check_forum_edit_api.py test/scripts/check_forum_poll.py test/scripts/check_forum_views.py test/scripts/check_timeline_privacy.py test/scripts/check_timeline_unread.py test/scripts/check_web_auth_guard.py test/test_auth_old_salt.py test/test_webapp_api_suites.py requirements.txt webapp/requirements.txt
git commit -m "refactor(配置): core/config 改读 config.yaml，测试隔离迁移 BOTERO_CONFIG"
```

---

### Task 2: 身份/路径/连接常量迁移（base/context/main）

**Files:**
- Modify: `core/base.py:11-13`
- Modify: `core/context.py:11-16`
- Modify: `main.py:1-30`
- Create: `test/test_config_wiring.py`

**Interfaces:**
- Consumes: Task 1 的 `core.config` 常量（`NICKNAME`/`SUPER_USER`/`BOT_QQ`/`DEFAULT_GROUP_ID`/`WS_URL`/`WS_TOKEN`/`LLONEBOT_DATA_PATH`/`PYTHON_DATA_PATH`/`ONEBOT_QQ_VOLUME`）
- Produces: 不变量——`from core.base import BOT_QQ` 等 7 处插件 import、`from core.context import DEFAULT_GROUP_ID`、测试对 `context.python_data_path` 的 patch 全部继续有效

- [ ] **Step 1: 写失败的接线测试**

`test/test_config_wiring.py`：

```python
"""身份常量接线：base/context 的旧名字 = config 值，且保持可 patch 的模块属性。"""
import sys
import unittest


class TestWiring(unittest.TestCase):
    def test_base_identity_from_config(self):
        from core import base, config
        self.assertIs(base.BOT_QQ, config.BOT_QQ)
        self.assertIs(base.SUPER_USER, config.SUPER_USER)
        self.assertIs(base.NICKNAME, config.NICKNAME)

    def test_context_attrs_from_config(self):
        from core import config, context
        self.assertEqual(context.DEFAULT_GROUP_ID, config.DEFAULT_GROUP_ID)
        self.assertEqual(context.llonebot_data_path, config.LLONEBOT_DATA_PATH)
        self.assertEqual(context.python_data_path, config.PYTHON_DATA_PATH)
        # 模块属性仍可整体替换（测试隔离依赖此性质）
        old = context.python_data_path
        try:
            context.python_data_path = "/tmp/patched"
            self.assertEqual(context.python_data_path, "/tmp/patched")
        finally:
            context.python_data_path = old

    def test_main_reads_config_ws(self):
        # 不 import main：import main 会触发 migrate_group_plugin_config() 直写真实 data.db（隔离铁律）。
        # 接线覆盖：Task 2 Step 7 grep + Task 4 Step 5 启动冒烟。
        import core.config as cfg
        self.assertTrue(hasattr(cfg, "WS_URL"))
        self.assertIsInstance(cfg.WS_TOKEN, str)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest test/test_config_wiring.py -v`
Expected: `test_base_identity_from_config` FAIL（base 常量是源码字面量，与 YAML 解析出的字符串非同一对象）；`test_context_attrs_from_config` 的赋值断言通过（上下文常量当前也是字面量同值——非本步关键）。整体文件 FAIL 即为有效 red。

- [ ] **Step 3: 改 `core/base.py`**

把：

```python
NICKNAME = "小埃同学"         # 机器人昵称
SUPER_USER = [1057613133]   # 主人的 QQ 号
BOT_QQ = "3915014383"
```

替换为：

```python
from core.config import BOT_QQ, NICKNAME, SUPER_USER  # noqa: F401 —— 身份配置单一来源 config.yaml
```

（放在文件顶部 import 区；`super_user()` 方法与各插件的 `from core.base import ...` 不动。）

- [ ] **Step 4: 改 `core/context.py`**

把：

```python
llonebot_data_path = "/app/llonebot/server_data"    # 使用api是用这个地址
python_data_path = "./server_data"                  # 在python脚本中访问用这个地址
onebot_qq_volume = "/var/lib/docker/volumes/onebot_qq_volume/_data"
```

与

```python
DEFAULT_GROUP_ID = 296470819 # 在这里填写你想固定使用的群号
```

替换为（顶部 import 区加）：

```python
from core import config as _config

llonebot_data_path = _config.LLONEBOT_DATA_PATH    # 使用api是用这个地址（config.yaml）
python_data_path = _config.PYTHON_DATA_PATH        # 在python脚本中访问用这个地址
onebot_qq_volume = _config.ONEBOT_QQ_VOLUME
```

与

```python
DEFAULT_GROUP_ID = _config.DEFAULT_GROUP_ID  # 固定群号（config.yaml bot.default_group）
```

注意：**保持模块属性形式**（不用 `from ... import` 直接绑定），测试大量 patch `context.python_data_path`。

- [ ] **Step 5: 改 `main.py`**

删除顶部整个 env 注入块（`_ENV_FILE = ...` 到 `os.environ.setdefault(...)` 循环，含注释），改为：

```python
import time
import threading
import json as json_

from datetime import datetime
from core import api
from core.config import WS_URL, WS_TOKEN
from core.logger import logger
import core.context as runtime_context
import plugins # 一定要导入，否则不能正常读取插件
runtime_context.migrate_group_plugin_config()

import websocket  # pyright: ignore[reportMissingImports]
```

并删除：

```python
# WS_URL = "ws://192.168.0.103:3001"   # 本机调试用
WS_URL = "ws://127.0.0.1:3001"   # WebSocket 地址
token = 123456
```

`__main__` 块中 `header=[f"Authorization: Bearer {token}"]` 改为 `header=[f"Authorization: Bearer {WS_TOKEN}"]`。

- [ ] **Step 6: 全量回归**

Run: `pytest`
Expected: 全部通过

- [ ] **Step 7: 验收 grep**

Run: `grep -rn "1057613133\|3915014383\|296470819\|小埃同学\|3001\|/app/llonebot" core/ plugins/ webapp/ main.py --include="*.py"`
Expected: 仅 `webapp/` 下的 SUPER/GROUP_ID 消费处与测试类文件命中——具体为 `webapp/activities/app.py`（`from core.base import SUPER_USER`，无字面量）应零命中；若有字面量命中逐个改为 import config。

- [ ] **Step 8: Commit**

```bash
git add core/base.py core/context.py main.py test/test_config_wiring.py
git commit -m "refactor(配置): QQ/群号/WS/数据路径等身份常量迁入 config.yaml"
```

---

### Task 3: 代理与散落读取点统一

**Files:**
- Modify: `core/utils.py:82-89`（download_image 的 proxies）
- Modify: `plugins/random_reference/__init__.py:17-24`
- Modify: `webapp/tools/icon.py:25`
- Modify: `webapp/live/app.py:20`
- Modify: `core/character_store.py:20`
- Modify: `core/user_settings.py:26`

**Interfaces:**
- Consumes: Task 1 的 `DOWNLOAD_PROXY`（str，空=直连）、`ICON_PROXY`（str|None）、`LIVE_FLV_URL`、`TRPG_CHARS_ROOT`、`USER_SETTINGS_ROOT`
- Produces: 无（终点消费）

- [ ] **Step 1: 改 `core/utils.py::download_image`**

把：

```python
        proxies = {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890"
        }

        response = requests.get(url, proxies=proxies, timeout=30)
```

替换为：

```python
        from core.config import DOWNLOAD_PROXY
        proxies = {"http": DOWNLOAD_PROXY, "https": DOWNLOAD_PROXY} if DOWNLOAD_PROXY else None

        response = requests.get(url, proxies=proxies, timeout=30)
```

（函数内 import 是刻意的：`core/utils.py` 顶部 import `core.config` 会与 `core.config` → 无环，但保持函数内 import 零风险；若顶部 import 无环告警则提到顶部。）

- [ ] **Step 2: 改 `plugins/random_reference/__init__.py::_resolve_image_url`**

把：

```python
        proxies = {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890",
        }
```

替换为：

```python
        from core.config import DOWNLOAD_PROXY
        proxies = {"http": DOWNLOAD_PROXY, "https": DOWNLOAD_PROXY} if DOWNLOAD_PROXY else None
```

（保留原有 try/except 直连重试结构不动。）

- [ ] **Step 3: 改 `webapp/tools/icon.py`**

把：

```python
PROXY = os.environ.get("BOTERO_ICON_PROXY")  # 可选：如 "http://127.0.0.1:7890"
```

替换为：

```python
from core.config import ICON_PROXY as PROXY  # 可选代理，None = 直连（config.yaml tools.icon_proxy）
```

（若 `os` 之后不再使用，顺手删掉 `import os`。）

- [ ] **Step 4: 改 `webapp/live/app.py`**

把：

```python
# 直播流地址（方案 A 状态探测与页面播放同源 URL；环境变量可覆盖，便于本地联调）
LIVE_FLV_URL = os.environ.get("BOTERO_LIVE_FLV_URL", "https://live.littlero.tech/live/livestream.flv")
```

替换为：

```python
from core.config import LIVE_FLV_URL  # 直播流地址（config.yaml live.flv_url 可覆盖，便于本地联调）
```

- [ ] **Step 5: 改 `core/character_store.py` 与 `core/user_settings.py`**

`character_store.py` 删除：

```python
CHARS_ROOT = Path(os.environ.get("BOTERO_TRPG_CHARS_ROOT", "server_data/trpg_chars"))
```

顶部 import 区改为：

```python
from core.config import TRPG_CHARS_ROOT as CHARS_ROOT
```

`user_settings.py` 同理：

```python
from core.config import USER_SETTINGS_ROOT as SETTINGS_ROOT
```

（两文件的 `import os` 若无其他使用则删除；模块属性名不变，现有 patch 继续有效。）

- [ ] **Step 6: 全量回归**

Run: `pytest`
Expected: 全部通过

- [ ] **Step 7: 验收 grep**

Run: `grep -rn "7890\|BOTERO_ICON_PROXY\|BOTERO_LIVE_FLV_URL\|BOTERO_TRPG_CHARS_ROOT\|BOTERO_USER_SETTINGS_ROOT" core/ plugins/ webapp/ main.py --include="*.py"`
Expected: 零输出

- [ ] **Step 8: Commit**

```bash
git add core/utils.py plugins/random_reference/__init__.py webapp/tools/icon.py webapp/live/app.py core/character_store.py core/user_settings.py
git commit -m "refactor(配置): 下载代理与散落环境变量读取统一进 config.yaml"
```

---

### Task 4: 启动参数清理 + 仓库收尾（配置退出 git）

**Files:**
- Modify: `webapp/__main__.py`
- Delete: `scripts/botero.env`（`git rm`）
- Modify: `scripts/botero-web.service:7`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 无
- Produces: 仓库不再含任何真实配置值；`config.yaml` 被 gitignore

- [ ] **Step 1: 清理 `webapp/__main__.py`**

把：

```python
    parser.add_argument("--db", default=None, help="data.db 路径")
    parser.add_argument("--images", default=None, help="record_images 根目录")
    args = parser.parse_args()

    if args.db:
        os.environ["BOTERO_DB_PATH"] = os.path.abspath(args.db)
    if args.images:
        os.environ["BOTERO_IMAGE_ROOT"] = os.path.abspath(args.images)

    db = os.environ.get("BOTERO_DB_PATH", str(DB_PATH))
    images = os.environ.get("BOTERO_IMAGE_ROOT", str(IMAGE_ROOT))
    print(f"数据库: {db}")
    print(f"图片目录: {images}")
```

替换为：

```python
    args = parser.parse_args()

    print(f"数据库: {DB_PATH}")
    print(f"图片目录: {IMAGE_ROOT}")
```

（import 行里不再用到的 `os` 与 `DB_PATH`/`IMAGE_ROOT` 按实际情况清理：`DB_PATH`/`IMAGE_ROOT` 仍用于打印则保留 import，`os` 删除。）

- [ ] **Step 2: 删除 `scripts/botero.env`**

```bash
git rm scripts/botero.env
```

（真实值已在 Task 1 Step 10 并入本机 `config.yaml`；VPS 侧迁移见本计划末尾「部署迁移清单」。）

- [ ] **Step 3: 改 `scripts/botero-web.service`**

删除第 7 行：

```
EnvironmentFile=/home/dore/onebot/Bot_Ero/scripts/botero.env
```

（webapp 进程改为直接读项目根 `config.yaml`。）

- [ ] **Step 4: 改 `.gitignore`**

在 `pyrightconfig.json` 行后追加：

```
config.yaml
```

- [ ] **Step 5: 冒烟验证（缺配置拒绝启动）**

```bash
mv config.yaml config.yaml.bak
python main.py; echo "exit=$?"   # 预期：打印 cp config.example.yaml 提示并退出，exit 非 0
python -m webapp --port 18765; echo "exit=$?"   # 同上
mv config.yaml.bak config.yaml
```

Expected: 两条命令都带 `config.example.yaml` 提示退出。

- [ ] **Step 6: 全量回归 + 仓库检查**

Run: `pytest` → 全部通过
Run: `git ls-files | grep -E "config.yaml|botero.env"` → 零输出（example 文件名是 `config.example.yaml`，不匹配 `config.yaml$`——若匹配到说明误提交，立即 `git rm --cached`）

- [ ] **Step 7: Commit**

```bash
git add webapp/__main__.py scripts/botero.env scripts/botero-web.service .gitignore
git commit -m "chore(配置): 移除 botero.env 与失效启动参数，config.yaml 退出 git 跟踪"
```

---

### Task 5: 文档同步 + CHANGELOG + 版本发布

**Files:**
- Modify: `kb/QUICK_REFERENCE.md`、`kb/OPERATIONS.md`、`kb/CONVENTIONS.md`、`CLAUDE.md`、`AGENTS.md`、`specs/conventions.md`、`docs/web-apps-deployment.md`、`CHANGELOG.md`
- Modify: `core/config.py`（`BOTERO_VERSION` → `"1.32.0"`）

**Interfaces:**
- Consumes: 前 4 个任务的最终形态
- Produces: 版本 1.32.0 发布；spec 验收标准全部满足

- [ ] **Step 1: `kb/QUICK_REFERENCE.md`**

- 「项目身份」段改为：全部身份值在 `config.yaml`（bot 节），代码零硬编码
- 「硬编码常量」表：删除 WS URL/WS Token/默认群号/超级用户/Bot QQ/Bot 昵称/下载代理/双数据路径/OneBot 数据路径 9 行；表格重命名为「代码内常量（非配置）」；新增一节「配置文件 `config.yaml`」：11 节键表（照抄 `config.example.yaml` 的节名与键名，标注必填/可选/默认值），并注明 `BOTERO_CONFIG` 定位机制
- 「常用路径」段加一句：路径可经 `config.yaml` 的 `paths`/`thumbs` 节覆盖

- [ ] **Step 2: `kb/OPERATIONS.md`**

- 第 23 行盐说明改为：登录密钥盐在 `config.yaml` 的 `auth.salt`（bot 与 webapp 共读同一文件；换盐把旧盐追加到 `auth.old_salts` 列表）
- 第 25 行 `BOTERO_LIVE_FLV_URL` → `config.yaml` `live.flv_url`
- 第 37 行周报三个 env → `config.yaml`（`paths.message_log_db`、`weekly.web_base_url`、`weekly.notify`）
- 全文 `BOTERO_*` 环境变量表（若在「部署」节存在）改为 config.yaml 键表 + `BOTERO_CONFIG` 一行说明

- [ ] **Step 3: `kb/CONVENTIONS.md`**

- 第 69 行「配置半环境变量化」改为：「配置统一 `config.yaml`（`core/config.py` import 时加载，`yaml.safe_load`）；`BOTERO_CONFIG` 环境变量仅用于定位配置文件」
- 第 74 行删除（`--db` 参数已删）
- 第 78 行盐单一来源改为 `config.yaml`
- 第 79 行 `BOTERO_AUTH_SALT_OLD` → `auth.old_salts`
- 第 122 行「--db 静默无效」陷阱整段替换为：「配置在 `core.config` import 时冻结；要换配置，改 `config.yaml` 后重启进程，或启动前设 `BOTERO_CONFIG` 指向别的文件」
- 第 153 行 `BOTERO_DB_PATH` 注入 → `BOTERO_CONFIG=<临时配置> python3 -m webapp`

- [ ] **Step 4: `CLAUDE.md`**

- 第 56 行：`config.py` 行改为「统一配置 `config.yaml` 读取（bot 与 webapp 共用；`BOTERO_CONFIG` 可定位文件）」
- 第 86 行：盐单一来源 `scripts/botero.env` → `config.yaml` 的 `auth.salt`
- 第 87 行：`BOTERO_*` 环境变量口径 → `config.yaml` 口径

- [ ] **Step 5: `AGENTS.md`**

- Toolchain reality 段「环境变量单一来源 `scripts/botero.env`」整条改为：「配置单一来源 `config.yaml`（gitignore，模板 `config.example.yaml`）：`core/config.py` import 时经 `yaml.safe_load` 加载；`BOTERO_CONFIG` 环境变量仅用于定位文件（测试用）」
- 「Hardcoded values (no config file)」表整节删除，替换为一句：「部署值全部在 `config.yaml`；代码内仅剩算法常量（见 `kb/QUICK_REFERENCE.md`）」
- 「Two path constants — one data」表保留，加注来源变为 `config.yaml` `bot.llonebot_data_path`/`bot.python_data_path`

- [ ] **Step 6: `specs/conventions.md`**

- 第 129 行 `BOTERO_IMAGE_ROOT` → `config.yaml` `paths.images`
- 第 250 行「以上六个值仍硬编码」段整段改写：配置统一 `config.yaml`，环境变量机制已移除（仅 `BOTERO_CONFIG` 定位文件）

- [ ] **Step 7: `docs/web-apps-deployment.md`**

- 第 52 行 unit 片段删 `EnvironmentFile=` 行（与 Task 4 的 service 文件一致）
- 第 62/75 行盐说明：`scripts/botero.env` → `config.yaml`（`auth.salt`/`auth.old_salts`）
- 第 109-116 行环境变量表 → config.yaml 键表
- 增加「首次部署」小节：`cp config.example.yaml config.yaml` 填值 → `systemctl daemon-reload`

- [ ] **Step 8: CHANGELOG + 版本 bump**

`core/config.py`：`BOTERO_VERSION = "1.32.0"`。

`CHANGELOG.md` 顶部新增（保持现有格式）：

```markdown
## [1.32.0] - 2026-08-31

### 变更
- 配置统一为项目根 `config.yaml`（YAML）：QQ 号、超管、默认群、WS 地址/token、数据路径、下载代理等原硬编码值与全部 `BOTERO_*` 环境变量合并为单一配置文件；真实配置退出 git（模板 `config.example.yaml`）
- `BOTERO_CONFIG` 环境变量仅用于定位配置文件（测试与多环境部署）
- 移除 `webapp` 失效的 `--db`/`--images` 启动参数与 `scripts/botero.env`
- 部署迁移：`cp config.example.yaml config.yaml` 填真实值并重启；systemd unit 移除 EnvironmentFile 后 daemon-reload
```

- [ ] **Step 9: 执行 spec 验收标准（逐条跑命令）**

1. `grep -rn "os.environ" --include="*.py" core/ main.py webapp/ plugins/ test/ | grep -v BOTERO_CONFIG | grep -v WINDIR | grep -v test_llm` → 零输出
2. `grep -rn "1057613133\|3915014383\|296470819\|127.0.0.1:7890\|192.168.0.103" core/ plugins/ webapp/ main.py --include="*.py"` → 零输出（与 spec 口径一致：测试与文档除外，故不 grep test/）
3. `pytest` → 全绿
4. Task 4 Step 5 已验证过缺配置拒绝启动
5. `git ls-files | grep -E "config.yaml$|botero.env"` → 零输出

- [ ] **Step 10: Commit**

```bash
git add kb/QUICK_REFERENCE.md kb/OPERATIONS.md kb/CONVENTIONS.md CLAUDE.md AGENTS.md specs/conventions.md docs/web-apps-deployment.md CHANGELOG.md core/config.py
git commit -m "feat(配置): 统一配置文件 config.yaml 发布 1.32.0，文档全面切换"
```

---

## 部署迁移清单（代码合并后、上线前人工执行，不属于任何 commit）

1. **本机**：确认 `config.yaml` 已按 Task 1 Step 10 生成且 bot / webapp 本地启动正常
2. **VPS**：
   ```bash
   cd /home/dore/onebot/Bot_Ero && git pull
   cp config.example.yaml config.yaml   # 然后编辑：填生产值（身份/盐/token 照抄原 botero.env 与生产实际）
   pip install PyYAML                   # 或 pip install -r requirements.txt
   sudo systemctl edit botero-web 之外：直接改 scripts/botero-web.service 已在仓库更新，执行 sudo systemctl daemon-reload
   sudo systemctl restart botero-web    # webapp
   # bot 进程（llonebot 容器侧）：重启 bot 主进程
   ```
3. VPS `config.yaml` 的 `live.flv_url` 填 `http://127.0.0.1:18080/live/livestream.flv`（原 systemd `Environment=BOTERO_LIVE_FLV_URL` 的本机 SRS 直连覆盖值，见 `scripts/botero-web.service` 注释）
4. VPS 上的 `scripts/botero.env` 会被 git pull 自动删除（已 `git rm`），其值必须已并入 `config.yaml` 再重启
5. 验证：webapp 首页可登录（盐一致）、bot 上线心跳正常、`/图库密钥` 生成的旧密钥仍可登录（old_salts 为空且盐未变则天然一致）

## Self-Review 记录

- **Spec 覆盖**：spec ①（文件与加载）→ Task 1；②（结构与映射）→ Task 1 Step 4/5；③（改动面表 10 行）→ Task 2（base/context/main/env 删除）、Task 3（utils/random_reference/icon/live/character_store/user_settings）、Task 4（__main__/botero.env/service/.gitignore）；④（测试与部署）→ Task 1 Steps 6-9 + 部署迁移清单；⑤（文档）→ Task 5。无缺口
- **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码
- **类型一致性**：`WS_TOKEN` 在 main.py 消费处、`DOWNLOAD_PROXY` 空=直连语义在 utils/random_reference 一致；`write_config` 返回 str 路径在 conftest/check 脚本一致
