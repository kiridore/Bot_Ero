# 设计

## 1. 缺陷机理与修复位置

FastAPI 在 `response_model` 下用 pydantic 模型对返回值做校验与序列化：模型未声明的键不会进入响应体（不是 500，是静默裁剪）。`GET /api/tools` 的链路是：

```
ToolsManager.list_tools() -> [{"tags": [...], ...}]
  -> api_tools_list() 补充 created_by_name/avatar 后 return {"items": items}
  -> response_model=ToolsListOut -> ToolItemOut 过滤 -> 响应体（无 tags）
```

`list_tools` 已用 `_link_tags_map()` 一次性聚合标签（一条 SQL，无 N+1），因此修复只需在 `ToolItemOut` 增加声明，查询、路由、数据层零改动：

```python
class ToolItemOut(BaseModel):
    ...
    click_count: int
    tags: list[str] = []
    created_by_name: str
    created_by_avatar: str
```

默认值 `[]` 只作为模型层的兜底（例如未来某条记录缺键时序列化为空数组），不改变 `list_tools` 始终返回 `tags` 键的现状；由于有默认值，该字段在 OpenAPI 中不进 `required`，对旧客户端仍是纯增量。

## 2. 为什么不用 `extra="allow"`

另一种「保留未知键」的写法是给 `ToolItemOut` 配 `model_config = ConfigDict(extra="allow")`。不采用：

- 契约价值：`extra="allow"` 让该模型在 OpenAPI 里没有 `additionalProperties` 的具体类型，生成的 Dart 客户端仍拿不到 `tags` 字段（或退化为无类型字典），本次要修的正是客户端类型与响应形态。
- 失败可见性：允许任意额外键会把「DB 返回了新字段但模型漏声明」这类错配继续藏起来；显式字段则让契约脚本/快照 diff 暴露每一次变更。
- 范围：`extra="allow"` 影响整个模型的所有字段，属于契约语义扩大；本次只需一个字段。

## 3. 契约快照刷新

`app/tool/export_openapi.py` 用 `BOTERO_CONFIG` 指向临时测试配置，导入 `webapp.app:app` 后取 `app.openapi()`，不启动服务、不访问数据库数据。刷新前先验证基线：在改动前用同一脚本导出并与已提交快照比较，结果**完全相等**（118 条路径），因此改后 diff 可归因。

执行：

```bash
cd app && python tool/export_openapi.py ..
git -C app diff -- openapi/openapi.json
```

预期且实测 diff 仅为 `ToolItemOut.properties` 中 `click_count` 与 `created_by_name` 之间新增：

```json
"tags": {"items": {"type": "string"}, "type": "array", "title": "Tags", "default": []}
```

（8 行新增，`required` 因默认值不变。）若出现其它 schema/路径漂移，说明本地环境或契约基线不一致，停止提交并报告。

快照文件位于 `app/` 子模块内；本提案只负责刷新文件内容，**不提交子模块指针**（`git add app` 由 Flutter 客户端另一半完成后统一处理）。

## 4. 测试策略

- **后端契约**（`test/scripts/check_webapp_api_contract.py`，既有自动发现回归）：用 `DbManager` 造一条链接与两个标签（直接写库，避免依赖 OneBot/时间线外部服务），真实调用 `GET /api/tools?q=...`，断言响应项 `tags` 等于写入值；再用独立 SQLite 连接查 `tools_link_tags JOIN tools_tags`，断言与响应完全一致；最后断言 `doc["components"]["schemas"]["ToolItemOut"]["properties"]["tags"]` 为字符串数组。
- **网页端行为**（新增 `test/test_tools_tags_render.js`，最小 DOM stub）：mock `GET /api/tools` 返回带 `tags` 的条目与已登录会话，执行真实 `webapp/static/tools.js`，断言卡片里出现 `.tools-tags-row` 且文本为 `工具,效率`；点击自己卡片的编辑按钮，断言 `#addTags` 预填 `工具, 效率`。该用例由 `test/test_dom_render_suites.py` 自动纳入 pytest。
- **全量回归**：`python -m pytest -q`。

不新增后端服务、不新增数据库表、不改前端源码；`webapp/static/tools.js` 的两处消费代码（271 行渲染、410 行预填）保持原样，由新 DOM 用例钉住。

## 5. 边界与失败路径

- 无标签的链接：`list_tools` 返回 `[]`，响应 `tags: []`，卡片不渲染标签行（现有 `if (item.tags && item.tags.length)` 分支），编辑表单预填空串——与「没有标签」语义一致。
- 标签顺序：`_link_tags_map` 按 `tag_id` 排序，响应顺序稳定；前端按该顺序渲染，不做二次排序。
- 旧客户端：新增字段被忽略，无破坏；`PUT` 语义不变，修复后网页端/Flutter 编辑时会带上已有标签，不再清空。
- 部署：无配置键、无迁移；bot 进程零改动。
