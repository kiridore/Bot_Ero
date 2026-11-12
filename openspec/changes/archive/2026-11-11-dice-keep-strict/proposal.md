# 骰子支持取高/取低，并改为严格解析

## Why

写《骰子使用指南》时对照代码发现两个缺陷：

1. **不支持取高/取低**：`_tokenize` 没有 `k` 分支，`.r 4d6k3` 只会掷 `4d6`，`k3` 被丢弃——DND 车卡的标准做法（4d6 取高三）根本无法用，而且玩家不会察觉。
2. **静默截断**：解析遇到未知字符就 `break`，`.r 2d6+abc` 算出 2d6 且不报错，比报错更危险。

## What Changes

- `_tokenize` 增加 `k` / `kh` / `kl` token（可带数字，缺省 1），`_parse_dice_result` 对其求值：保留最高/最低 N 颗，其余丢弃，回执显示保留与丢弃的骰值。
- `k` 只能跟在骰子表达式后；保留数超范围报错；`k` 未跟骰子时报「意外的标记」。
- 解析改为严格：遇到未知字符抛 `ValueError` 并指出剩余片段，提示「说明文字请用空格与算式分开」。
- 更新 `kb/DICE_GUIDE.md`：新增取高/取低示例与「表达式规则与报错」一节，移除「已知限制」中的两条。

## Capabilities

### New Capabilities

- `trpg-dice`：跑团骰子表达式语法与错误处理。

## Scope and Compatibility

- 既有表达式行为不变（`2d6`、`4d6`、`1d20+3`、`3#d20`、`%`、优势/劣势）。
- **行为收紧**：以前 `.r 2d6+abc` 会被静默算成 `2d6`，现在会报错；说明文字必须用空格分隔（文档已注明）。
- COC 的 `b`/`p` 与 `.ra`/`.rc` 门控不变。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 取高 | `python -m pytest test/test_trpg_dice_keep.py -q` | `4d6k3` 与 `4d6kh3` 对同一组骰值得到相同结果并显示丢弃值；`4d6k3+2` 正确加算 |
| AC02 取低与边界 | 同上 | `4d6kl1` 保留最小值；`3d6k` 缺省保留 1 颗；`2d6k5` 报错 |
| AC03 严格解析 | 同上 | `parse("2d6+abc")` 抛 ValueError 且消息含 `abc`；`.r 4d6k3x` 回执含「无法解析」 |
| AC04 兼容 | `python -m pytest test/test_dice.py test/test_trpg.py -q` | 既有表达式用例全绿；`.r 1d20 偷袭` 仍把「偷袭」当原因显示 |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate trpg-dice --strict` | 全量回归绿；`kb/DICE_GUIDE.md` 已更新；`CHANGELOG [1.76.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
