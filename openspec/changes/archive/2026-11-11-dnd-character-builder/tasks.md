# 实施与验收任务

## 1. 规则与校验

- [x] 1.1 `core/trpg/rules.py`：CLASSES 增加每职业可选技能清单（吟游诗人 `any`）与 `ATTRIBUTE_MODES`。对应 AC03。
- [x] 1.2 `core/trpg/character.py`：新增 `validate()`（生成方式/范围/购点预算/种族职业/技能清单与数量/豁免数量）、`point_buy_spent()`、`suggest_hp()`。对应 AC01–AC04。

## 2. 接口与前端

- [x] 2.1 `webapp/trpg/app.py`：`CharacterIn` 增 `attributes_mode`；DND 分支保存前调用 `validate()`；`/api/trpg/rules` 增加生成方式表（CLASSES 自动带技能清单）。对应 AC05。
- [x] 2.2 `webapp/static/trpg.js`：四个生成方式按钮写入 `attributes_mode`、属性框范围随方式变化、显示「基础+种族=最终」、购点超支提示、技能表显示职业可选范围并按清单禁用、HP 一键计算。对应 AC05、AC07。

## 3. 测试

- [x] 3.1 新建 `test/test_trpg_dnd_builder.py`（17 例）：购点预算与范围、其他生成方式、技能与豁免限制、HP 计算。对应 AC01–AC04。
- [x] 3.2 新建 `test/scripts/check_trpg_dnd_builder.py`：规则接口字段、合法建卡（种族加值只加一次）、超支/超选/越界/范围四类 400。对应 AC05。

## 4. 文档与交付

- [x] 4.1 `CHANGELOG.md` 新增 `[1.67.0]`，`core/config.py::BOTERO_VERSION` bump 至 1.67.0；插件目录同步描述。对应 AC06。
- [x] 4.2 全量 `pytest` 绿；`openspec validate dnd-character-builder --strict` 通过；逐条 AC 写 `acceptance.md`；归档与实现同一 commit。AC07 由所有者手工验收。
