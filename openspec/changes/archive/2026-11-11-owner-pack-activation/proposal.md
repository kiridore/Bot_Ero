# 群主自助开启功能包

## Why

新群的插件与功能包默认全关（严格白名单），过去只能由超级用户进群或用网页面板逐群配置。所有者希望群主自己解决：群主发 `/功能包 跑团` 就能开启跑团功能，不需要超管参与。原计划的 `/跑团 初始化`（一键关掉其余全部）因此取消，改为给现有 `/功能包` 开权限。

另发现「跑团」功能包漏了 1.69 新增的 `trpg_vitals`（`.hp/.san/.sc`），开启跑团包会缺这一项。

## What Changes

- `core/feature_packs.py`：把 `trpg_vitals` 补进「跑团」包。
- `plugins/group_manager`：
  - 新增 `owner_user()`（`sender.role == "owner"` 或超管）；
  - 新增群主受限路径 `_owner_request()`：只能 `/功能包 <白名单包>`（默认「基础包」「跑团」）、只能作用于**当前群**、只能「开启」；
  - 群主尝试 `/插件`、带其他群号、关闭、白名单外的包时，分别给出明确拒绝文案；群管理员（`role=admin`）不享有该权限。
- 菜单与 `kb/QUICK_REFERENCE.md` 同步权限说明。

## Capabilities

### New Capabilities

- `plugin-management`：功能包的管理权限与默认策略。

## Scope and Compatibility

- 新群默认仍然全关（不自动播种），群主主动开启一次即可。
- 超级用户权限不变：任意包/插件、任意群、开与关。
- 取消 `/跑团 初始化` 指令（未实现，无兼容风险）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 跑团包完整 | `python -m pytest test/test_group_manager_owner.py -q` | `FEATURE_PACKS["跑团"]` 含 `trpg_dice/trpg_session/trpg_char/trpg_vitals` |
| AC02 群主开包 | 同上 | 群主 `/功能包 跑团` 返回「已开启功能包「跑团」」且四个插件都写入本群；`/功能包 基础包` 同样生效 |
| AC03 群主边界 | 同上 | 白名单外的包被拒（「群主只能开启」）；`off` 被拒；带其他群号被拒；`/插件` 被拒 |
| AC04 权限分离 | 同上 | 群管理员（admin）被拒（「仅超级用户」）；超级用户不受限（可开关任意包） |
| AC05 文档与归档 | `python -m pytest -q`；`openspec validate plugin-management --strict` | 全量回归绿；菜单与 QUICK_REFERENCE 同步；`CHANGELOG [1.75.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
