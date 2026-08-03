import os
from pathlib import Path

# 项目根目录（checkin_gallery 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _path_from_env(key: str, default: Path) -> Path:
    raw = os.environ.get(key)
    return Path(raw) if raw else default


DB_PATH = _path_from_env("BOTERO_DB_PATH", PROJECT_ROOT / "data.db")
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

THUMB_CACHE_DIR = _path_from_env(
    "BOTERO_THUMB_CACHE",
    PROJECT_ROOT / "server_data" / "thumb_cache",
)
THUMB_MAX_WIDTH = int(os.environ.get("BOTERO_THUMB_MAX_WIDTH", "480"))
THUMB_MAX_HEIGHT = int(os.environ.get("BOTERO_THUMB_MAX_HEIGHT", "720"))
THUMB_JPEG_QUALITY = int(os.environ.get("BOTERO_THUMB_QUALITY", "82"))

# 图库登录密钥（QQ 号 + 盐 → HMAC → Base64）
AUTH_SALT = os.environ.get("BOTERO_AUTH_SALT", "BotEro-Gallery-ChangeMe")

# 网页打卡上传
CHECKIN_MAX_IMAGES = int(os.environ.get("BOTERO_CHECKIN_MAX_IMAGES", "9"))
CHECKIN_MAX_BYTES = int(os.environ.get("BOTERO_CHECKIN_MAX_BYTES", str(10 * 1024 * 1024)))
