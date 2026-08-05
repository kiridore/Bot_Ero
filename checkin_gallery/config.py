"""Web 配置（兼容层）：常量全部来自 core.config，保持旧 import 不破坏。"""

from core.config import *  # noqa: F401,F403
from core.config import (
    AUTH_SALT,
    CHECKIN_MAX_BYTES,
    CHECKIN_MAX_IMAGES,
    DB_PATH,
    GROUP_ID,
    HOST,
    IMAGE_ROOT,
    ONEBOT_HTTP_URL,
    ONEBOT_TOKEN,
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    PORT,
    PROJECT_ROOT,
    REMEDY_MARKER,
    THUMB_CACHE_DIR,
    THUMB_JPEG_QUALITY,
    THUMB_MAX_HEIGHT,
    THUMB_MAX_WIDTH,
    ACTIVITY_ROOT,
    TRPG_CHARS_ROOT,
    USER_SETTINGS_ROOT,
)
