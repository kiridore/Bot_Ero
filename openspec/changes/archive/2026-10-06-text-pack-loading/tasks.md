# Tasks · 文案包加载机制（T0.8）

> 验收标准见 proposal.md（6 条）；记 CHANGELOG `[未发布]` 不 bump（Ruling：部署者面先例）。

- [x] 1. `core/config.py`：TEXT_PACK 键（缺省空串）
- [x] 2. 新建 `core/text_pack.py`（加载器 + get_text）
- [x] 3. `plugins/menu/__init__.py`：handle 惰性取 `get_text("menu_text", BOT_MENU_TEXT)`
- [x] 4. 新建 `text_packs/community.yaml`（中性草稿，T2.4 定稿）
- [x] 5. `config.example.yaml` 补 text_pack 注释
- [x] 6. 新增 `test/test_text_pack.py`（六向单元 + 坏包降级 + community.yaml 静态断言）
- [x] 7. 文档同步：AGENTS.md 菜单文本条目、specs/conventions.md §双形态接缝、kb/QUICK_REFERENCE.md、development-plan T0.8 重写
- [x] 8. 全量 `pytest` 绿（验收 1）
- [x] 9. `openspec archive text-pack-loading`，同 commit：`feat(文案): 文案包加载机制与社区菜单草稿`
