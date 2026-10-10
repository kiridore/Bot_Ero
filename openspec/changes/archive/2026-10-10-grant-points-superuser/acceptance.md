# 验收记录（grant-points-superuser，2026-10-10，1.52.1）

| 标准 | 执行 | 结果 |
|---|---|---|
| AC1 | `python -m pytest test/test_grant_points_permission.py -q` | 4 passed：群管理员/群主/普通成员不匹配；超级用户群聊与私聊均匹配且照常全员发分 |
| AC2 | `python -m pytest -q` | **606 passed** |
| AC3 | `rg -n "admin_user" plugins/grant_points_all/` 零命中 | kb/QUICK_REFERENCE、kb/PLUGIN_CATALOG 权限描述已改为超级用户 |
| AC4 | `openspec validate grant-points-superuser --strict` | 通过；`BOTERO_VERSION=1.52.1` 与 CHANGELOG 一致 |
