# 实施与验收任务

- [x] 1.1 `webapp/static/trpg_coc.js`：`ATTRS` 改为九项 3×3 顺序、`ATTR_NOTE_TITLE`/`ATTR_NOTES`/`describeAttr`。对应 AC01。
- [x] 1.2 `webapp/static/trpg_coc.js`：属性区左 3×3 输入（🎲 图标）+ 右 3×3 描述；重算时刷新描述；`rollAll` 覆盖幸运。对应 AC02、AC03。
- [x] 1.3 `webapp/static/trpg.css`：`.coc-attr-wrap` / `.coc-notes` / `.coc-dice` 与窄屏断点。对应 AC02。
- [x] 1.4 新建 `test/test_trpg_coc_attr_notes.js`（12 项断言）。对应 AC01。
- [x] 1.5 `CHANGELOG [1.77.1]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC04。
