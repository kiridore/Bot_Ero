# DND 5E 升级向导

## Why

现有 DND 卡只在 1 级算过一次 HP，之后 `level` 由经验值自动推导——玩家把 XP 填进编辑页的瞬间等级就变了，HP 一点没加、属性值提升（ASI）也没人问。这既违反 5E 的升级流程，也让高等级角色的血量全部要手改。所有者按「引导式建卡工具」标准要求补上升级流程。

## What Changes

- **等级显式保存**：`level` 由卡片保存，经验值只决定「够不够升」；`finalize` 不再用 XP 反推等级。
- **网页升级向导** `/trpg/levelup/<编号>`：经验达标时在角色列表出现「升级到 Lv.N」入口，向导分三步——
  1. 生命值：取均值（骰面/2+1+体质加值）或掷生命骰（服务器掷，提交后出结果）；
  2. 属性值提升：3→4、7→8、11→12、15→16、18→19 级，单项 +2 或两项各 +1，含种族加值不超过 20；
  3. 本次获得的特性/法术（可选，追加到 `features`）。
- **升级接口** `POST /api/me/characters/{id}/levelup`：校验 XP 门槛、等级上限 20、ASI 规则后落盘，返回增长值与派生值。
- **升级历史** `level_history: [{level, hp_gain, hp_mode, asi}]`。
- **HP 与当前 HP 同步增长**（升级那部分视为立即恢复）。
- **QQ 端**：`/跑团 角色 查看` 增加「可升级」或「升级进度 X/Y」一行，不新增指令。

## Capabilities

### New Capabilities

- `dnd-level-up`：DND 5E 升级流程（可升级判定、HP 增长方式、ASI 分配与上限、历史记录、满级处理）。

### Modified Capabilities

- `dnd-character-builder`：等级由卡片显式保存，XP 不再反推等级；编辑页显示升级进度。

## Scope and Compatibility

- 经验值仍由玩家/DM 手工填写，向导不自动发经验。
- 不实现职业特性表、子职业、法术位与法术选择（无对应数据；由第 3 步的自由文本记录）。
- **不做旧卡等级迁移**：所有者确认生产环境没有旧卡，`level` 缺失时才按 XP 兜底推导。
- 升级不可撤销；满级（20）与经验不足均返回 400。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 |可执行验证 | 通过条件 |
|---|---|---|
| AC01 可升级判定 | `python -m pytest test/test_trpg_levelup.py -q` | XP 299/300 分别为不可升/可升；满级不可升；等级被截断在 1-20 |
| AC02 HP 增长 | 同上 | 战士体质 14 取均值 +8；掷骰 7 +9；掷骰 11 报错；低体质时不低于 1 |
| AC03 ASI 规则 | 同上 | 单项 +2 通过；两项各 +1 通过；总计 ≠2 报错；三项报错；人类基础 19 再 +1 报错（超 20）；未知属性报错 |
| AC04 升级落盘 | 同上 | 等级 +1、HP 与当前 HP 同时 +gain、`level_history` 追加、`features` 追加、经验不足与 20 级报错 |
| AC05 接口 | `python test/scripts/check_trpg_levelup_api.py` | 建卡返回 `can_level_up`；取均值升级后等级 2、HP 20；XP 不足 400；4 级缺 ASI 400、带 ASI 200 且力量 +1；超上限 400；满级 400；COC 卡 400 |
| AC06 等级语义 | `test/test_trpg_finalize.py` | XP 够 5 级但 `level=1` 时仍为 1 级、熟练加值 +2；`level=5` 时为 +3 |
| AC07 文档与归档 | `python -m pytest -q`；`openspec validate dnd-level-up --strict` | 全量回归绿；`CHANGELOG [1.71.0]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
| AC08 真实环境冒烟 | 部署机手工 | 打开 `/trpg/levelup/<编号>`：切换均值/掷骰、4 级时选 ASI 并看到超 20 提示、提交后等级与 HP 正确 |
