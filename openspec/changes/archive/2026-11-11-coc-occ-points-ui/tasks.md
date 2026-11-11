# 实施与验收任务

- [x] 1.1 `webapp/static/trpg_coc.js`：`occAllowedNames` / `occAllows` 纯函数；重算时禁用非本职行的职业列、清零越界值并提示。对应 AC01、AC02。
- [x] 1.2 `webapp/static/trpg.css`：`is-not-occ` 淡化与 `[data-occ]:disabled` 样式。对应 AC03。
- [x] 1.3 扩展 `test/test_trpg_coc_skill_name.js`（6 项允许集合断言）与 `test_trpg_coc.py` 源码守卫。对应 AC01、AC02。
- [x] 1.4 `CHANGELOG [1.73.2]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC04。
