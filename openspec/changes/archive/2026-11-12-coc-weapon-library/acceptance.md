# 武器字段与武器库 — 验收记录

实施分支：`master`；版本 1.77.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 武器库数据 | `test_trpg_coc.py::test_weapon_library_passes_validation`：104 条全部通过 `weapon_problems` | 通过 |
| AC02 新字段校验 | `test_skill_required`、`test_skill_must_exist`、`test_type_length`：缺技能/技能不存在/类型超长均报错；斗殴·手枪·步枪-霰弹枪·弓·投掷·射击:手枪·格斗:斗殴 全部通过 | 通过 |
| AC03 伤害写法 | `test_damage_forms`/`test_damage_rejects_garbage` + 库内 104 条 `1D6+半DB`、`2D6/1D6/1D3`、`4D10/5码`、`眩晕`、`1D6+燃烧` 全部通过；`1D8+`、`+1D8`、`1D`、`一点八` 仍被拒 | 通过 |
| AC04 时代筛选 | `node test/test_trpg_coc_weapon_era.js`：10 项断言全过（1920s/现代/多标签/空标签/未填时代） | 通过 |
| AC05 接口 | `check_trpg_coc_api.py`：`weapon_library` ≥100 条、字段齐全、含 1920s 与现代；建卡回传 `type`/`skill`；非法与缺失使用技能均 400 | 通过 |
| AC06 DB 标注 | `test_damage_with_db_annotation`：`1D6+DB` → `1D6+DB（当前 DB=1D4）`、`1D3+半DB` → `（当前 DB=0）`、`2D8` 不加标注；`/跑团 角色 查看` 实测输出「短管霰弹枪｜步枪/霰弹枪｜1D6+DB（当前 DB=0）｜射程 10/20/50」 | 通过 |
| AC07 文档与归档 | 全量 `pytest` → **761 passed**（4:42）；`openspec validate coc-character-sheet --strict` valid；`CHANGELOG [1.77.0]` 与 `BOTERO_VERSION = "1.77.0"` 一致 | 通过 |

## 实测与裁定

- **数据来源**：`docs/COC7空白卡CY26.3.xlsx`「武器列表 战斗」工作表；脚本按 B~M 列逐行读取，类型列在合并单元格里只出现于分段首行，需向下填充；C 列不是武器技能的行（部位瞄准、毒剂表等）跳过，最终 104 条。注释列（N）在源表里行位错位（例如电锯的注释挂到了弓箭行），因此**不导入注释**。
- **校验口径变化**：伤害与次数放宽是为了让新卡真实写法能存；严格性通过「`1D8+`/`+1D8`/`1D`/`一点八`/`21D6` 仍被拒」的既有用例守住。
- **不使用武器技能基础值表**：本次不做 `.atk`，所以不需要为「射击:步枪」这类卡上不存在的技能编造基础值；只校验名字是否存在。
- **已知限制**：武器不参与掷骰；旧卡缺 `skill` 字段保存会被拒（当前环境无生产旧卡）；武器库注释未导入。
