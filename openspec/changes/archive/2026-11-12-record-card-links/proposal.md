# 记录页：参与者角色卡可点进详情

## Why

复盘时看到「参团角色卡」只有快照摘要（HP/SAN/技能数），想看完整卡（武器、装备、背景）得自己去 `/trpg` 里翻；聊天气泡的头像也什么都不能点。

## What Changes

- 记录详情页的「参团角色卡」条目：有 `char_id` 的参与者整条变成链接，指向 `/trpg/char/<user_id>/<char_id>`，并显示「查看角色卡 →」；有卡但本场没有快照的老记录也会列出（只有名字 + 链接）。
- 聊天气泡头像：有 `char_id` 时头像外层包成链接，点进同一详情页。
- 悬停概要：头像与角色卡条目都带 `title`，内容按规则取自开录快照（没有则用结束快照）——
  - COC：`角色名 · 职业 · N岁 · HP 当前/上限 · SAN 当前/上限 · MP 当前/上限`
  - DND：`角色名 种族 职业 Lv.N · HP 当前/上限 · AC`
  - 无快照：`角色名（本场没有角色卡快照）`
- 机器人等没有 `char_id` 的参与者不出链接。

## Capabilities

### Modified Capabilities

- `trpg-record-web`：参与者角色的详情入口与悬停概要。

## Scope and Compatibility

- 纯前端改动 + 复用现有 `/trpg/char/<user_id>/<char_id>` 页面与 `/api/characters/...` 接口；`meta.json`、`messages.jsonl`、接口返回都不变。
- 目标卡设置了「不公开角色卡」时，点进去会看到既有的「对方未公开角色卡」提示——记录页上的快照摘要仍照常显示。
- 无数据库变更、无新增依赖；版本 1.86.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 悬停概要 | `node test/test_trpg_records_dom.js` | COC 概要含职业与 `SAN 当前/上限`；DND 含 `Lv.N` 与 `AC`；无快照时提示「本场没有角色卡快照」 |
| AC02 地址拼装 | 同上 | `charUrl({user_id,char_id})` → `/trpg/char/<user_id>/<char_id>`；无 `char_id` 返回空串 |
| AC03 头像链接 | 同上 | 有角色卡的他人头像被 `<a class="trpg-card-link">` 包裹，`href` 与 `title` 正确 |
| AC04 角色卡条目 | 同上 | 参团角色卡列表条目本身是 `<a>`、带「查看角色卡 →」与悬停概要；无 `char_id` 不包链接 |
| AC05 全量回归 | `python -m pytest -q` | 全绿 |
| AC06 文档与归档 | `openspec validate trpg-record-web --strict`；归档与实现同一 commit | `CHANGELOG [1.86.0]` 与 `BOTERO_VERSION` 一致 |
