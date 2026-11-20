# 实施与验收任务

## 1. 数据与序列化层（`webapp/timeline/app.py`）
- [x] 1.1 `_visibility_ctx` 在同一遍历中返回 `states: {event_id: state}`（仅 `source=checkin`，取值 `show|blur|text|hidden`），沿用 `actor_states` 每作者每页一次设置读取。对应 AC01。
- [x] 1.2 `_serialize_rows` 为每条 `source=checkin` 事件写入 `checkin_state`（来自 `vis["states"]`，与 `viewer_id` 无关）；非打卡事件不写该键。对应 AC01、AC02。
- [x] 1.3 `EventOut` 显式声明 `checkin_state: str | None = None`；`/api/timeline` 与 `/api/timeline/new` 增加 `response_model_exclude_unset=True`，保持非打卡事件无键。对应 AC02、AC06。
- [x] 1.4 确认既有 hidden 过滤、blur URL 改写、text 剥图 + `images_hidden`、`self_only` 逻辑零改动。对应 AC03。

## 2. 测试
- [x] 2.1 `test/scripts/check_timeline_privacy.py`：新增 show/blur/text 三态的作者×非作者 `checkin_state` 逐事件相等断言。对应 AC01。
- [x] 2.2 同脚本：hidden 态作者 `"hidden"` 且非作者 feed/new/poll 仍无该事件。对应 AC01、AC03。
- [x] 2.3 同脚本：造一条 `source=forum` 事件，断言响应无 `checkin_state` 键；断言 OpenAPI `EventOut` schema 声明可空 `checkin_state` 且不在 `required`。对应 AC02、AC06。
- [x] 2.4 同脚本既有断言（`self_only`、`images_hidden`、`blur=1`、分页、poll 差分）保持通过。对应 AC03。
- [x] 2.5 `python test/scripts/check_webapp_api_contract.py` 既有契约段通过（确认 `exclude_unset` 未破坏其它响应字段）。对应 AC04。
- [x] 2.6 全量 `python -m pytest -q`。对应 AC05。

## 3. 契约快照
- [x] 3.1 `cd app && python tool/export_openapi.py ..` 刷新 `app/openapi/openapi.json`；`git -C app diff` 核对：`EventOut.checkin_state` + 已确认的 2.1.x 基线补齐（`CharOut.illegal`、`CharOut.occupation_attr`、`CharacterIn.occupation_attr`），无其它异常漂移。对应 AC06。

## 4. 文档与版本
- [x] 4.1 `specs/timeline-protocol.md` 新增 `checkin_state` 约束小节：取值、仅打卡事件、与查看者无关、与 `self_only`/`images_hidden`/`blur=1` 的关系、隐私状态公开说明。对应 AC07。
- [x] 4.2 `docs/webapp-api.md` 时间线 `GET /api/timeline` 行补 `checkin_state` 说明。对应 AC07。
- [x] 4.3 `core/config.py::BOTERO_VERSION` 2.1.5 → 2.2.0；`CHANGELOG.md` 顶部新增 `[2.2.0]` 节。对应 AC08。

## 5. 验收与交付
- [x] 5.1 逐条执行 AC01–AC09 并把命令与结果记入 `acceptance.md`。对应 AC01–AC09。
- [x] 5.2 `openspec validate 2026-11-19-timeline-checkin-state --strict` → `openspec archive 2026-11-19-timeline-checkin-state --yes` → `openspec validate timeline-feed --strict`；归档与实现同一 commit（不提交 `app/` 子模块指针）。对应 AC09。
