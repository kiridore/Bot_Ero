# 修正准备中卡片：审核提示口径与整行可点

## Why

所有者报告两件事：非本群 DM 的账号也看到「你是本群 DM，可点开每张角色卡审核」，且卡片点不开。

复现后确认根因：

1. **`is_dm` 把超级用户也算成 DM**：`/api/trpg/parties` 里 `is_dm = (本群 DM) or 是超级用户`，而页面用 `is_dm` 决定提示文案。超级用户（本群 DM 是别人）看到的提示因此把自己当成 DM。
2. **只有小按钮可点**：成员行只有末尾的「查看角色卡」是链接，点名字或角色名不会有任何反应，看起来就是「点不开」。

## What Changes

- `/api/trpg/parties` 拆分口径：`is_dm` 只表示本群 DM；新增 `is_super` 与 `can_audit`（本群 DM 或超级用户，与角色卡审核接口判定一致）。
- 页面提示按身份区分：本群 DM →「你是本群 DM…」；超级用户 →「你是超级用户…」；其他登录用户 → 不显示审核提示。
- 成员行改为整行可点（`.trpg-party-member.is-link`），保留「查看角色卡」按钮作为视觉提示；未准备成员仍显示「等待准备」。

## Capabilities

### New Capabilities

- `trpg-party-roster`：网页准备名单的身份口径与交互。

## Scope and Compatibility

- 只改列表接口字段与渲染；角色卡审核权限判定不变（DM/超级用户可越过隐私门控，其他人按 `privacy.char_public`）。
- 新增字段向后兼容，页面在缺字段时按假值处理（旧数据不会误显示提示）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 身份口径 | `python test/scripts/check_trpg_party_api.py` | 本群 DM：`is_dm=true can_audit=true`；普通登录用户：两者皆假；超级用户非本群 DM：`is_dm=false is_super=true can_audit=true` |
| AC02 提示文案 | `node test/test_trpg_party_render.js` | DM 卡显示「你是本群 DM」；超级用户卡显示「你是超级用户」且不含「你是本群 DM」；其他人无审核提示 |
| AC03 整行可点 | 同上 | 有角色卡的成员行是 `<a class="trpg-party-member is-link">`，仍含「查看角色卡」；未准备成员为普通文本「等待准备」 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate trpg-party-roster --strict` | 全量回归绿；`CHANGELOG [1.79.2]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
