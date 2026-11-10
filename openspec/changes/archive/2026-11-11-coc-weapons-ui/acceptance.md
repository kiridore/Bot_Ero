# COC 建卡武器表 — 验收记录

实施分支：`master`；版本 1.68.0；提案 `openspec/changes/2026-11-11-coc-weapons-ui/`。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 页面录入 | `node --check webapp/static/trpg_coc.js` 通过；`grep -c data-weapon webapp/static/trpg_coc.js` → 4（字段渲染、行容器、收集、删除各一处）；新建卡默认 `徒手格斗 25% 1D3+DB`。浏览器交互待 AC04 | 通过（代码层） |
| AC02 保存与回填 | `python test/scripts/check_trpg_coc_api.py` 全过：带「徒手格斗」「.32 自动手枪」两把的卡保存后返回两条且名称一致；更新为一把「短棍」后返回只有「短棍」 | 通过 |
| AC03 文档与归档 | `python -m pytest -q` → **616 passed**（4:32）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG` 顶部 `[1.68.0]` 与 `BOTERO_VERSION = "1.68.0"` 一致 | 通过 |
| AC04 真实环境冒烟 | 待所有者在部署机手工：添加两把武器保存、重新打开编辑可见并可删改 | 未执行（浏览器手测） |

## 实测与裁定

- 武器表是 1.66.0 的遗漏：后端字段、接口、xlsx 数据都在，只有页面没做，本次仅补前端与测试，无后端改动。
- 字段照 xlsx 武器区：武器、成功率、伤害、射程、次数、弹药、故障值、贯穿；名称留空的行不提交，避免空行堆积。
- 武器不参与任何校验（不与技能/预算联动），与 xlsx 一致。
