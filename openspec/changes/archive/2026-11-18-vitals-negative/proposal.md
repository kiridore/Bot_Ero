# 数值表达式的负合计会反向加血（并修明细可读性）

## Why

`.hp/.san/.mp/.sc` 的骰子表达式复用 `roll_expression()`，它原样返回 `sum(values) + modifier`。合计为负时：

| 输入（d4=1） | 修前 | 问题 |
|---|---|---|
| `.san -1d4-2` | SAN 50 → **51** | 想扣血，结果回血 |
| `.san +1d4-3` | SAN 50 → **48** | 想回血，结果扣血 |
| `.hp -1d4-2` | 未满时会 +1 | 同上 |
| `.sc 0/1d4-2` | 「今日累计损失 **-1**」 | 累计被负值抵消，`累计 > 不定时疯狂线` 判断失效 |

另一个可读性问题：明细只写合值 `d4=4`，看不出 `d4+1` 里骰子滚了几点，容易被误读成「+1 没生效」。

## What Changes

- `roll_expression()`：返回的数值夹到 `max(total, 0)`；带修饰时明细写成 `d4+1=4（3+1）`，被夹时写成 `d4-2=-1→0（1-2）`；无修饰时保持原样 `d4=3` / `2d6=7`。
- `kb/DICE_GUIDE.md`：数值指令一节补充「一个骰子项 + 一个数字修饰」的写法、最小为 0、明细构成，以及 `.san -1d4+1` 的负号作用于整体。
- 测试：`roll_expression` 三例（修饰可见、夹 0、恰好为 0）+ 四条端到端（`.san` 负合计不回血、`.san` 正号负合计不扣血、`.sc` 损失不为负且累计为 0、`.sc` 修饰计入损失）。

## Capabilities

### Modified Capabilities

- `trpg-vitals`：数值表达式的取值下限与回执明细。

## Scope and Compatibility

- 只影响「合计 ≤ 0」的写法与带修饰的明细文本；`1d6`、`2d6`、纯数值的数值与文本都不变。
- `.sc` 的成功/失败判定、累计、阈值提示逻辑不变（累计现在不会为负）。
- 版本 2.1.6。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 修饰可见 | `python -m pytest test/test_trpg_vitals.py -q -k modifier` | `1d4+1` 掷 3 → `(4, "d4+1=4（3+1）")` |
| AC02 夹到 0 | 同上 `-k negative_total` | `1d4-2` 掷 1 → `(0, "d4-2=-1→0（1-2）")`；掷 2 → `(0, "d4-2=0（2-2）")` |
| AC03 不回血 | `... -k "negative_total_does_not_heal"` | `.san -1d4-2`（d4=1）SAN 50 → 50 |
| AC04 不误扣 | `... -k "positive_negative_total"` | `.san +1d4-3`（d4=1）SAN 50 → 50 |
| AC05 累计不为负 | `... -k "loss_never_negative"` | `.sc 0/1d4-2`（d4=1）SAN 50 → 50，今日累计 0 |
| AC06 修饰生效 | `... -k "check_modifier_applied"` | `.sc 1/1d4+1`（d4=3）SAN 50 → 46 |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate trpg-vitals --strict`；归档与实现同一 commit | `CHANGELOG [2.1.6]` 与 `BOTERO_VERSION` 一致 |
