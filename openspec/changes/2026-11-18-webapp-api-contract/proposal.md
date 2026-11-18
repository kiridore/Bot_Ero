# Webapp API 契约固化：面向移动端 / PC 客户端

## Why

所有者原始指令（不得改写）：

- 「我准备将webapp解耦拆分出来，第一步是为web新增一套API接口」
- 「后续还会开发手机app，在这个条件下再检查一下哪些API是必须的」
- 「手机app计划使用flutter开发」
- 「我的设想是QQbot和Webapp各自独立，且都直接访问数据库。webapp提供API先考虑移动端和PC端App」
- 「第一版还是保证webapp和bot在同机同用户运行」

第一版移动端 / PC 端客户端（Flutter，一套 Dart 代码双端）将以 webapp 为唯一 API 后端，并计划用 `openapi.json` 生成类型化 Dart 客户端。当前 webapp 的 API 面无法直接锁定为契约：130 条路由中仅 14 条带 `response_model`（无 schema 的路由在生成客户端中退化为无类型，代码生成价值归零）；列表分页存在两种方言（`page/page_size` 与 `limit`，响应体仅 9 处 `items`、2 处 `total`，部分列表裸返回数组）；导航数据挂在非 API 命名的 `/entries.json`；live 流地址硬编码在前端 JS，客户端无从获取。契约若不先固化，客户端一旦发版，这些不一致全部变成破坏性变更。本提案只动 webapp，bot 侧零改动。

## What Changes

- **OpenAPI schema 补全**：全部 `/api/*` 路由声明响应模型（`response_model` 或等价显式声明），使 `GET /openapi.json` 成为完整契约；`/openapi.json` 维持登录门控（Flutter 代码生成时携带 Bearer 凭证获取）。
- **列表分页统一**为 `page`（≥1）+ `page_size` 查询参数，响应体 `{"items": [...], "total": int | null, "page": int, "page_size": int}`（精确计数成本过高时 `total` 允许 `null`，客户端不得依赖）。改造点：
  - `GET /api/forum/posts`、`GET /api/forum/posts/{id}/comments`（`limit` → `page/page_size`）
  - `GET /api/timeline`、`GET /api/timeline/new`（`limit` → `page/page_size`，窗口式翻页机制不变）
  - `GET /api/checkins`（画廊）、`GET /api/guestbook`、`GET /api/me/checkins`（参数已对，响应体补齐统一结构）
  - `GET /api/tools` 若存在 `limit` 参数（实现时审计确认）一并统一
  - 同步修改 web 前端消费方（forum.js、forum_detail.js、timeline.js、gallery.js、guestbook.js、profile.js、tools.js）与对应 node DOM 测试 stub
- **导航数据升格 API**：新增 `GET /api/nav`，返回与现 `/entries.json` 相同结构；web 前端两处引用（timeline.js、tools.js）迁移，删除 `/entries.json` 路由与 `webapp/app.py` 缓存中间件中的特判（改判 `/api/nav`）。
- **新增 live 流地址 API**：`GET /api/live/streams` 返回 `{"flv": str, "hls": str | null}`；`config.yaml` 新增 `live.hls_url`（缺省空 → `hls: null`，兼容旧配置文件）。`/api/live/status|heartbeat|viewers` 三条 API 不变；web 端 live.js 维持硬编码 FLV 现状不动。
- **错误响应契约声明**：错误体统一为 FastAPI 默认 `{"detail": ...}`（值可为字符串或校验错误数组）；现状 174 处 HTTPException 已基本一致，仅做审计清理，无大规模改动。
- **媒体引用契约声明**：API 返回媒体一律为相对路径或文件名，客户端以部署 base_url 拼接；六个媒体前缀（`/thumb/`、`/media/`、`/forum/media/`、`/archive/`、`/trpg/media/`、`/donate/media/`）路径不变，均接受 Bearer 头（纯声明，不改代码）。
- 版本 bump **2.0.0**（新功能 minor；1.99.0 → 2.0.0，对移动/PC 客户端 API 里程碑）。

## Capabilities

### New Capabilities
- `webapp-api-contract`：面向外部客户端（web 前端 / 移动端 / PC 端）的 webapp API 契约——OpenAPI 完整性、分页与错误约定、媒体引用规则、live 流地址。

### Modified Capabilities
- `web-navigation`：新增「导航数据经认证 API 提供」Requirement（`GET /api/nav` 取代 `/entries.json`）。

## Scope and Compatibility

- 基于 master（1.99.0）`feat/webapp-api-contract` 分支实施；bot 进程零改动（不改 `plugins/`、`core/` 业务逻辑，仅 `core/config.py` 增加 `live.hls_url` 读取一行）。
- **社区版与私有版两者一致**：改动全部在 webapp 层与配置读取，无 edition 分支；`live.hls_url` 两版按同一规则配置（缺省空即功能等同现状）。
- 旧配置兼容：`config.yaml` 缺 `live.hls_url` 键不报错（`.get()` 带默认值，与 `flv_url` 同模式）；无任何数据库 schema 变更，旧数据零迁移。
- 部署影响：维持 webapp 与 bot 同机同用户现状；SRS 输出 HLS 为部署侧前置条件（未配置 `hls_url` 时 API 返回 `null`，不阻塞其余功能）。
- **不做**：不加 `/api/v1` 版本前缀（契约版本走 OpenAPI 文档与弃用策略）；不做 CORS（Flutter 原生客户端不受同源策略约束）；不做消息推送；不做媒体路径重构；不动认证体系（token 即登录 key）；不实现 Flutter 客户端本身（独立仓库另行开工）；`/api/timeline/poll` 轮询语义不变。
- 前端行为变化：受分页统一影响的页面翻页行为不变（参数与响应结构在 JS 层适配），无用户可见功能增删。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_webapp_api_contract.py`（schema 段） | 携登录凭证获取 `/openapi.json` 成功；全部 `/api/*` 路径的 2xx 响应均含非空 JSON schema（`response_model` 或显式声明），无「空 schema」路由 |
| AC02 | `python test/scripts/check_webapp_api_contract.py`（分页段） | 上述清单内每个列表端点：查询参数恰为 `page`/`page_size`（无 `limit` 残留）；空库返回 `{"items": [], "total": 0, "page": 1, "page_size": n}` 结构（`total` 允许 null 的端点豁免数值断言）；`page=0` 返回 422 且体含 `detail` |
| AC03 | `python test/scripts/check_webapp_api_contract.py`（nav 段）；`rg -n "entries\.json" webapp/` | 预置 entries.json 后 `GET /api/nav` 登录返回其原结构、未登录 401 `{"detail"}`；rg 无残留引用（timeline.js、tools.js、webapp/app.py、webapp/timeline/app.py 均已迁移） |
| AC04 | `python test/scripts/check_webapp_api_contract.py`（live 段） | 配置 `hls_url` 时 `GET /api/live/streams` 返回 `{"flv": <flv_url>, "hls": <hls_url>}`；未配置时 `hls` 为 `null` 且 `flv` 不受影响；`/api/live/status` 行为不变 |
| AC05 | `python -m pytest -q`（含更新后的 `test/*.js` DOM 用例，经 `test_dom_render_suites.py` 纳入） | 全量绿：受响应体变化影响的 forum/guestbook/timeline/gallery/profile/tools DOM 用例 stub 已同步并通过 |
| AC06 | `openspec validate 2026-11-18-webapp-api-contract --strict`；归档后 `openspec validate webapp-api-contract --strict`、`openspec validate web-navigation --strict` | 变更级校验通过；归档后两能力合并规范校验通过（存量 web-navigation Purpose 过短警告随本次扩写消除）；归档与实现同一 commit |

## 维护者可持续性

不新增服务、不新增表、不改 bot。分页统一后新端点照抄单一形态，`response_model` 同时充当 FastAPI 运行期校验与契约文档；契约检查脚本纳入 `test_webapp_api_suites.py` 自动发现回归，后续新增 API 若违反契约会在 CI 期暴露。`live.hls_url` 与 `flv_url` 同模式维护。
