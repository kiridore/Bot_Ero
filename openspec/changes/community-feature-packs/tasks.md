# Tasks · 功能包双表与打卡-经济解耦（T0.7）

> 验收标准见 proposal.md（6 条）；CHANGELOG `[未发布]` 不 bump（Ruling：T0.4 先例）。

- [ ] 1. `core/feature_packs.py` 双表重写 + `economy_active()`
- [ ] 2. `plugins/checkin/__init__.py` 三触点门控（原块缩进，内部逐字不动）
- [ ] 3. `plugins/roll_back` / `plugins/checkin_recall`：`on_quest_rollback` 门控
- [ ] 4. `text_packs/community.yaml` 菜单同步（剔 13 指令）
- [ ] 5. 新增 `test/test_feature_packs.py`（双表/两态判定/解耦-对照/撤回侧/菜单 grep）
- [ ] 6. 全量 `pytest` 绿（验收 1、4）
- [ ] 7. 文档：development-plan T0.7 勾选 + §2 包结构表、kb/PLUGIN_CATALOG.md + specs/plugin-catalog.md 功能包节、CHANGELOG
- [ ] 8. `openspec archive community-feature-packs`，同 commit：`feat(功能包): 社区版批次1功能包表与打卡经济解耦`
