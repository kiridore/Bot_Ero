# HP / SAN 变动与 COC 理智检定 — 验收记录

实施分支：`master`；版本 1.69.0；提案 `openspec/changes/2026-11-11-trpg-vitals/`。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 HP 变动 | `test/test_trpg_vitals.py`：`.hp -5` → `current_hp` 15 且回执含「HP 20 → 15」；`.hp -99` 截断 0 并含「HP 归零」；`.hp 满` 回满 30；`.hp 5` 被拒（「请带上正负号」） | 通过 |
| AC02 骰子表达式 | `.hp -1d6`（骰值 4）→ HP 20 → 16，回执含算式 | 通过 |
| AC03 权限 | 玩家 `@DM` 被拒且 DM 数值不变；DM `@玩家` 成功扣到 15 | 通过 |
| AC04 规则门控 | DND 卡 `.san` 被拒（「没有 SAN」）；本团 COC + DND 卡 `.hp` 被拒（「本团规则是 COC 7th」） | 通过 |
| AC05 理智检定 | 成功 SAN 65→64；失败 65→61 且含今日累计 4；成功且损失 0 保持 65；SAN 2 失败损失 10 → 0 且「永久疯狂」；连续两次失败累计 8；损失 6 触发「一次性损失 ≥5」 | 通过 |
| AC06 当前值存储 | `check_trpg_coc_api.py`：新建卡 `current_san=65/current_mp=13`；显式传 `current_san=40, current_hp=6` 原样返回 | 通过 |
| AC07 记录联动 | 实现走 `runtime_context.record_bot_message`，路径与 `trpg_dice` 相同（同一函数已由既有用例覆盖）；本次未单测录制场景 | 代码层通过，未单测 |
| AC08 文档与归档 | `python -m pytest -q` → **634 passed**（4:39）；`openspec validate trpg-vitals --strict` valid；菜单/QUICK_REFERENCE/PLUGIN_CATALOG/specs/plugin-catalog 已同步；`CHANGELOG [1.69.0]` 与 `BOTERO_VERSION = "1.69.0"` 一致 | 通过 |
| AC09 真实环境冒烟 | 待所有者：群里 `.hp -5`、`.san -1`、`.sc 1/1d6` 各一次，核对回执与网页只读值 | 未执行 |

## 实测与裁定

- **并发写卡**：角色卡存储的跨进程（bot/webapp）无锁，因此网页按决策只读；写入收敛在 bot 进程内的 `.hp/.san/.sc`。
- **SAN 上限**：`current_san` 的上限是 `99 - 克苏鲁神话`（7 版规则），缺省值取意志；某次实现曾误用「意志」当上限，被 `check_trpg_coc_api.py` 的 `current_san=40` 用例抓出并修正。
- **`CharacterIn` 漏字段**：COC 当前值最初只加在 `CharOut`，`model_dump()` 拿不到导致保存被重置为上限；同一条用例守住了这个回归。
- **疯狂判定**：按决策只提示（一次性 ≥5、今日累计 vs 1/5 线），不自动判定临时/不定时/永久疯狂。
- **未做**：`@全体` 批量改值、DND 临时 HP 与死亡豁免、专注。
