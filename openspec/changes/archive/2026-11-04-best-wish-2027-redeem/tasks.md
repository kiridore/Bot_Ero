# 实施与验收任务

## 1. 兑换码与称号定义
- [x] 1.1 `webapp/profile/redeem_service.py`：`CODE_PATTERN` 放宽为 `[A-Z0-9]{4}` 三段、格式错误文案改「大写字母或数字」；新增 `BEST-WISH-2027` 条目与回调（同事务解锁 503/504/505，返回奖励说明）。对应 AC01/AC02。
- [x] 1.2 `plugins/title/defs.py`：新增 503「神秘」、504「大」、505「烤鱼」，rarity 全 `rare`、`unlock_type: redeem`、简介逐字为「感谢你购买烤鱼2027板油日历，祝你2027一切都好」。对应 AC04。

## 2. QQ 提示桩插件
- [x] 2.1 重建 `plugins/redeem_code/__init__.py`（CommandPlugin，`/兑换码` `/兌換碼`）：撤回＋无条件迁移提示，不碰数据库；`core/feature_packs.py` 仅引用 `redeem_shop`，无需改动。对应 AC03。

## 3. 测试
- [x] 3.1 扩展 `test/scripts/check_redeem_web.py`：新码成功三称号、重复拒、小写归一、含数字格式错拒绝不写库、错误文案断言。对应 AC01/AC02。
- [x] 3.2 新增 `test/test_redeem_code_stub.py`（`MockApiWrapper` 补 `delete_msg` 记录桩、`make_*_message` 支持自定义 `message_id`）：匹配/繁体别名/撤回失败仍提示/私聊/非指令不匹配。对应 AC03。

## 4. 文档与交付
- [x] 4.1 同步 `kb/GAMEPLAY.md`（兑换码称号行 501–505）、`kb/PLUGIN_CATALOG.md`（45 号提示桩、计数 47）、`kb/QUICK_REFERENCE.md`（指令表补 `/兑换码` 行）、`specs/plugin-catalog.md`、CHANGELOG `[1.61.0]`＋bump `BOTERO_VERSION`。
- [x] 4.2 全量 `python -m pytest -q` 绿（521 passed）；`openspec validate best-wish-2027-redeem --strict` 通过；归档（含手动对齐 spec Purpose 段）与实现同一提交，推 master。
