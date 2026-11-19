# 准备中卡片排除机器人 — 验收记录

实施分支：`master`；版本 1.99.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 机器人自己不进名单 | `check_trpg_party_api.py`：「机器人不进名单」输出 `['12345601', '12345602', '12345603', '12345699']` | 通过 |
| AC02 别的机器人也不进 | 同上（假成员里含 `is_robot: True` 的 `2222333`） | 通过 |
| AC03 用例能抓住回归 | 临时把过滤改回只判 `is_robot` 重跑 → `FAIL - 机器人不进名单 [..., '3915014383']`；恢复后 ok | 通过 |
| AC04 真人名单不受影响 | 同一用例中 DM / 玩家 / 观察者 / 未准备路人仍在名单里 | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **977 passed**（5:34） | 通过 |
| AC06 文档与归档 | `openspec validate trpg-party-roster --strict` valid；`CHANGELOG [1.99.1]` 与 `BOTERO_VERSION = "1.99.1"` 一致；同一 commit 归档 | 通过 |

## 根因

| 位置 | 过滤条件 | 结果 |
|---|---|---|
| `plugins/trpg_session`（群内 `/跑团` 卡片） | `not is_robot and user_id != BOT_QQ` | 正确 |
| `webapp/trpg/app.py::_pending_roster`（网页准备中卡片） | 只有 `not is_robot` | 机器人自己漏进来 |

OneBot 成员列表的 `is_robot` 标的是「其他机器人账号」，机器人自身的账号通常为 false，所以单靠该字段无法排除自己。

## 修复

```python
bot_qq = str(core_config.BOT_QQ)
humans = [m for m in (group_members or [])
          if not m.get("is_robot") and str(m.get("user_id")) != bot_qq]
```
