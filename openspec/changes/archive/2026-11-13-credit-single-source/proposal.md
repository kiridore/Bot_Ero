# 信用评级单一来源：资产区

## Why

信用评级在卡上有两处：资产区的 `credit_rating`（受职业区间校验、决定现金/其他资产/生活水平）与技能表里的「信用评级」行（基础 0，可填兴趣点，职业点被拒）。两处不同步，`.ra 信用评级` 的取值还是分裂的：技能行 > 0 时用技能行，否则才回落到资产区。实测「资产区 45 + 技能行兴趣点 20」会让 `.ra` 判 20、资产按 45 算。

## What Changes

- `core/trpg/coc.py` 新增 `credit_value()` / `normalize_credit_rating()`：信用评级唯一来源是资产区。
- `finalize()` 强制技能表的 `信用评级` 行为镜像：`total = credit_rating`（钳 0–99），技能行上的成长/职业/兴趣点不参与计算。
- `validate()` 开头做一次归一化：技能行残留点数并入 `credit_rating`（仅当资产区还是 0，避免覆盖玩家填的值），随后把三列清零——旧卡保存即完成迁移。
- `.ra 信用评级`（含 `信用` 别名）标注为「信用评级」而不是「技能」，且不打成长标记。
- 建卡页 `trpg_coc.js`：技能表的信用评级行四列全部只读（`disabled`，提示「在资产区填写」），资产区改动即时同步到该行；保存时该行提交全 0。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：信用评级的存储与展示口径。

## Scope and Compatibility

- 资产区输入框仍是唯一编辑入口；职业区间校验不变。
- 旧卡不需要手工迁移：下次保存时自动把技能行点数并入资产区并清零。
- 无数据库变更；版本 1.93.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 展示同源 | `python -m pytest test/test_trpg_coc.py -q -k CreditSkillMirror` | 技能行带兴趣点 20、资产区 45 时，`finalize` 的信用评级 total 为 45 且 interest 为 0 |
| AC02 取值同源 | 同上 | `skill_value("信用评级")` / `skill_value("信用")` 都等于资产区值；无技能行时也如此 |
| AC03 迁移 | 同上 | 资产区 0 + 技能行兴趣点 40 → `validate` 通过且 `credit_rating` 变 40、技能行点数清零；资产区已有值时不覆盖 |
| AC04 上限 | 同上 | 资产区 140 → total 钳到 99 |
| AC05 骰子 | `python -m pytest test/test_trpg.py -q -k credit` | `.ra 信用评级` 输出 `[信用评级=40]`（资产区值，不是技能行的 20），且不打成长标记 |
| AC06 接口保存 | `python test/scripts/check_trpg_coc_api.py` | 创建后技能表镜像资产区；`PUT` 带技能行点数时并入或清零 |
| AC07 页面只读 | `python -m pytest test/test_trpg_coc.py -q -k CreditSkillUi` | 源码含 `isCreditSkill`、禁用标记、`collect` 写全 0、资产区 `input` 监听同步 |
| AC08 全量回归 | `python -m pytest -q` | 全绿 |
| AC09 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [1.93.0]` 与 `BOTERO_VERSION` 一致 |
