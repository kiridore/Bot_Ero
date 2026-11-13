# 可打勾范围 — 验收记录

实施分支：`master`；版本 1.84.1。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 不打勾 | `test_mark_refused`：`mark("信用评级")`/`mark("克苏鲁神话")` 返回 False，卡上无 `check`；`mark("侦察")` 仍为 True | 通过 |
| AC02 不结算 | `test_settle_skips_them`：旧勾不产生明细，结算后勾清空、`growth` 为 0 | 通过 |
| AC03 不发 SAN | `test_high_credit_does_not_grant_san`（信用评级 95 + 侦察 30 → `san_change == 0`）；`test_real_mastery_grants_san`（侦察 95 成长后仍给 2D6=7） | 通过 |
| AC04 指令层 | 插桩验证：`.ra 信用评级` 大成功后卡上 `check` 为 None；`.ra 侦察` 大成功仍写 `check: true` | 通过 |
| AC05 全量回归 | `python -m pytest -q` → **907 passed**（5:13） | 通过 |
| AC06 文档与归档 | `openspec validate coc-skill-growth --strict` valid；`kb/DICE_GUIDE.md` 已注明；`CHANGELOG [1.84.1]` 与 `BOTERO_VERSION = "1.84.1"` 一致；同一 commit 归档 | 通过 |

## 规则原文核对（守密人核心规则书 5.11）

- 「克苏鲁神话与信用评级永远不会获得技能成长标记，角色卡上也没有相应的方框。技能不能获得增长没有其他不利后果。」
- 「若玩家投出了高于当前技能值的结果，或者结果大于 95，则调查员该技能获得改善：骰 1D10 并且立即将结果加到当前技能值上。技能可通过此方式超过 100%。」
- 「90% 或更多的技能值：于幕间成长中，若一位调查员有技能达到了 90% 或更高，为他的当前理智点增加 2D6 点。」

实现的 `improves()`、`SKILL_CEILING=199`、2D6 加当前 SAN 均与原文一致；本轮只修「不可打勾的两项」。

## 留待确认的规则歧义

原文没有限定「90% 奖励每次幕间都给」还是「只在首次达到 90% 时给」。当前实现按字面**每次结算只要存在 90% 以上技能就给 2D6**，长期可能导致 SAN 无限增长。若要收紧，可改为「仅当本次成长使某技能首次达到 90% 时给」。
