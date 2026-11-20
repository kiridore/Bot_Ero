# 时间线打卡事件新增与查看者无关的 checkin_state 字段（2.2.0）

## Why

所有者原始指令（不得改写）：

> 目标：给时间线打卡事件增加**与查看者无关**的显示状态字段 `checkin_state`（让作者与非作者都能在客户端看到隐私标记），刷新契约快照，交付主仓库 2.1.0。

> 所有者裁决（原话）：「新增标记，并且这个标记不论本人还是其他人都能看到标记」——已确认接受**将作者打卡隐私状态对查看者公开**这一语义变化；走方案 B（改后端补 viewer 无关字段）。

> 版本修正（实施前裁决）：任务书的 2.1.0 基于旧 HEAD（270e65a / BOTERO_VERSION 2.0.1）；实际 master 已到 b0245af / 2.1.5，2.1.0 已被 631d8d9 占用。经裁决本次 bump **2.2.0**，不降级、不重号。

现状事实（已核实）：

- `webapp/timeline/app.py::_visibility_ctx` 只返回 `hidden`/`blur`/`text` 三个事件 id 集合，按作者 `user_settings.checkin_display()` 的 private/group 态计算（类型由 `data.private` 决定）。
- 序列化处（`_serialize_rows`）只输出**查看者相关**的变换结果：隐藏事件对非作者过滤、作者自见时带 `self_only: true`；blur 态对非作者图片 URL 追加 `?blur=1`；text 态对非作者清空 `images` 并带 `images_hidden: true`。
- 客户端拿不到作者设置的**原值**：非作者视角只能从「图片被改写成 blur」或「图片被清空」间接反推，作者视角则看不到任何「我对他人隐藏/模糊了图片」的标记。`show` 与「无标记」也不可区分。
- `EventOut` 声明为 `extra="allow"`，`self_only`/`images_hidden` 靠透传，未在 OpenAPI schema 中出现。
- `hidden` 态事件对非作者**不下发**（`/api/timeline`、`/api/timeline/poll`、`/api/timeline/new` 同口径）；因此「所有人都能看到 hidden 标记」在语义上只能是：能收到该事件的查看者（实际只有作者）看到 `checkin_state: "hidden"`。

## What Changes

- `webapp/timeline/app.py::_visibility_ctx` 在一次遍历中额外产出 `states: {event_id: state}`（仅 `source=checkin` 事件；state ∈ `show|blur|text|hidden`）。沿用 `actor_states` 缓存，仍是**每作者每页只读一次**用户设置。
- `_serialize_rows` 为每条 `source=checkin` 事件写入 `checkin_state`，取值只来自 `states`，**与 `viewer_id` 无关**（不放在现有 `viewer_id is not None` 分支内）；非打卡事件不写该键。
- `EventOut` 增加**显式声明**的可选字段 `checkin_state: str | None = None`，使 OpenAPI schema 出现该字段（客户端生成物可类型化）；`/api/timeline` 与 `/api/timeline/new` 路由加 `response_model_exclude_unset=True`，让「非打卡事件无此键」保持条件键语义（无键 ≠ `null`），同时不影响既有总是输出的 `description/target/data/next_cursor`（它们由处理函数显式写入，视为 set）。
- 既有可见性行为**零改动**：hidden 仍对非作者过滤、blur 仍改写 URL、text 仍剥图并保留 `images_hidden`；`self_only` 逻辑不变。
- 测试：扩展 `test/scripts/check_timeline_privacy.py`——同一打卡事件在作者与非作者视角 `checkin_state` 完全一致（show/blur/text 三态逐态对比）；hidden 态作者看到 `"hidden"` 且非作者仍拿不到事件（回归保护）；非打卡事件不含该键；既有 `self_only`/`images_hidden`/`blur=1` 断言全部保持通过。
- 协议与接口文档：`specs/timeline-protocol.md` 新增 `checkin_state` 小节（取值、仅打卡事件、与查看者无关、与既有三信号的关系、**隐私状态对查看者公开**的语义变化）；`docs/webapp-api.md` 时间线 `GET /api/timeline` 行补字段说明。
- 刷新 `app/openapi/openapi.json` 契约快照。基线核对：当前 HEAD 导出的快照与已提交快照的差异为 2.1.x 引入但未同步的 `CharOut.illegal`、`CharOut.occupation_attr`、`CharacterIn.occupation_attr` 三处（经裁决属正常补齐，一并保留）；本次自身 diff 仅为 `EventOut.checkin_state`。
- 版本 bump **2.2.0**（新增 API 字段，minor）；`CHANGELOG.md` 顶部新增 `[2.2.0]` 节。
- 不提交 `app/` 子模块指针；不改 `app/lib/**`、`app/android/**`。

## Capabilities

### Added Capabilities

- `timeline-feed`：时间线信息流事件的响应载荷语义。本次新增 Requirement「打卡事件携带与查看者无关的 checkin_state」——`GET /api/timeline` 与 `GET /api/timeline/new` 返回的每条 `source=checkin` 事件 SHALL 带 `checkin_state`（`show|blur|text|hidden`，作者设置原值，与查看者无关）；非打卡事件 MUST NOT 带该键；既有可见性过滤与展示变换 MUST NOT 改变。

（`openspec/specs` 下无时间线相关能力，故新建 `timeline-feed`；`webapp-api-contract` 只管契约生成与分页/错误形态，不承载时间线事件语义，不改动它。）

## Scope and Compatibility

- **社区版与私有版两者一致**：改动全在 webapp 读侧序列化与契约/文档，无 edition 分支、无配置差异。
- **additive 契约变更**：只新增可选字段，既有字段、状态码、分页、过滤行为全部不变；旧客户端忽略新字段即可继续工作。不涉及破坏性变更。
- **部署与旧数据**：无数据库 schema 变更、无迁移、无回填；历史打卡事件无 `data.private` 按群聊类型取 `checkin_display_group`，与现有可见性口径一致。bot 进程零改动。
- **隐私语义变化（已裁决）**：该字段会把作者的打卡显示设置（`show/blur/text`，以及作者自见时的 `hidden`）暴露给所有**能查看该事件**的用户。这是所有者明确要求的标记可见性；不改变谁能看到哪条事件。
- **不做**：不改时间线前端（`webapp/static/timeline.js`）渲染；不改 Flutter Dart 代码；不改 `poll` 响应（不返回卡片）；不改用户设置写入面；不新增设置项；不把 `checkin_state` 写进数据库（每次读取时由作者当前设置计算）。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_timeline_privacy.py` | 新增断言全部 `ok`：四态各自取值正确；作者与非作者对同一可见事件（show/blur/text）拿到的 `checkin_state` 完全一致；hidden 事件作者看到 `"hidden"` 且非作者拿不到事件；脚本输出 `PASS` 且退出码 0 |
| AC02 | 同上脚本中非打卡事件段（造一条 `source=forum` 事件） | 该事件响应 dict 不含 `checkin_state` 键（`"checkin_state" not in ev`） |
| AC03 | 同上脚本既有断言段 | `self_only: true`（hidden 作者自见）、`images_hidden: true`（text 非作者）、`?blur=1` URL 改写（blur 非作者）、三端点 hidden 过滤与 poll 计数差分全部保持通过 |
| AC04 | `python test/scripts/check_webapp_api_contract.py` | 既有契约用例全绿（确认 `response_model_exclude_unset` 未破坏其它响应字段）；脚本退出码 0 |
| AC05 | `python -m pytest -q` | 全量通过（0 failed；`check_timeline_privacy.py` 由 `test_webapp_api_suites.py` 子进程纳入） |
| AC06 | `cd app && python tool/export_openapi.py .. && git -C app diff -- openapi/openapi.json` | `EventOut.properties.checkin_state` 为 `{"anyOf": [{"type": "string"}, {"type": "null"}], ...}` 且不在 `required`；diff 另含已确认的 2.1.x 基线补齐（`CharOut.illegal`、`CharOut.occupation_attr`、`CharacterIn.occupation_attr`），无其它异常漂移 |
| AC07 | `rg -n 'checkin_state' specs/timeline-protocol.md docs/webapp-api.md` | 协议文档含取值、仅打卡事件、与查看者无关、与 `self_only`/`images_hidden`/`blur=1` 关系、隐私公开说明；API 文档时间线行含 `checkin_state` |
| AC08 | `rg -n 'BOTERO_VERSION = "2.2.0"' core/config.py`；`sed -n '1,20p' CHANGELOG.md` | 版本号为 2.2.0；CHANGELOG 顶部 `[2.2.0]` 节描述本次新增字段与隐私语义 |
| AC09 | `openspec validate 2026-11-19-timeline-checkin-state --strict`；`openspec archive 2026-11-19-timeline-checkin-state --yes`；`openspec validate timeline-feed --strict` | 归档前变更级 `--strict` 通过；归档后能力规范 `--strict` 通过；归档与实现同一 commit |
