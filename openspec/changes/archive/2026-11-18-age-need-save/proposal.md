# 新卡未保存时，年龄调整面板要说明「先保存」

## Why

新建一张卡（`/trpg/coc`）时页面还没有卡号，点「应用年龄调整」只会弹一句 toast；用户不知道按钮为什么没用，也不知道该在流程的哪一步做这件事。

## What Changes

- 建卡页年龄调整面板：`CHAR_ID` 为空时显示醒目说明「先保存角色卡，再回到这里应用年龄调整：教育成长检定要由服务端掷骰，保存前拿不到卡号。」
- 同时把「应用年龄调整」「不再提示」两个按钮置灰，提示行固定为「先保存角色卡」，不再让用户点了再吃 toast。
- 测试：`test_trpg_coc_age_dom.js` 新增 4 项断言（说明存在、两个按钮禁用、提示语优先）。

## Capabilities

### Modified Capabilities

- `coc-character-sheet`：年龄调整面板在未保存状态下的可用性与说明。

## Scope and Compatibility

- 已保存的卡（`CHAR_ID` 存在）行为完全不变。
- 版本 2.1.4。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 说明可见 | `node test/test_trpg_coc_age_dom.js` | 未保存时面板含「先保存角色卡」与 `id="ageNeedSave"` |
| AC02 按钮禁用 | 同上 | `ageApply.disabled` 与 `ageSkip.disabled` 均为 true |
| AC03 提示语 | 同上 | 提示行文字为「先保存角色卡」 |
| AC04 已保存不受影响 | 同上（其余用例仍走 `CHAR_ID = 7`） | 32 项断言全过 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate coc-character-sheet --strict`；归档与实现同一 commit | `CHANGELOG [2.1.4]` 与 `BOTERO_VERSION` 一致 |
