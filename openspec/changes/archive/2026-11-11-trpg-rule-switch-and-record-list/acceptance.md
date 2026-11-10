# 规则切换、COC 恢复与行式记录 — 验收记录

实施分支：`master`；版本 1.65.0；提案 `openspec/changes/2026-11-11-trpg-rule-switch-and-record-list/`。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 规则注册表 | `python -m pytest test/test_trpg.py -q` → 38 passed；`normalize_rule` 对 `DND5E` / `coc7` / `coc` 等变体归一到规则 id，未知值返回 `None`；`rule_name` 返回「DND 5E」「COC 7th」 | 通过 |
| AC02 `/跑团 规则` | `test/test_trpg_session.py`（72 passed）：无参输出「当前规则：DND 5E」与 COC 选项；DM 切换后 `pending.json.rules == "coc7th"`；非 DM 回「只有 DM」；录制中回「录制中」；`gurps` 回「未知规则」且规则不变 | 通过 |
| AC03 规则写入与恢复 | `test_rule_written_into_meta_on_start`：`meta.rules == "coc7th"` 且会话 `rules` 一致；`TestResumeRule`：`meta.rules` 为 `coc7th` 的残留录制续录后会话规则为 `coc7th` | 通过 |
| AC04 COC 检定 | `test_check_grades`（10→极限、25→困难、55→常规、97→大失败）、`test_check_rejects_out_of_range`、`test_ra_under_coc_rule`、`test_r_c_syntax_under_coc_rule` | 通过 |
| AC05 奖惩骰 | `test_bonus_and_penalty_dice`：`.r b2` 与 `.r 1d100b2` 输出「奖励骰」、`.r p1` 输出「惩罚骰」；数量越界报错 | 通过 |
| AC06 规则门控 | `test_handle_ra_rejected_under_dnd_rule`、`test_bonus_dice_refused_under_dnd_rule`、`test_rc_refused_under_coc_rule` | 通过 |
| AC07 行式条目 | `node test/test_trpg_records_list_dom.js` → 12 项全过（两行渲染、团名、起止时间、进行中、状态徽标、人数、我的身份 DM/角色卡名、规则、条数、`mine=1` 查询）；`check_trpg_records_api.py` 断言 `rules_name` / `player_count` / `my_role` 全过 | 通过 |
| AC08 详情页规则 | `node test/test_trpg_records_dom.js` → 34 项全过（详情头部渲染规则字段） | 通过 |
| AC09 文档与归档 | `python -m pytest -q` → **579 passed**（4:18）；`openspec validate` 对 `trpg-rule-selection`、`trpg-dice-coc`、`trpg-session-recording`、`trpg-record-web` 均 valid；`CHANGELOG` 顶部 `[1.65.0]` 与 `BOTERO_VERSION = "1.65.0"` 一致；菜单、`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 已更新 | 通过 |
| AC10 真实环境冒烟 | 待所有者在部署机执行：DM `/跑团 规则 coc7th` → `.ra 70` → 开录 → 网页条目显示 COC 7th 与我的身份 | 未执行（需真实 QQ 环境） |

## 实测与裁定

- **COC 奖惩骰语法**：历史代码里 `b`/`p` 是**独立原子**（`.r b2`），作者此前误述为纯后缀。实现同时接受两种写法（正则 `^(?:(\d*)d100)?b(\d*)$`），覆盖历史习惯与后缀习惯，数量上限 10（历史无上限，本次加保护）。
- **规则读侧优先会话**：开录时 `pending.json` 会被清空，若骰子只读 `pending.json`，本场规则会立刻回落默认值。因此 `current_rule()` 在录制中优先读会话里的 `rules`；会话由开录写入、由续录从 `meta.json` 恢复。
- **旧用例改写**：`test_trpg.py` 里两条断言 `.ra` 不匹配历史的用例（COC 移除时留下的）改为「`.ra` 能匹配但被 DND 规则拒绝」，保留原意。
- **列表 DOM 用例新增**：此前只有详情页 DOM 用例；本次新增 `test_trpg_records_list_dom.js` 覆盖行式条目字段，防止字段回退。
- **未验证**：没有真实 QQ 环境跑过 COC 规则切换；`.ra` 的技能名映射按决策仅支持数值；网页未在浏览器里实际打开验证，仅 DOM stub 层。
