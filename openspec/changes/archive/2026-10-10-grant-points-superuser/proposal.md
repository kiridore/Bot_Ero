# /发金币 权限统一为仅超级用户（M1 权限适配，所有者裁定 A）

## Why

所有者裁定（2026-10-10）：`/发金币` 在两种部署统一为仅超级用户可用，不保留"私有版群管理员可用"的旧差异。旧计划以部署标签分支的方案违反"仅配置差异"要求（两种部署共用同一实现），本次直接统一语义，消除最后一处按部署分侧的管理权限。

## What Changes

1. `plugins/grant_points_all/__init__.py`：match 门 `admin_user()` → `super_user()`（群管理员/群主不再匹配该指令；超级用户不变）。
2. 文档同步：`kb/QUICK_REFERENCE.md` 指令表、`kb/PLUGIN_CATALOG.md` 权限列。
3. bump `BOTERO_VERSION` → 1.52.1，CHANGELOG 记录。

## Scope / Non-Goals

- 只改 `/发金币` 一处；`/超级补卡`、`/刷新商店` 等仍用 admin_user()（群管理员可用），如需统一另行提案。
- 不加配置键、不留部署分支。

## Capabilities

### Modified Capabilities
- `plugin-event-processing`：新增“发金币仅超级用户可用”要求（能力内新要求，非改写既有要求）。

## Impact

- 私有部署行为变化（已获所有者授权）：群管理员发 `/发金币` 不再响应（静默不匹配）。
- 菜单无需改动：`/发金币` 本就在仅超级用户可见的管理员指令段。

## 验收标准

| 编号 | 验证命令 | 必须通过 |
|---|---|---|
| AC1 | `python -m pytest test/test_grant_points_permission.py -q` | 超级用户群内可用；群管理员/群主/普通成员均不匹配；私聊超级用户可用 |
| AC2 | `python -m pytest -q` | 全量回归通过 |
| AC3 | `rg -n "admin_user" plugins/grant_points_all/` 零命中；kb 两处权限描述已更新 | 代码与文档一致 |
| AC4 | `openspec validate grant-points-superuser --strict` | 校验通过；版本 1.52.1 与 CHANGELOG 一致 |

## 维护者可持续性影响

权限面收缩一档，减少一个"公开部署可能被群管理员滥用"的点；无新增维护流程。
