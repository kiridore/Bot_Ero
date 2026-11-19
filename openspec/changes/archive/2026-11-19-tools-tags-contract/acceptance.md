# 验收记录

环境：master（HEAD 6913560），Windows 开发机，2026-11-19。bot 进程与数据库零改动。

| AC | 验证命令 | 结果 | 证据 |
|---|---|---|---|
| AC01 | `python test/scripts/check_webapp_api_contract.py` | ✅ | 新增段三项全 `ok`：`工具箱列表项含 tags 数组`（响应 `tags: ["契约标签A","契约标签B"]`）、`tags 与 tools_link_tags 一致`、`OpenAPI ToolItemOut 声明 tags 数组`；脚本输出「全部通过」 |
| AC02 | `cd app && python tool/export_openapi.py ..`；`git -C app diff -- openapi/openapi.json` | ✅ | 导出 `openapi 3.1.0, 118 条路径`；diff 仅 `ToolItemOut.properties` 新增 `tags: {items: {type: string}, type: array, title: Tags, default: []}`，`1 file changed, 8 insertions(+)`，无其它路径/schema 漂移；`required` 因默认值不变 |
| AC03 | `node test/test_tools_tags_render.js` | ✅ | 四项全 `ok`：列表渲染出一条卡片、卡片标签行渲染 `item.tags`（文本 `工具,效率`）、自己提交的卡片有编辑按钮、编辑表单预填 `工具, 效率` |
| AC04 | `python -m pytest -q` | ✅ | `977 passed`，0 failed（含新增 node DOM 用例，`test_dom_render_suites.py` 自动发现） |
| AC05 | `openspec validate 2026-11-19-tools-tags-contract --strict`；归档；`openspec validate webapp-api-contract --strict` | ✅ | 归档前：`Change '2026-11-19-tools-tags-contract' is valid`；归档后能力规范 `--strict` 通过（见下方归档记录） |
| AC06 | `rg -n 'BOTERO_VERSION = "2.0.1"' core/config.py`；`CHANGELOG.md`；`docs/webapp-api.md` | ✅ | `core/config.py:17:BOTERO_VERSION = "2.0.1"`；CHANGELOG 顶部 `[2.0.1]` 节描述本次修复；`docs/webapp-api.md:119` 声明每项含 `tags`（tag 名数组） |

## 行为验证说明

- **真实调用**：AC01 通过 `TestClient` 走完整路由与 `response_model`，不是直接读 `list_tools()`；写入的标签来自 `DbManager.add_link_tags`，响应中的 `tags` 与独立 SQLite 连接查询 `tools_link_tags JOIN tools_tags` 的结果逐项相等。
- **网页端渲染/预填**：AC03 执行真实的 `webapp/static/tools.js`（未改动），mock 的 `GET /api/tools` 响应带 `tags`；卡片出现 `.tools-tags-row` 且标签名与响应一致；点击编辑按钮后 `#addTags` 预填 `工具, 效率`。此前该字段被响应模型裁掉时，同一用例的标签行不存在、预填为空串。
- **旧数据**：无迁移；无标签链接响应 `tags: []`，卡片不渲染标签行，与现状语义一致。

## 归档记录

- `openspec archive 2026-11-19-tools-tags-contract --yes`：`Specs updated successfully`，能力规范 `+1 added`（Requirement: 工具箱列表响应含标签数组）。
- `openspec validate webapp-api-contract --strict`：`Specification 'webapp-api-contract' is valid`。
- 快照 `app/openapi/openapi.json` 已刷新，但按分工不提交 `app/` 子模块指针；主仓库 commit 只含后端字段、测试、规范、文档与版本。
