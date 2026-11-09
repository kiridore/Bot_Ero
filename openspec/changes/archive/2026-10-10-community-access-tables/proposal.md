# 社区准入数据层：注册账号、群登记、申请队列与黑名单表（M1 T1.1）

## Why

公开实例需要一个 QQ 号对陌生人群和私聊用户服务。在接入注册、群审核、拉黑与频控（M1 其余任务）之前，系统没有任何地方记录"谁已注册""哪个群已批准""哪个申请待处理""谁被拉黑"——后续每一项检查都依赖这些数据存在。本任务先交付纯数据层，不引入任何行为变化。

## What Changes

1. 新增四张表（DDL 进 `core/db/_base.py::init_schema`，`CREATE TABLE IF NOT EXISTS` 幂等）：
   - `user_accounts`：已注册账号（注册即插入，重复注册幂等；封禁不在本表设状态列，统一走黑名单表）
   - `group_registry`：已批准群（`status: active|removed`；机器人被移出群只改状态、保留审核历史）
   - `group_requests`：加群申请队列（存 OneBot 加群请求凭证 flag 与 sub_type；`status: pending|approved|rejected`）
   - `blacklist`：黑名单（`scope ∈ user|group`，目标唯一，可解除）
2. 新增 `core/db/community.py::CommunityManager`（读写集中），挂到 `DbManager.community`：
   注册/查注册、申请入队/待审列表/裁决、群激活/查激活/遍历激活群/标记移出、拉黑/解除/查拉黑。
3. 文档同步：`kb/DATABASE.md` 与 `specs/database.md` 表数与结构说明（以当前 48 张为基线，44→48 的旧写法作废）。

## Scope / Non-Goals

- **只做数据层**：不接事件入口检查（后续任务）、不做注册/审核/拉黑任何指令、不做 OneBot 加群 API 调用、不改菜单。
- 不做按版本分支：四种部署共用的普通表，私有部署启动同样建表，空表 = 无任何行为影响。
- 不迁移历史数据（新表无历史可迁）。

## Capabilities

### New Capabilities
- `community-access-registry`：注册账号、群登记、申请队列、黑名单四类记录的完整性与状态流转契约。

### Modified Capabilities
（无）

## Impact

- 代码：`core/db/_base.py`（+4 DDL）、新 `core/db/community.py`、`core/database_manager.py`（挂 manager）。
- 数据：启动时对既有 `data.db` 幂等建表；私有部署升级后仅多 4 张空表。
- 无用户可见行为变化：不 bump 版本，CHANGELOG 记 `[未发布]`。

## 验收标准

| 编号 | 验证命令 | 必须通过 |
|---|---|---|
| AC1 | `python -m pytest test/test_community_db.py -q` | CRUD、状态流转（pending→approved/rejected、active→removed）、幂等（重复注册、重复入队去重、重复激活、重复拉黑）、解除拉黑 |
| AC2 | `python -m pytest test/test_context_system_plugins.py test/test_database_schema.py -q`（或全量） | 既有测试零回归 |
| AC3 | `python -m pytest -q` | 全量通过 |
| AC4 | `rg -n "community_access|user_accounts" core/db/_base.py` + 文档核对 | `kb/DATABASE.md`、`specs/database.md` 表数更新为当前基线+4，四表结构、状态取值与索引说明齐全 |
| AC5 | `openspec validate community-access-tables --strict` | 校验通过，无归档告警 |

## 维护者可持续性影响

纯数据层、无新增人工流程、无监控盲区；表结构即后续注册/审核/拉黑的地基，避免 M1 后续任务各自建表漂移。
