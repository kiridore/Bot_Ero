# Design — 社区准入数据层（M1 T1.1）

## 表结构（最终以 `core/db/_base.py::init_schema` 为准）

```sql
user_accounts(user_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL)

group_registry(group_id INTEGER PRIMARY KEY, name TEXT, invited_by INTEGER,
               approved_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active')
    -- status: active | removed

group_requests(group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, flag TEXT NOT NULL,
               sub_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
               created_at TEXT NOT NULL, PRIMARY KEY (group_id, user_id, created_at))
    -- status: pending | approved | rejected；flag 加唯一索引（同一凭证去重）

blacklist(scope TEXT NOT NULL, target_id INTEGER NOT NULL, reason TEXT,
          created_at TEXT NOT NULL, PRIMARY KEY (scope, target_id))
    -- scope: 'user' | 'group'
```

## 与旧开发计划的差异（已按"仅配置差异"核对）

| 旧计划 | 本设计 | 原因 |
|---|---|---|
| 表数 44→48 | 以当前 48 张为基线 +4（44→48 的历史写法作废；lottery/rewards/开关等表已先行落地） | 基线漂移，旧计数照抄必错 |
| T1.2 里"门控仅 EDITION==community" | 本任务零版本判断：四表全部署建表，空表即无行为 | 所有者要求仅配置差异（#135） |
| user_accounts 曾考虑 status 列 | 不设：封禁统一走 blacklist，一张表一个职责 | 状态语义不清是维护债 |

## CommunityManager API（读写集中，禁止其他模块裸 SQL 这些表）

```python
register_user(uid) -> bool              # 幂等，False=已存在
is_registered(uid) -> bool
upsert_request(gid, uid, flag, sub_type) -> bool   # 同 flag 去重，False=已存在
pending_requests() -> list[sqlite3.Row]
resolve_request(gid, uid, created_at, approve: bool) -> bool  # 仅 pending 可裁决
activate_group(gid, name=None, invited_by=None)    # 幂等；removed→active 保留 approved_at
is_group_active(gid) -> bool
iter_active_groups() -> list[int]
mark_group_removed(gid)                  # 不删行
ban(scope, target_id, reason=None)       # 幂等
unban(scope, target_id) -> bool
is_banned(scope, target_id) -> bool
```

- 方法默认自动 commit；参与外层事务时统一走既有 `commit=False` 约定（本任务无事务组合点，预留签名一致性）。
- 时间戳 `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`，与全库口径一致。

## 不变量

1. `user_accounts` / `blacklist` 行数 = 去重集合大小（主键保证）。
2. `group_requests` 终态行永不被 UPDATE 第二次（resolve 内先查 status）。
3. `group_registry.approved_at` 一经写入不变（重新激活保留首值）。
4. 无任何代码路径按部署标签读写这四张表。

## 测试设计（test/test_community_db.py）

真实临时数据库（init_schema）逐条断言 spec 场景；另加：DbManager.community 挂载可用、重复建表幂等（二次 init_schema 不报错不重复）。

## 风险

- `group_requests` 主键含 created_at：同一秒同群同人两次不同凭证申请理论上碰撞——flag 唯一索引兜底，测试覆盖。
- flag 是 OneBot 一次性凭证：队列长期留存 pending 无害（凭证过期后通过会失败，属后续群审核任务的处理范围，数据层只存不判断）。
