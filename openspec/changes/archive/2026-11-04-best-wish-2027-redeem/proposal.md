# 烤鱼2027板油日历兑换码 BEST-WISH-2027 + `/兑换码` 迁移提示桩

## Why

所有者指令（2026-11-04）：
1. 新增兑换码 `BEST-WISH-2027`，随「烤鱼2027板油日历」周边发售，购买者凭码解锁三个彩蛋称号「神秘」「大」「烤鱼」（连读为「神秘大烤鱼」），简介统一为感谢与祝福语。
2. QQ 群内使用 `/兑换码` 指令会把兑换码明文暴露在群里，且该功能已在 1.58.0 迁至网页；需要拦截该指令：撤回原消息，并提示功能已迁移至网页个人主页，防止兑换码在群聊泄露、引导用户到正确入口。

现行为（与目标的冲突点）：`openspec/specs/redeem-codes/spec.md` 规定「QQ 指令移除……机器人无任何响应」，本提案把它反转为「撤回＋迁移提示」；同时兑换码格式校验仅允许大写字母，`BEST-WISH-2027` 第三段含数字，需放宽。

## What Changes

- **兑换码格式放宽**：`CODE_PATTERN` 每段由 `[A-Z]{4}` 放宽为 `[A-Z0-9]{4}`（仍全大写、三段式）；格式错误文案改为「应为 XXXX-XXXX-XXXX（大写字母或数字）」。
- **新兑换码 `BEST-WISH-2027`**（`webapp/profile/redeem_service.py` 注册表新条目）：同一事务内解锁三个称号（503「神秘」、504「大」、505「烤鱼」），回调失败整体回滚，沿用既有一次性/原子性语义；描述为「烤鱼2027板油日历专属：解锁「神秘」「大」「烤鱼」称号」。
- **三个新称号**（`plugins/title/defs.py`，`unlock_type: redeem`，稀有度全部 `rare`）：简介统一「感谢你购买烤鱼2027板油日历，祝你2027一切都好」。
- **QQ 提示桩插件**（重建 `plugins/redeem_code/`）：匹配 `/兑换码`、`/兌換碼` → 撤回该消息（`delete_msg`，尽力而为）→ 无论撤回成败都回复「兑换码功能已迁移至网页个人主页「兑换码」页签」；不读写数据库。菜单既有指向行「兑换码请在网页个人主页「兑换码」页签使用」保留不动。
- 版本 bump **1.61.0**（新功能 minor）。

## Capabilities

### Modified Capabilities
- `redeem-codes`：网页兑换入口的格式校验放宽（数字段）；「QQ 指令移除」要求修订为「QQ 指令迁移提示桩」（撤回＋提示）。兑换码定义维护方式不变（改代码重启 webapp）。

### New Capabilities
- 无（称号定义走 `kb/GAMEPLAY.md` 文档同步，无独立称号规范）。

## Scope and Compatibility

- 实施分支：**master**（所有者明确指定，覆盖既往 dev 分支约定）。
- `redeem_code_usage` 表与网页 API/前端不动（前端输入框 placeholder 保持 `XXXX-XXXX-XXXX` 示例，仍合法）。
- 已有兑换码（TEST-CODE-TEST、ONLY-YEAR-ONCE）行为不变；历史记录与下架占位逻辑不变。
- 提示桩插件为普通插件（可按群/私聊开关），非系统插件，插件编号沿用原 45 号位（`kb/PLUGIN_CATALOG.md` 同步）。
- 不做：兑换码有效期/次数上限、批量生成、网页管理界面、撤回失败的重试。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_redeem_web.py` 扩展段 | `BEST-WISH-2027` 兑换成功且 503/504/505 三称号全部解锁；同一用户重复兑换被拒且称号不重复发放；含数字段、小写输入（`best-wish-2027`）归一后可用 |
| AC02 | 同脚本格式段 | 纯字母码格式校验不受影响；含数字但段长/分隔错误（如 `BEST-WISH-207`）仍报「格式不正确」且提示语含「大写字母或数字」；格式/未知码拒绝路径不写库 |
| AC03 | 新增 QQ 桩插件单测（进程内假 API） | 匹配 `/兑换码 ANY` 与 `/兌換碼` 触发：调用 `delete_msg(message_id)` 一次；发送消息含「已迁移至网页个人主页」与「兑换码」页签指引；`delete_msg` 返回 False 时仍发送提示；不产生任何数据库写入；非指令消息不匹配 |
| AC04 | `rg -n "神秘\|烤鱼" plugins/title/defs.py` 与 `python -c "import plugins.title.defs"` | 503/504/505 存在、rarity 全为 rare、简介与指令原文逐字一致、`unlock_type: redeem` |
| AC05 | `python -m pytest -q` 全量 + `openspec validate best-wish-2027-redeem --strict` | 全量回归绿；提案严格校验通过；归档与实现同一提交 |

## 维护者可持续性

兑换码维护方式与现状完全一致（改注册表＋重启 webapp）；提示桩插件无状态、无数据依赖，撤回失败不影响提示触达。测试沿用既有自动发现的 API 脚本模式与进程内插件单测模式，纳入统一回归。
