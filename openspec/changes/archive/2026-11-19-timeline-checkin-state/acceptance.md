# 验收记录

环境：master（HEAD b0245af，BOTERO_VERSION 2.1.5 → 2.2.0），Windows 开发机，2026-11-20。bot 进程与数据库零改动；社区版/私有版共用同一实现。

| AC | 验证命令 | 结果 | 证据 |
|---|---|---|---|
| AC01 | `python test/scripts/check_timeline_privacy.py` | ✅ | 新增段全 `ok`：`show 态：作者与非作者 checkin_state 一致`（`checkin:c-ev` → `show`）、`blur 态：作者与非作者 checkin_state 一致`（`checkin:a-group`，作者 A 与查看者 C 均 `blur`）、`text 态：作者与非作者 checkin_state 一致`（`checkin:b-priv`，作者 B 与查看者 C 均 `text`）、`hidden 态：作者看到 hidden，非作者仍不下发`（A 视角 `checkin_state: "hidden"`，C 的 feed 不含该事件）；脚本输出 `PASS`，退出码 0 |
| AC02 | 同上脚本第 10 段 | ✅ | `ok - 非打卡事件不含 checkin_state 键`（`source=forum` 的 `forum:state-check` 响应无该键）；`ok - OpenAPI EventOut 声明可空 checkin_state 且非必填`（`{'anyOf': [{'type': 'string'}, {'type': 'null'}], 'title': 'Checkin State'}`） |
| AC03 | 同上脚本既有断言段 | ✅ | `self_only=true`（A 私聊打卡、B 群聊 hidden 作者自见）、`images_hidden=true`（B 私聊 text 非作者）、`?blur=1` URL 改写（A 群聊 / B 群聊 blur）、三端点 hidden 过滤（C 的 feed/new/poll 均无隐藏事件，poll 差分 hidden→show 恰 +2）全部保持 `ok` |
| AC04 | `python test/scripts/check_webapp_api_contract.py` | ✅ | 既有契约段全 `ok`（含 `ToolItemOut.tags` 三断言、门控/登录/OpenAPI 检查），输出「全部通过」，退出码 0；`response_model_exclude_unset` 未改变其它响应字段 |
| AC05 | `python -m pytest -q` | ✅ | `1012 passed, 17655 warnings in 341.18s (0:05:41)`，0 failed（`check_timeline_privacy.py` 由 `test_webapp_api_suites.py` 子进程纳入） |
| AC06 | `cd app && python tool/export_openapi.py ..`；`git -C app diff -- openapi/openapi.json` | ✅ | 导出 `openapi 3.1.0, 118 条路径`；`1 file changed, 30 insertions(+), 1 deletion(-)`。`EventOut.properties.checkin_state` = `anyOf [string, null]`，不在 `required`；`EventOut.description` 同步模型 docstring。另含已裁决的 2.1.x 基线补齐：`CharOut.occupation_attr`、`CharOut.illegal`、`CharacterIn.occupation_attr`（各带 `default`，属 2.1.0/2.1.2 引入但快照未同步的既有字段）。无其它路径/schema 漂移。 |
| AC07 | `rg -n 'checkin_state' specs/timeline-protocol.md docs/webapp-api.md specs/web-gallery.md` | ✅ | `specs/timeline-protocol.md:113` 新增 `## Constraint: 打卡显示状态（checkin_state）`：取值、仅打卡事件、与查看者无关、与 `self_only`/`images_hidden`/`?blur=1` 的共存关系、**隐私状态对查看者公开**说明；`docs/webapp-api.md:52` 时间线行补字段；`specs/web-gallery.md:446` 时间线隐私约束补状态标记 bullet |
| AC08 | `rg -n 'BOTERO_VERSION = "2.2.0"' core/config.py`；`sed -n '1,20p' CHANGELOG.md` | ✅ | `core/config.py:17:BOTERO_VERSION = "2.2.0"`；`CHANGELOG.md:7:## [2.2.0]`，描述新增字段、作者/非作者一致、隐私设置对可查看者公开、既有信号不变 |
| AC09 | `openspec validate 2026-11-19-timeline-checkin-state --strict`；`openspec archive 2026-11-19-timeline-checkin-state --yes`；`openspec validate timeline-feed --strict` | ✅ | 归档前：`Change '2026-11-19-timeline-checkin-state' is valid`；归档：`Specs updated successfully`（`timeline-feed: +1 added`）；归档后：`Specification 'timeline-feed' is valid`（见下方归档记录） |

## 行为验证说明

- **两视角一致（同一事件）**：AC01 的对比不是断言各自期望值，而是同一事件在作者 feed 与非作者 feed 中的 `checkin_state` 相等；三态分别覆盖不同作者，避免「同一作者两类设置」混淆：
  - `show`：`checkin:c-ev`，作者 C 与查看者 A、B 均为 `"show"`；
  - `blur`：`checkin:a-group`，作者 A 与查看者 C 均为 `"blur"`（A 的旧布尔键已懒迁移为群聊 blur）；
  - `text`：`checkin:b-priv`，作者 B 与查看者 C 均为 `"text"`（C 侧同时 `images_hidden: true`，B 侧原图）；
  - `hidden`：`checkin:a-priv` 只有作者 A 能看到，值为 `"hidden"`；C 的 feed/new 不含该事件——hidden 的不可见性原样保留，「标记可见」不改变下发表。
- **条件键**：非打卡事件由 `response_model_exclude_unset=True` 省略未提供的 `checkin_state`，`description/target/data/next_cursor` 仍按原样输出（显式 set，含 `null`），因此「无键 ≠ null」的既有契约语义不变。
- **实现路径**：`_visibility_ctx` 在既有四态遍历里顺带产出 `states`（每作者每页仍只读一次用户设置）；`_serialize_rows` 在任何查看者分支之前写入 `checkin_state`，`viewer_id=None` 时同样可算出。
- **快照归属**：`app/openapi/openapi.json` 已刷新，但按分工不提交 `app/` 子模块指针；主仓库 commit 只含后端字段、测试、规范、文档与版本。

## 归档记录

- `openspec validate 2026-11-19-timeline-checkin-state --strict`：`Change '2026-11-19-timeline-checkin-state' is valid`。
- `openspec archive 2026-11-19-timeline-checkin-state --yes`：`Specs updated successfully`，新增能力规范 `openspec/specs/timeline-feed/spec.md`（Requirement: 打卡事件携带与查看者无关的 checkin_state，4 scenarios）。
- `openspec validate timeline-feed --strict`：`Specification 'timeline-feed' is valid`。
