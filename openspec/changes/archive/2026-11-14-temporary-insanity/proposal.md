# `.ti` 疯狂发作（临时性疯狂 · 即时症状）

## Why

规则书第八章（p139）规定：一次理智检定损失超过 5 点时，守秘人要求智力检定，通过则进入**临时性疯狂**；发作时的表现按 **p141 表Ⅶ「疯狂发作-即时症状」**掷 1D10（或由守秘人指定）决定，持续 1D10 轮；其中第 9/10 条再查表Ⅸ恐惧症状表、表Ⅹ狂躁症状表（D100）。目前这些只能靠 DM 翻书掷骰，团里没有对应指令。

## What Changes

- 新增 `.ti [@目标]`：COC 7th 专用，**人工手动触发**（不做「损失≥5 → 掷智力 → 自动发作」的自动链路）。
  - 骰 1D10 → 表Ⅶ 即时症状；若抽到 **9 恐惧 / 10 躁狂**，再骰 D100 从表Ⅸ/表Ⅹ 抽具体症状；
  - 额外骰症状持续轮数（1D10 轮）与临时性疯狂小时数（1D10 小时），后者标注「整段是否适用由守秘人裁定」；
  - 抽到 **5 人际依赖** 时，若角色卡「背景 · 重要之人」有内容，一并带出；
  - 抽到 9/10 时把具体恐惧症/狂躁症追加到角色卡「背景 · 恐惧症和狂躁症」（已有内容用「、」连接）。
- 权限：本人可为自己触发；`@他人` 需要本群 DM 或超级用户（与 `.hp`/`.sc` 一致）。
- 回执通过 `record_bot_message` 写进跑团记录（与 `.sc` 一致）。
- 新增数据模块 `core/trpg/madness.py`：表Ⅶ 10 条、表Ⅸ 100 条、表Ⅹ 100 条，全部取自规则书原文（去掉译注①②与页码），文件头注明来源与重新生成方式。
- 文档：菜单文案 `bot_menu_text.py`、`kb/DICE_GUIDE.md` 新增 `.ti` 一节。

## Capabilities

### ADDED Capabilities

- `trpg-madness`：COC 7th 疯狂发作（即时症状）的掷表、写卡与权限。

## Scope and Compatibility

- 不改 SAN，不记录「正在疯狂」状态，不做总结症状表（表Ⅷ）与之后的不定性疯狂——本提案只做即时症状。
- 表Ⅹ 第 34/95 条原文同名（都是「抓挠癖」），保留原文不做改名（拉丁名不同，写在回执里）。
- 无数据库变更；版本 1.99.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 数据完整 | `python -m pytest test/test_trpg_insanity.py -q -k Tables` | 表Ⅶ 10 条、表Ⅸ/Ⅹ 各 100 条、编号连续、名称/拉丁/描述齐全、无 ①② 残留 |
| AC02 掷表查表 | 同上 | `immediate_symptom(4)`=偏执、`phobia(1)`=洗澡恐惧症、`mania(100)`=喜兽癖；越界返回 None |
| AC03 基本回执 | `... -k "paranoia_output"` | 回执含「陷入疯狂发作」「D10=4 → 偏执」「症状持续 1D10 轮 → 7 轮」「1D10 小时 → 5 小时」「由守秘人裁定」 |
| AC04 人际依赖 | `... -k dependence` | 含「卡上的「重要之人」：爱丽丝，未婚妻」 |
| AC05 恐惧写卡 | `... -k phobia_written` | 回执含「牙科恐惧症（Dentophobia）」且卡上 `social_background.phobias` 为该名 |
| AC06 狂躁追加 | `... -k mania_appends` | 原值「幽闭恐惧症」→「幽闭恐惧症、喜兽癖」 |
| AC07 规则门控 | `... -k dnd_card_refused` | DND 卡提示「疯狂发作是 COC 7th 功能」 |
| AC08 权限 | `... -k "needs_dm or can_target"` | 玩家 @ 他人被拒；DM 用 `@` 可为他人触发 |
| AC09 指令匹配 | `... -k matches_command` | `.ti` 能通过 `match("message")` |
| AC10 写入记录 | `... -k recorded` | `record_bot_message` 被调用且内容含症状名 |
| AC11 全量回归 | `python -m pytest -q` | 全绿 |
| AC12 文档与归档 | `openspec validate trpg-madness --strict`；归档与实现同一 commit | 菜单与 `kb/DICE_GUIDE.md` 已加 `.ti`；`CHANGELOG [1.99.0]` 与 `BOTERO_VERSION` 一致 |
