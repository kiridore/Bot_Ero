"""BotEro 共享配置：bot 与全部 Web 子应用共用的环境变量读取。"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 当前版本（单一来源，随 CHANGELOG.md 同步更新）
BOTERO_VERSION = "1.19.0"

def _path_from_env(key: str, default: Path) -> Path:
    raw = os.environ.get(key)
    return Path(raw) if raw else default


DB_PATH = _path_from_env("BOTERO_DB_PATH", PROJECT_ROOT / "data.db")
MESSAGE_LOG_DB_PATH = _path_from_env(
    "BOTERO_MESSAGE_LOG_DB_PATH", PROJECT_ROOT / "server_data" / "message_log.db"
)
IMAGE_ROOT = _path_from_env("BOTERO_IMAGE_ROOT", PROJECT_ROOT / "server_data" / "record_images")
TRPG_CHARS_ROOT = _path_from_env(
    "BOTERO_TRPG_CHARS_ROOT", PROJECT_ROOT / "server_data" / "trpg_chars"
)
USER_SETTINGS_ROOT = _path_from_env(
    "BOTERO_USER_SETTINGS_ROOT", PROJECT_ROOT / "server_data" / "user_settings"
)
ACTIVITY_ROOT = _path_from_env(
    "BOTERO_ACTIVITY_ROOT", PROJECT_ROOT / "server_data" / "activity_archive"
)
HOST = os.environ.get("BOTERO_GALLERY_HOST", "0.0.0.0")
PORT = int(os.environ.get("BOTERO_GALLERY_PORT", "8765"))
PAGE_SIZE_DEFAULT = 40
PAGE_SIZE_MAX = 100

REMEDY_MARKER = "remedy_checkin"

# OneBot HTTP（NapCat / Lagrange 等），用于拉取 QQ 昵称
ONEBOT_HTTP_URL = os.environ.get("BOTERO_ONEBOT_HTTP", "http://192.168.0.103:3000")
ONEBOT_TOKEN = os.environ.get("BOTERO_ONEBOT_TOKEN", "123456")
GROUP_ID = int(os.environ.get("BOTERO_GROUP_ID", "296470819"))

# 小埃周报：Web 基址（群通知链接）与通知开关
WEB_BASE_URL = os.environ.get("BOTERO_WEB_BASE_URL", "https://littlero.tech").rstrip("/")
WEEKLY_NOTIFY_ENABLED = os.environ.get("BOTERO_WEEKLY_NOTIFY", "0") == "1"

THUMB_CACHE_DIR = _path_from_env(
    "BOTERO_THUMB_CACHE",
    PROJECT_ROOT / "server_data" / "thumb_cache",
)
THUMB_MAX_WIDTH = int(os.environ.get("BOTERO_THUMB_MAX_WIDTH", "480"))
THUMB_MAX_HEIGHT = int(os.environ.get("BOTERO_THUMB_MAX_HEIGHT", "720"))
THUMB_JPEG_QUALITY = int(os.environ.get("BOTERO_THUMB_QUALITY", "82"))

# 图库登录密钥（QQ 号 + 盐 → HMAC → Base64）
AUTH_SALT = os.environ.get("BOTERO_AUTH_SALT", "BotEro-Gallery-ChangeMe")
# 历史盐列表（逗号分隔）：换盐后旧密钥仍可验证，实现无感迁移
AUTH_SALT_OLD = [s for s in os.environ.get("BOTERO_AUTH_SALT_OLD", "").split(",") if s.strip()]

# 网页打卡上传
CHECKIN_MAX_IMAGES = int(os.environ.get("BOTERO_CHECKIN_MAX_IMAGES", "9"))
CHECKIN_MAX_BYTES = int(os.environ.get("BOTERO_CHECKIN_MAX_BYTES", str(10 * 1024 * 1024)))

# 议事厅正文图片上传
FORUM_IMAGES_ROOT = _path_from_env("BOTERO_FORUM_IMAGES_ROOT", PROJECT_ROOT / "server_data" / "forum_images")
FORUM_IMAGE_MAX_BYTES = int(os.environ.get("BOTERO_FORUM_IMAGE_MAX_BYTES", str(10 * 1024 * 1024)))

# 社区时间线（Event Server 基地址与系统间事件令牌）
TIMELINE_URL = os.environ.get("BOTERO_TIMELINE_URL", "http://127.0.0.1:8765")
TIMELINE_TOKEN = os.environ.get("BOTERO_EVENT_TOKEN", "BotEro-Timeline-ChangeMe")
