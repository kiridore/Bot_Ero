# 实施与验收任务

## 1. 计算与存储

- [x] 1.1 新建 `core/trpg/vitals.py`：`clamp` 与 `format_change`。对应 AC01。
- [x] 1.2 `core/trpg/coc.py`：`finalize` 增加 `current_hp/current_mp/current_san`，缺省取上限、越界截断（SAN 上限用 `99-克苏鲁神话`）。对应 AC06。
- [x] 1.3 `webapp/trpg/app.py`：`CharacterIn`/`CharOut` 补当前值字段；新建 COC 卡时按上限初始化。对应 AC06。
- [x] 1.4 `webapp/static/trpg_coc.js`：只读展示「当前 / 上限」。对应 AC06。

## 2. 指令插件

- [x] 2.1 新建 `plugins/trpg_vitals/`：`.hp` / `.san` / `.sc`，含骰子表达式、截断、状态提示、`满`、权限与规则门控。对应 AC01–AC05。
- [x] 2.2 `core/context.py`：`RECORDING_ALLOWED_PLUGINS` 加入 `trpg_vitals`，录制期间可用。对应 AC07。
- [x] 2.3 `plugins/menu/bot_menu_text.py`：补三条指令说明。对应 AC08。

## 3. 测试

- [x] 3.1 新建 `test/test_trpg_vitals.py`（18 例）：解析与截断、扣血/回满/需符号、骰子扣血、权限、规则门控、理智检定成功/失败/零损失/归零/累计。对应 AC01–AC05。
- [x] 3.2 `test/scripts/check_trpg_coc_api.py`：新增当前值缺省与显式保存断言。对应 AC06。

## 4. 文档与交付

- [x] 4.1 `kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 同步；`CHANGELOG [1.69.0]`；`BOTERO_VERSION` 1.69.0。对应 AC08。
- [x] 4.2 全量 `pytest` 绿；`openspec validate trpg-vitals --strict` 通过；写 `acceptance.md`；归档与实现同一 commit。AC07、AC09 由所有者验收。
