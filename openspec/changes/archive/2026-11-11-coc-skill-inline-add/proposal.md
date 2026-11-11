# 添加技能改为页面内输入 + 下拉

## Why

「添加技能」目前用浏览器 `prompt()` 弹窗，弹窗里塞了一段类别说明（还因为转义写错把 `\n` 直接显示出来）；校验失败也只能用 `showToast` 在页面角落提示，弹窗已关掉，输入内容也丢。所有者要求改成页面内的输入框（带下拉候选）+「添加技能」按钮。

## What Changes

- 技能区标题下方新增一行：文本输入（`list="skillOptions"` 绑定官方技能名下拉）+「添加技能」按钮 + 就地提示文字。
- 输入支持官方技能名与 `类别:专攻` 写法；回车等同点击按钮。
- 校验失败（无法识别 / 已存在）在输入框右侧就地显示低饱和红提示，不再弹窗，输入内容保留。
- 添加成功后清空输入与提示并保持焦点，方便连续添加。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：技能录入的交互方式。

## Scope and Compatibility

- 只改前端交互，技能名校验规则（`normalizeSkillName`）与保存逻辑不变。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 无弹窗 | `python -m pytest test/test_trpg_coc.py -q -k inline_input` | 建卡页脚本中不存在 `prompt(`；存在 `id="skillName"`、`list="skillOptions"`、`addSkillFromInput` |
| AC02 交互 | 人工看 `/trpg/coc` | 输入「侦察」点添加即增行；输入「飞天」就地提示且不清空；重复添加提示「技能已存在」；回车可添加 |
| AC03 文档与归档 | `python -m pytest -q`；`openspec validate coc-character-sheet --strict` | 全量回归绿；`CHANGELOG [1.73.3]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
