# COC 属性检定 — 验收记录

实施分支：`master`；版本 1.84.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 属性表 | `TestAttributeValue` 4 例：八项中文、英文缩写含 `Siz`/`int` 混合大小写、幸运/信用评级/「信用」别名、未知名字（飞天/运气/Strength）返 None | 通过 |
| AC02 `.ra` 属性名 | `test_ra_attribute_name`：`.ra 力量` → `[力量=60]`，无成长标记，`update_char` 调用 0 次 | 通过 |
| AC03 别名与缩写 | `test_ra_attribute_abbreviations`：`STR` / `str` / `Str` 都取到力量 | 通过 |
| AC04 幸运与信用 | `test_ra_luck_and_credit`：`[幸运=50]`、`[信用评级=40]` | 通过 |
| AC05 零值提示 | `test_ra_zero_attribute_reported`：信用评级 0 → 「无法检定」 | 通过 |
| AC06 `.r` 拦住 | `test_r_attribute_on_coc_card_points_to_ra`：输出含 `.ra`、不含 `=25=` | 通过 |
| AC07 全量回归 | `python -m pytest -q` → **903 passed**（5:10） | 通过 |
| AC08 文档与归档 | `openspec validate trpg-dice-coc --strict` valid；`kb/DICE_GUIDE.md` 已补属性检定；`CHANGELOG [1.84.0]` 与 `BOTERO_VERSION = "1.84.0"` 一致；同一 commit 归档 | 通过 |

## 实测回执

```
.ra 力量      → 老张的COC检定 D100=16 [力量=60] → 困难成功
.ra STR      → 老张的COC检定 D100=45 [力量=60] → 常规成功
.ra 幸运      → 老张的COC检定 D100=11 [幸运=50] → 困难成功
.ra 信用评级    → 老张的COC检定 D100=79 [信用评级=40] → 失败
.ra 侦察      → 老张的COC检定 D100=22 [技能=25] → 常规成功 · 已标记技能成长
.ra 飞天      → 角色卡里没有技能或属性「飞天」
.r 力量       → COC 的属性与技能请用 .ra <属性名/技能名> 做检定，例如 .ra 力量
```

## 实现中的裁定

- **技能优先于属性**：`信用评级` 在技能表里也有一行（基础值 0），直接用 `skill_value` 会拿到 0。改为「技能成功率 > 0 才算命中技能」，否则回落属性表。
- **属性不打成长标记**：`is_skill` 标志控制，测试断言 `update_char` 未被调用。
- **零值单独提示**：属性路径下 `value <= 0` 给出「无法检定（目标值需要 1 以上）」，比 `coc_check` 的「应在 1~199」更贴近原因。
- **`.r` 只在卡是 COC 时拦截**：DND 卡继续沿用加值替换；`.r 1d6 力量打击` 这类说明文字不受影响（只检查算式部分）。
- **未做**：属性检定的优势/劣势语法（仍用 `.r 1d100b2`）、把 `.ra 力量` 结果写进跑团记录之外的任何地方（记录走既有机器人消息通道）。
