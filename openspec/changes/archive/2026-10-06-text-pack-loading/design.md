# 设计 · 文案包加载机制（T0.8）

## 核心组件

```python
# core/text_pack.py（全文）
"""文案包：bot.text_pack 指向的 yaml 覆盖内置文案，缺键回落默认。启动一次加载。"""
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
        else:
            logger.warning("文案包顶层不是映射，忽略: %s", config.TEXT_PACK)
    except Exception:
        logger.exception("文案包加载失败，回落内置文案: %s", config.TEXT_PACK)

def get_text(key: str, default: str) -> str:
    val = _pack.get(key)
    if isinstance(val, str) and val.strip():
        return val.replace("{NICKNAME}", config.NICKNAME)
    return default
```

`{NICKNAME}` 用 `str.replace` 而非 `str.format`：对包作者误写的花括号免疫（format 会 KeyError 崩加载）。

## 消费方（唯一）

```python
# plugins/menu/__init__.py handle()
self.api.send_forward_msg([text(get_text("menu_text", BOT_MENU_TEXT))])
```

惰性求值（handle 期查询而非 import 期绑定）：测试直接 `mock.patch.object(core.text_pack, "_pack", {...})` 即可断言，无需 reload menu 模块（reload 会向 plugin_registry 追加重复类）。

## 设计要点

- **不 ship `text_packs/private.yaml`**：内置基线 ≡ 私有文案，双份存储必然漂移；私有部署不配 `text_pack` 即原样。owner 后续改私有菜单 → 仍改 `bot_menu_text.py`（AGENTS.md"指令文本唯一来源"惯例不变）
- **键粒度**：今日仅 `menu_text` 一键；M1 注册引导语 / T2.4 群欢迎语等后续文案单元加键即可，机制零改动
- **无热重载**：与 config.yaml 同语义（重启生效）

## text_packs/community.yaml 草稿结构

- 指令集 = T0.7 草案"打卡基础+经济扩展"两包 + 管理员指令；**不含** 仙人彩/FF新闻/跑团/卧底/活动/闹钟/占卜/随机参考（批次 2/3 或私域）
- 触发词不改（改名指令是独立任务），仅描述中性化：`/本周板油 查看本周打卡成员`
- 无"喵"/"板油"/FF14 字样；`{NICKNAME}` 占位替换人设名
- 头部注释标注"草稿，T2.4 定稿"

## 测试策略（`test/test_text_pack.py`）

get_text 单元（mock.patch `_pack`）：覆盖/缺键/空串/null/非字符串/{NICKNAME} 替换 六向；
坏包降级（临时目录写坏 yaml + mock.patch.object(config, "TEXT_PACK", path) 后 `importlib.reload(core.text_pack)`，断言 WARNING 且 `_pack == {}`，finally reload 还原）；
community.yaml 静态断言：合法 yaml、含 menu_text、含 {NICKNAME}、不含私域词。
