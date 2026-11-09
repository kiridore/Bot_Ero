# 功能包双表与打卡-经济解耦（社区版 T0.7 · M0 收官）

> **暂停实施，待修订**：以下正文是历史草案，不是当前实施依据。所有者随后确认社区首版开放打卡基础与积分系统、经济扩展关闭；插件解耦改由 `plugin-event-dispatch` 提案实施。本草案仅保留讨论记录，未验收、未归档，禁止按旧的“关闭积分”和 `economy_active()` 方案实现。

## Why

M0 最后一项：社区版功能包结构与私有版分侧。所有者拍板（2026-10-06）：**社区版批次 1 仅"打卡基础"包；经济扩展不进社区表（后续批次再议）；社区版不含积分系统**——具体裁定 Q1:不提供补卡（remedy_checkin 不进社区表）、Q2:剔除 /排名（leaderboard 不进社区表）、Q3:打卡内经济钩子解耦（原选"钩子注册制"，落地形态修正见 Ruling）。私有表原样不动（红线 #122）。

## What Changes

- **`core/feature_packs.py` 双表**：按 `config.EDITION` 选表——私有 = 现 6 包逐项不变；社区批次 1 = 仅"打卡基础"`{checkin, checkin_recall, roll_back, week_checkin_display, all_checkin_display, week_list, personal_records}`（较私有同名包剔除 remedy_checkin/leaderboard），其余包以注释标注批次 2/3 待释。模块级 `FEATURE_PACKS` 名字保留（消费方 group_manager 零改动）
- **新增 `economy_active()` 判定**（同文件）：`"基础扩展包" in FEATURE_PACKS`——社区表无该包 → False；批次 2 若释出经济包自动翻 True（前向兼容）
- **打卡域经济触点门控**（`plugins/checkin`、`roll_back`、`checkin_recall`）：checkin 的三处（称号解锁评估 / 月全勤+幸运加分+`add_user_point` / `on_quest_trigger`）与两撤回侧的 `on_quest_rollback`，经 `if feature_packs.economy_active():` 包裹——社区形态打卡纯记录，积分/称号/周常代码零触达
- **`text_packs/community.yaml` 菜单同步**：剔除全部经济指令（/周常 /抽奖 /一键抽奖 /抽卡消费 /排名 /商店 /兑换码 /称号×7 /发金币 /刷新商店 /超级补卡 /超级单日补卡）与 /补卡 /单日补卡；保留 /打卡 /撤回打卡 /档案 /本周打卡图 /ALL /本周板油 + 系统管理员指令

> **Ruling（落地形态修正，请所有者过目）**：Q3 原选"钩子注册制"。读码后发现注册制在本库不可行且会破坏私有行为：(a) 插件自动导入机制使**所有插件模块在任何形态都被 import**——import 期注册钩子无法区分形态；(b) 按群启用状态门控钩子会改变私有现状（今天私有群即便关掉经济包，打卡照发积分）；(c) 三个触点交错在打卡消息组装的三个不同位置（称号消息在前、加分行在中、周常行在后），单点注册必重排私有消息顺序。故落地为**接缝文件内的能力判定函数**（`feature_packs.economy_active()`，属双形态接缝白名单 #2 处），业务代码调能力函数而非 `if EDITION` 字面量——精神与 T0.6 钩子一致（core 不感知形态差异，差异收敛于接缝文件）。

## Capabilities

- **New Capabilities**：`feature-packs`——功能包表按部署形态选择 + 打卡/经济解耦契约
- **Modified Capabilities**：无

## 验收标准

1. **私有零变化**：EDITION=private 时 `FEATURE_PACKS` 与现表 6 包**逐项一致**（含打卡基础内的 remedy_checkin/leaderboard）；全量 pytest 绿（红线 #122）
2. **社区表正确**：EDITION=community 时 `FEATURE_PACKS` == 仅"打卡基础"7 插件，不含 remedy_checkin/leaderboard/任何经济插件；`economy_active()` 返回 False
3. **经济解耦生效**：`economy_active()=False` 下 `checkin.handle()` 完整执行（打卡落库+时间线事件+回执消息）但 `add_user_point`/`evaluate_and_unlock_titles`/`on_quest_trigger` 零调用、quest_progress 无写入；`roll_back`/`checkin_recall` 的 `on_quest_rollback` 零调用（mock 断言）
4. **私有行为等价**：`economy_active()=True` 下三触点执行顺序与消息组装与现状一致（既有打卡/称号/周常用例回归）
5. **菜单同步**：community.yaml 不含 13 个被剔除指令字样（grep 断言），仍含 /打卡 /撤回打卡 /本周板油 等保留项
6. **文档同步**：development-plan T0.7 勾选 + §2 包结构表更新（含所有者三项裁定）；kb/PLUGIN_CATALOG.md + specs/plugin-catalog.md 功能包节；CHANGELOG `[未发布]`（Ruling：延续 T0.4 部署者面先例不 bump）
