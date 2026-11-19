# webapp-api-contract Specification

## Purpose

webapp 对外（web 前端、移动端 App、PC 端 App）提供一致的 JSON API 契约：OpenAPI 文档完整可生成类型化客户端、列表分页与错误响应形态统一、媒体引用可由客户端解析、直播流地址可查询。契约演进默认只允许 additive 变更（加字段/加端点）；破坏性变更 MUST minor bump + CHANGELOG 显著标注 + 旧形态保留至少一个版本，不使用 URL 版本前缀。

## ADDED Requirements

### Requirement: 工具箱列表响应含标签数组
`GET /api/tools` 的响应 SHALL 为 `{"items": [...]}`，其中每个 `items[]` 元素 SHALL 含 `tags` 字段（字符串数组，无标签时为空数组），内容 SHALL 与数据库 `tools_link_tags` 中该链接的标签一致；OpenAPI 的 `ToolItemOut` schema SHALL 声明该字段为字符串数组。该字段为 additive 契约，客户端据此渲染标签并预填编辑表单；标签写入语义（提交值清洗、`PUT` 整体替换）不受本要求影响。

#### Scenario: 列表返回已有标签
- **WHEN** 某链接在 `tools_link_tags` 中挂了两个标签，登录用户请求 `GET /api/tools`
- **THEN** 该链接的 `items[]` 元素包含 `tags: ["标签A", "标签B"]`（顺序与关联记录一致）

#### Scenario: 无标签链接
- **WHEN** 某链接没有任何标签关联
- **THEN** 该元素的 `tags` 为空数组 `[]`，不省略字段

#### Scenario: 生成客户端可见字段
- **WHEN** 以 `GET /openapi.json` 的 `ToolItemOut` schema 生成类型化客户端
- **THEN** 生成的模型包含 `tags`（字符串数组），编辑时可直接回传该值而不会清空已有标签
