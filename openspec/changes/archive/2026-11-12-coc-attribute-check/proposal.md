# COC 属性检定：`.ra <属性名>`

## Why

`.ra` 目前只认「数字」与「技能名」，属性检定必须先查卡再手敲数值（`.ra 60`）。而 `.r 力量` 走的是 DND 属性加值路径，对 COC 卡会把 `(60−10)//2 = 25` 当数值输出——玩家很容易把 25 当成检定目标，实际力量是 60。

## What Changes

- `core/trpg/coc.py` 新增 `attribute_value(data, name)`：认中文全称（力量/体质/体型/敏捷/外貌/智力/意志/教育）、英文缩写（STR/CON/SIZ/DEX/APP/INT/POW/EDU，大小写不敏感）、幸运与信用评级；返回（显示名，数值）。
- `plugins/trpg_dice::_handle_coc_check`：技能名取不到值时回落属性；回执用 `[力量=60]` 区别于 `[技能=65]`；属性检定不写成长标记。
- 技能成功率为 0 或属性为 0 时给出「无法检定（目标值需要 1 以上）」而不是「应在 1~199 之间」。
- `.r <属性名>` 在 COC 卡上直接拒绝并提示改用 `.ra <属性名>`（不再吐 DND 加值）。
- `kb/DICE_GUIDE.md` 补属性检定用法与 `.r` 的禁忌。

## Capabilities

### Modified Capabilities

- `trpg-dice-coc`：COC 百分骰检定的取值来源。

## Scope and Compatibility

- 纯新增取值方式，`.ra <数字>`、`.ra <技能名>`、`.r c<值>` 行为不变。
- 属性检定不打成长标记（规则如此），也不写角色卡。
- `闪避` 已经是技能（基础值 = 敏捷÷2），继续走技能路径，不重复。
- 无数据库变更、无新增依赖；版本 1.84.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 属性表 | `python -m pytest test/test_trpg_coc.py -q -k AttributeValue` | 八项中文、英文缩写（含混合大小写）、幸运、信用评级取到正确数值；未知名字返 None |
| AC02 `.ra` 属性名 | `python -m pytest test/test_trpg.py -q -k ra_attribute` | `.ra 力量` → `[力量=60]`，不写成长标记、不落盘 |
| AC03 别名与缩写 | 同上 | `STR` / `str` / `Str` 都取到力量 |
| AC04 幸运与信用 | 同上 | `.ra 幸运` → `[幸运=50]`；`.ra 信用评级` → `[信用评级=40]` |
| AC05 零值提示 | 同上 | 目标值为 0 → 「无法检定（目标值需要 1 以上）」 |
| AC06 `.r` 拦住 | 同上 | COC 卡 `.r 力量` → 提示改用 `.ra`，输出里不再出现 DND 加值 |
| AC07 全量回归 | `python -m pytest -q` | 全绿 |
| AC08 文档与归档 | `openspec validate trpg-dice-coc --strict`；归档与实现同一 commit | `CHANGELOG [1.84.0]` 与 `BOTERO_VERSION` 一致；`kb/DICE_GUIDE.md` 已更新 |
