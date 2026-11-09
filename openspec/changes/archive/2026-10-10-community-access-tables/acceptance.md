# 验收记录（M1 T1.1，2026-10-10）

| 标准 | 执行 | 结果 |
|---|---|---|
| AC1 | `python -m pytest test/test_community_db.py -q` | 10 passed：注册幂等、群登记激活/移出/重批保留历史、申请去重与终态不可逆、黑名单范围隔离/解除、二次建表幂等、DbManager 挂载 |
| AC2 | 全量中含 schema/系统插件既有测试 | 零回归 |
| AC3 | `python -m pytest -q` | **602 passed** |
| AC4 | `kb/DATABASE.md` 表数 48→52、四表 DDL 与状态说明；`specs/database.md` 新增准入数据节 | 已核对 |
| AC5 | `openspec validate community-access-tables --strict` | 通过；无版本分支代码（`rg edition core/db/` 零命中） |

CHANGELOG 记 [未发布] 内部条目，不 bump（无用户可见变化）。
