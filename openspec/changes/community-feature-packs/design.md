# 设计 · 功能包双表与打卡-经济解耦（T0.7）

## 双表结构（core/feature_packs.py 全文重写）

```python
"""功能包表（双形态接缝 #2）：按 bot.edition 选表；私有 = 历史全量，社区 = 按批次释出。"""
from core.config import EDITION

_PACKS_PRIVATE = {  # 私有形态：与改造前逐项一致（勿动）
    "基础包": {... 现 9 插件原样 ...},
    "基础扩展包": {... 现 6 插件原样 ...},
    "休闲娱乐": {...}, "匿名游戏": {...}, "跑团": {...}, "群管理工具": {...},
}

_PACKS_COMMUNITY = {
    "打卡基础": {  # 批次 1（所有者 2026-10-06 拍板）：不含补卡/积分排行/经济
        "plugins": [
            "checkin", "checkin_recall", "roll_back",
            "week_checkin_display", "all_checkin_display",
            "week_list", "personal_records",
        ],
    },
    # 批次 2 待释（释出时移入表）：娱乐工具(group_alarm/dice/divination/random_reference)
    #   活动(activity)、匿名游戏(who_is_spy)、群管理工具(group_essence/recall_message/set_group_title，默认关)
    # 批次 3 待释：跑团(trpg_dice/trpg_session/trpg_char)；经济扩展是否释出另议
}

FEATURE_PACKS = _PACKS_COMMUNITY if EDITION == "community" else _PACKS_PRIVATE

def economy_active() -> bool:
    """经济能力（积分/称号/周常）是否在本部署可用——社区批次 1 为 False。"""
    return "基础扩展包" in FEATURE_PACKS
```

消费方 `plugins/group_manager` 只 `from core.feature_packs import FEATURE_PACKS` 并迭代——零改动。

## 打卡域门控（4 文件，if 包裹保持位置，私有 True 直通零重排）

- `plugins/checkin/__init__.py` 三处：
  1. `unlocked = evaluate_and_unlock_titles(...)` 及其消息块 → `if economy_active():` 内
  2. `checkin_luck_bonus` 块（`shop.pop_luck`——经济道具，顺带纳入）→ 同
  3. 月全勤 + bonus_total + `add_user_point` + 周常 `on_quest_trigger` 行 → 同
- `plugins/roll_back/__init__.py` / `plugins/checkin_recall/__init__.py`：`on_quest_rollback` 调用 → `if economy_active():`

`from core import feature_packs` 模块导入（属性访问，测试可 patch `feature_packs.economy_active`）。门控块内代码逐字不动——位置原样包裹，私有形态消息组装顺序逐字节等价。

## 菜单同步（text_packs/community.yaml）

剔除：/补卡 /单日补卡 /周常 /抽奖 /抽卡 /一键抽奖 /抽卡消费 /排名 /rank /商店 /兑换码 /称号×7 /超级补卡 /超级单日补卡 /发金币 /刷新商店。保留：/菜单 /打卡 /档案 /本周打卡图 /ALL /撤回打卡 /本周板油 /召唤 + 管理员（/数据备份 /系统状态 /更新 /插件 /功能包）。

## 测试策略（test/test_feature_packs.py）

1. 双表：`importlib.reload` + patch `core.config.EDITION` 断言私有表 == 硬编码期望全量、社区表 == 仅打卡基础 7 项；`economy_active()` 两态
2. 解耦（核心，真实临时 DB + Event 构造）：patch `feature_packs.economy_active → False`，构造带图消息事件跑 `CheckinPlugin.handle()`——断言 `user_assets` 无积分行/积分 0、`quest_progress` 空、mock 层断言 `evaluate_and_unlock_titles` 未被调用；对照 `→ True` 时积分/周常有写入（等价回归）
3. 菜单 grep 断言：剔除 13 指令零出现、保留项在
4. 撤回侧：patch False 后 `on_quest_rollback` 零调用（mock）

Event/api 构造参照 `test/test_lottery_bulk.py`（Event + fake api 已有先例）。

## 风险

- checkin.handle 重组装风险 → 门控用最小侵入（原块整体缩进，不改内部代码）；既有用例（checkin/title/quest/lottery）+ 新增对照断言双保险
- community.yaml 与 T0.8 测试（test_no_private_jargon）兼容：剔除指令后 grep 断言集更新
