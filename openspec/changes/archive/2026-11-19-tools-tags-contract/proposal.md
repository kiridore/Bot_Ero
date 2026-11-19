# 工具箱列表响应补齐 tags 字段并刷新契约快照（2.0.1）

## Why

所有者原始指令（不得改写）：

> 目标：修复工具箱 API 丢弃 `tags` 字段的缺陷（网页端与我方 Flutter 客户端都受影响），并刷新 openapi 快照，交付主仓库 2.0.1。

缺陷事实（已复现确认）：

- `core/db/tools.py::list_tools` 返回的每条记录**包含** `"tags": [...]`（第 76/87 行，`_link_tags_map()` 一次查询聚合，无 N+1）。
- `webapp/tools/app.py::ToolItemOut` 未声明 `tags`；`GET /api/tools` 的 `response_model=ToolsListOut` 由 FastAPI 按模型过滤响应，**多余键被静默丢弃**，所以实际响应里没有 `tags`。
- 后果（网页端）：`webapp/static/tools.js` 第 271 行读 `item.tags` 决定是否渲染卡片标签行，永远为 `undefined` → 卡片从不显示标签；第 410 行编辑表单预填 `item.tags` 永远得到空串 → 用户只改标题/描述/URL 时，`PUT /api/tools/{id}` 会带着空 `tags` 提交，而 `ToolsManager.update_tool` 按提交值**整体替换**标签（先 `DELETE FROM tools_link_tags` 再写入）→ **标签静默丢失**。
- 后果（Flutter 客户端）：生成模型 `ToolItemOut` 不含 `tags`，列表拿不到已有标签，只能在卡片上不显示标签并在编辑表单提示「保存会整体替换标签，需按需重填」。

这是契约与实现的错配，不是数据写入语义问题；`tags` 的清洗、去重、整体替换规则都正确，缺陷只在列表响应声明漏字段。

## What Changes

- `webapp/tools/app.py::ToolItemOut` 增加 `tags: list[str] = []`（纯增量字段，默认空数组）。`list_tools` 已返回该键，路由无需其它改动。
- 契约回归 `test/scripts/check_webapp_api_contract.py` 增加工具箱段：真实调用 `GET /api/tools`，断言每条 `items[]` 含 `tags` 数组且与 `tools_link_tags` 表一致；并断言 OpenAPI `ToolItemOut.properties.tags` 为字符串数组。
- 新增 `test/test_tools_tags_render.js`（最小 DOM stub）：断言 `webapp/static/tools.js` 用响应中的 `tags` 渲染卡片标签行、编辑表单预填已有标签。
- 刷新 `app/openapi/openapi.json` 快照（`app/tool/export_openapi.py`，TestClient 离线导出）。快照 diff MUST 只有 `ToolItemOut` 新增 `tags` 一处；若出现无关漂移则停止并报告，不提交。
- 版本 bump **2.0.1**（修复 patch）；`CHANGELOG.md` 新增 `[2.0.1]` 节；`docs/webapp-api.md` 工具箱 `GET /api/tools` 说明补 `tags` 字段。`specs/web-gallery.md` 第 309 行已声明每项含 `tags`（本次修复使其成立），无需改写。

## Capabilities

### Modified Capabilities

- `webapp-api-contract`：新增 Requirement「工具箱列表响应含标签数组」——`GET /api/tools` 的每个 `items[]` 元素 SHALL 含 `tags`（字符串数组），并在 OpenAPI `ToolItemOut` schema 中声明；内容与 `tools_link_tags` 一致。

## Scope and Compatibility

- **只补字段**：不改 `tags` 写入语义（`_clean_tags` 清洗规则、`PUT` 整体替换、`add_link_tags` 幂等）、不改数据库 schema、不改 `list_tools` 查询、不改任何页面行为。`webapp/static/tools.js` 本就按 `item.tags` 编写，无需改动。
- **additive 契约变更**：旧客户端忽略新增字段即可继续工作；不 bump minor（未破坏任何既有字段/端点/状态码）。
- **社区版与私有版两者一致**：改动全在 webapp 与契约层，无 edition 分支、无配置差异。
- **部署与旧数据**：无迁移；旧数据库里的 `tools_tags`/`tools_link_tags` 原样生效。Flutter 侧仅刷新 `app/openapi/openapi.json` 快照，不改 `app/lib/**` Dart 代码、不改子模块指针（由客户端另一半完成后处理）。
- **不做**：不改标签的增删改语义；不加分页（`/api/tools` 维持全量返回）；不改 `GET /api/tools/tags`；不动 `app/` 内的 Dart 实现与 Flutter 测试。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_webapp_api_contract.py` | 「工具箱列表项含 tags 数组」「tags 与 tools_link_tags 一致」「OpenAPI ToolItemOut 声明 tags 数组」三项均 `ok`，脚本输出「全部通过」且退出码 0 |
| AC02 | `cd app && python tool/export_openapi.py .. && git -C app diff -- openapi/openapi.json` | 快照中 `ToolItemOut.properties.tags` 为 `{"type": "array", "items": {"type": "string"}}`；diff 仅该 schema 的 8 行新增（无其它路径/schema 漂移、无删除） |
| AC03 | `node test/test_tools_tags_render.js` | 「卡片标签行渲染 item.tags」与「编辑表单预填已有标签」均 `ok`，退出码 0 |
| AC04 | `python -m pytest -q` | 全量通过（0 failed；node DOM 用例经 `test_dom_render_suites.py` 自动纳入，新增 tools 用例在内） |
| AC05 | `openspec validate 2026-11-19-tools-tags-contract --strict`；`openspec archive 2026-11-19-tools-tags-contract --yes`；`openspec validate webapp-api-contract --strict` | 归档前变更级 `--strict` 通过；归档后能力规范 `--strict` 通过；归档与实现同一 commit |
| AC06 | `rg -n 'BOTERO_VERSION = "2.0.1"' core/config.py`；`sed -n '7,12p' CHANGELOG.md`；`rg -n 'tags' docs/webapp-api.md` | 版本号为 2.0.1；CHANGELOG 顶部 `[2.0.1]` 节描述本次修复；`docs/webapp-api.md` 工具箱 `GET /api/tools` 行含 `tags` 说明 |

## 维护者可持续性

不需要新表、新配置或新服务。`ToolItemOut` 与数据库 `list_tools` 的字段对应关系由契约脚本同时断言响应与 `tools_link_tags`，以后再漏声明字段会立刻被抓到；OpenAPI 快照随契约脚本同一流程刷新，Flutter 生成物与后端不再静默漂移。
