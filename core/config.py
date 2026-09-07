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
BOTERO_VERSION = "1.35.2"

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

# —— cloud-mail 邮件（可选；url/email/password 留空 = 功能关闭）——
_mail = _sec("mail")
CLOUDMAIL_URL = str(_mail.get("url") or "")
CLOUDMAIL_EMAIL = str(_mail.get("email") or "")
CLOUDMAIL_PASSWORD = str(_mail.get("password") or "")
CLOUDMAIL_SENDER_NAME = str(_mail.get("sender_name") or "")
