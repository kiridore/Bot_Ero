# 跑团规则选择与 COC 7th 恢复、网页记录行式条目

## Why

所有者指令（2026-11-11）：网页跑团记录应当是一条一条的条目，包含团名、开始/结束时间、当前状态、参与人数、用户在该团中的身份（DM / 观察者 / 对应角色卡名）、所使用规则（DND5E / COC7th 等）。经澄清，所有者进一步要求**规则选择真的切换骰子行为**，因此需要恢复被删除的 COC 7th 检定实现。

现状：`meta.json` 没有规则字段；`plugins/trpg_dice/games.py` 只注册了 `dnd5e`，COC 的 `.ra`、奖惩骰与 `rolls.py` 在提交 `3dae681` 被删除；网页列表是卡片且只显示团名、时间、条数与参与者徽标，没有规则、人数口径与"我的身份"。

## What Changes

### 1. 规则注册表上移
- 新建 `core/trpg/game_systems.py`：`dnd5e` 与 `coc7th` 两项（id、展示名、检定指令、处理器名、大小写别名），提供 `normalize_rule()` 与 `rule_name()`。
- `plugins/trpg_dice/games.py` 改为从 core 重导出，避免两处注册表漂移。

### 2. `/跑团 规则`
- 无参：输出当前规则与可选项（`/跑团 规则 dnd5e`、`/跑团 规则 coc7th`）。
- 带参：仅 DM 或超级用户可切换；未识别值提示可选规则；录制中拒绝。
- 选择写入 `pending.json` 的 `rules` 字段（与准备名单同一文件、同一原子写）；未设置时默认 `dnd5e`。
- 开录时把当前规则写进 `meta.json.rules`；录制期间骰子读会话里的规则；重启续录时从 `meta.json.rules` 恢复。

### 3. COC 7th 恢复
- 恢复 `plugins/trpg_dice/rolls.py`：`coc_check`（极限/困难/常规成功、大失败）、`coc_bonus`、`coc_penalty`。
- 恢复三种检定入口：`.ra <技能值>`、`.r c<技能值>`、`.rh c<技能值>`（暗骰版结果只回私聊、录制中以暗骰入档）。
- 恢复奖惩骰：`.r b2` / `.r p1`，并接受 `.r 1d100b2` / `.r 1d100p1` 后缀写法；数量 1–10。
- 规则门控：DND 5E 下 `.ra`、`.r b/p` 拒绝并提示切换；COC 7th 下 `.rc` 拒绝并提示用 `.ra`。`.r` 通用掷骰两种规则下都可用。

### 4. 网页记录列表改为行式条目
- 每条一行：标题行（团名 + 状态徽标），细节行（`开始 — 结束`／`进行中` · `N 人` · `我的身份：…` · 规则名 · `N 条消息`）。
- 人数只统计普通玩家（排除 DM/观察者/机器人）；"我的身份"为 DM / 观察者 / `角色卡名（玩家）` / 玩家 / 未参与。
- 详情页顶部也显示规则名。
- 旧记录没有 `rules` 字段时显示「未知规则」。

### 5. 文档与版本
- 菜单文本、`kb/QUICK_REFERENCE.md`、`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md` 同步。
- `CHANGELOG.md` 新增 `[1.65.0]`，`BOTERO_VERSION` bump 至 1.65.0。

## Capabilities

### New Capabilities

- `trpg-rule-selection`：`/跑团 规则` 的查看与切换、权限、录制中拒绝、`pending.json.rules` 存储、开录写入与重启恢复。
- `trpg-dice-coc`：COC 7th 检定与奖惩骰的指令、判定口径，以及与 DND 5E 的规则门控。

### Modified Capabilities

- `trpg-session-recording`：`meta.json` 增加 `rules` 字段，续录时恢复规则。
- `trpg-record-web`：记录列表改为行式条目并展示规则、人数口径与"我的身份"；详情页显示规则。

## Scope and Compatibility

- **COC 检定只接受数值**（`.ra 70`）：角色卡是 DND 5E 的，没有 COC 技能数据，不做技能名映射。
- 未选择规则时默认 DND 5E；`pending.json` 旧文件缺 `rules` 字段按默认处理，不强制重写盘。
- 旧记录（无 `rules`）网页显示「未知规则」，不猜测。
- 社区版与私有版一致；无数据库变更；无新增第三方依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 规则注册表 | `python -m pytest test/test_trpg.py -q` | `normalize_rule` 接受 `dnd5e/DND5E/dnd`、`coc7th/COC7th/coc` 等变体，拒绝未知值；`rule_name` 返回展示名 |
| AC02 `/跑团 规则` 查看与切换 | `python -m pytest test/test_trpg_session.py -q` | 无参输出当前规则与可选项；DM 切换后 `pending.json.rules` 改变；非 DM 被拒；录制中被拒；未知规则被拒且不写入 |
| AC03 规则写入与恢复 | 同上专项 | 开录后 `meta.json.rules` 与当时选择一致、会话里也带同一规则；重启续录后会话规则来自 `meta.json` |
| AC04 COC 检定 | `python -m pytest test/test_trpg.py -q` | `.ra 70` 在 COC 规则下输出技能检定与成功等级；`.r c70`、`.rh c70` 等价；技能值 0/101 报错 |
| AC05 奖惩骰 | 同上专项 | `.r b2`、`.r 1d100b2` 输出奖励骰，`.r p1` 输出惩罚骰；数量 0 或超过 10 报错 |
| AC06 规则门控 | 同上专项 | DND 规则下 `.ra`、`.r b2` 被拒并提示切换；COC 规则下 `.rc` 被拒并提示用 `.ra` |
| AC07 网页行式条目 | `node test/test_trpg_records_list_dom.js` + `python test/scripts/check_trpg_records_api.py` | 列表渲染出每场一行的团名/状态/起止时间/玩家人数/我的身份/规则/消息条数；接口返回 `rules_name`、`player_count`、`my_role` |
| AC08 详情页规则 | `node test/test_trpg_records_dom.js` | 详情页头部包含规则名 |
| AC09 文档与归档 | `python -m pytest -q`；三个能力 `openspec validate --strict` | 全量回归绿；`CHANGELOG` 顶部 `[1.65.0]` 与 `BOTERO_VERSION` 一致；菜单与知识库已更新；归档与实现同一 commit |
| AC10 真实环境冒烟 | 部署机手工 | DM `/跑团 规则 coc7th` → 玩家 `.ra 70` 输出 COC 检定 → 开录 → 网页条目显示 COC 7th 与我的身份 |
