# 实施与验收任务

## 1. API 层
- [x] 1.1 `webapp/tools/app.py::ToolItemOut` 增加 `tags: list[str] = []`；确认 `api_tools_list` 直接透传 `list_tools()` 的字典，无需其它字段构造改动。对应 AC01。

## 2. 测试
- [x] 2.1 `test/scripts/check_webapp_api_contract.py` 增加工具箱段：造一条带两个标签的链接 → `GET /api/tools` 断言 `items[].tags` → 独立 SQLite 连接断言与 `tools_link_tags` 一致 → 断言 OpenAPI `ToolItemOut.properties.tags` 为字符串数组。对应 AC01。
- [x] 2.2 新增 `test/test_tools_tags_render.js`：最小 DOM stub 下执行真实 `webapp/static/tools.js`，断言卡片标签行渲染与编辑表单预填。对应 AC03。
- [x] 2.3 全量 `python -m pytest -q`。对应 AC04。

## 3. 契约快照
- [x] 3.1 `cd app && python tool/export_openapi.py ..` 刷新 `app/openapi/openapi.json`；`git -C app diff` 确认只有 `ToolItemOut.tags` 8 行新增，无其它漂移。对应 AC02。

## 4. 文档与版本
- [x] 4.1 `core/config.py::BOTERO_VERSION` 2.0.0 → 2.0.1；`CHANGELOG.md` 顶部新增 `[2.0.1]` 节（修复工具箱列表响应缺 tags 导致的网页端标签不显示与编辑清空）。对应 AC06。
- [x] 4.2 `docs/webapp-api.md` 工具箱 `GET /api/tools` 行补 `tags` 说明。对应 AC06。

## 5. 验收与交付
- [x] 5.1 逐条执行 AC01–AC06 并把命令与结果记入 `acceptance.md`。对应 AC01–AC06。
- [x] 5.2 `openspec validate 2026-11-19-tools-tags-contract --strict` → `openspec archive 2026-11-19-tools-tags-contract --yes` → `openspec validate webapp-api-contract --strict`；归档与实现同一 commit（不提交 `app/` 子模块指针）。对应 AC05。
