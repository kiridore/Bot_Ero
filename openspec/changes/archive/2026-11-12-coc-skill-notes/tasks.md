# 实施与验收任务

- [x] 1.1 从附表 B95:K212 生成 `core/trpg/skill_notes.py`（110 条）。对应 AC01。
- [x] 1.2 `core/trpg/coc.py::skill_note_index()` + 旧译名映射。对应 AC01。
- [x] 1.3 options 下发 `skill_notes`；新增 skill-notes 接口。对应 AC02。
- [x] 1.4 `trpg_coc.js`：`skillNote`/`skillNoteTitle` + ⓘ 图标；`char_view.js` 按需加载并显示。对应 AC03、AC04。
- [x] 1.5 测试：`TestSkillNotes`（4 例）、`test_trpg_coc_skill_notes_dom.js`（6 项）、API 2 条断言。对应 AC01–AC03。
- [x] 1.6 `CHANGELOG [1.80.1]`、`BOTERO_VERSION`、归档与实现同一 commit。对应 AC05。
