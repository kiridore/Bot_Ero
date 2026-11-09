"""文案包：bot.text_pack 指向的 yaml 覆盖内置文案，缺键回落默认。启动一次加载，重启生效。

键粒度按文案单元（如 menu_text）；包内 {NICKNAME} 占位符替换为配置昵称。
"""
import logging
from pathlib import Path

import yaml

from core import config

logger = logging.getLogger(__name__)
_pack: dict = {}

if config.TEXT_PACK:
    try:
        _loaded = yaml.safe_load(Path(config.TEXT_PACK).read_text(encoding="utf-8"))
        if isinstance(_loaded, dict):
            _pack = _loaded
            if "menu_text" in _pack:
                # 旧整段菜单覆盖已停用（config-unification）：菜单按有效插件过滤，文字不能绕过
                logger.warning(
                    "文案包含 menu_text 整段覆盖：已停用并忽略，菜单改用结构化条目（menu.<指令词> 逐条覆盖）；请迁移")
        else:
            logger.warning("文案包顶层不是映射，忽略: %s", config.TEXT_PACK)
    except Exception:
        logger.exception("文案包加载失败，回落内置文案: %s", config.TEXT_PACK)


def get_text(key: str, default: str) -> str:
    val = _pack.get(key)
    if isinstance(val, str) and val.strip():
        # replace 而非 format：对包作者误写的花括号免疫
        return val.replace("{NICKNAME}", config.NICKNAME)
    return default
