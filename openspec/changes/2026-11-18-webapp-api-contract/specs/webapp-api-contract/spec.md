# webapp-api-contract Specification

## Purpose

webapp 对外（web 前端、移动端 App、PC 端 App）提供一致的 JSON API 契约：OpenAPI 文档完整可生成类型化客户端、列表分页与错误响应形态统一、媒体引用可由客户端解析、直播流地址可查询。契约演进默认只允许 additive 变更（加字段/加端点）；破坏性变更 MUST minor bump + CHANGELOG 显著标注 + 旧形态保留至少一个版本，不使用 URL 版本前缀。

## ADDED Requirements

### Requirement: OpenAPI 契约完整性
全部 `/api/*` JSON 路由 SHALL 在 `GET /openapi.json` 中声明非空响应 schema（`response_model` 或等价显式声明）；媒体与页面路由不受此要求约束。`/openapi.json` SHALL 处于全站登录门控之内，客户端以 Bearer 凭证获取。

#### Scenario: 生成类型化客户端
- **WHEN** 携带有效登录凭证获取 `/openapi.json` 并交给代码生成器
- **THEN** 每条 `/api/*` JSON 路由的 2xx 响应均有具名 schema，生成客户端无无类型接口

#### Scenario: 未登录获取契约
- **WHEN** 无凭证请求 `/openapi.json`
- **THEN** 按全站门控返回 401/302，不暴露契约文档

### Requirement: 列表分页统一
列表端点 SHALL 使用 `page`（≥1）与 `page_size` 查询参数，MUST NOT 使用 `limit` 命名；`page_size` 上限沿用各端点现值并逐端点在 OpenAPI 中声明；响应体 SHALL 为 `{"items": [...], "total": int | null, "page": int, "page_size": int}`。精确计数成本过高的端点 `total` 允许为 `null`，客户端 MUST NOT 依赖其存在。非法分页参数（`page=0` 等）MUST 返回 422 且错误体含 `detail`。

#### Scenario: 空结果首页
- **WHEN** 登录用户以 `page=1` 请求任一列表端点且无数据
- **THEN** 返回 `{"items": [], "total": 0, "page": 1, "page_size": n}`（`total` 豁免端点为 `null`）

#### Scenario: 非法页码
- **WHEN** 请求 `page=0`
- **THEN** 返回 422，响应体含 `detail` 字段

### Requirement: 统一认证与凭证传递
全部 `/api/*` 路由 SHALL 要求 HTTP Bearer 凭证，凭证值为图库密钥（bot 侧私聊 `/图库密钥` 指令按 QQ 号签发）。密钥为确定性签名：同一 QQ 号重发得到同一把钥匙，单用户吊销不支持，唯一吊销手段是全局盐轮换（换 `AUTH_SALT` 且不再保留旧盐）。`POST /api/auth/login` SHALL 接受图库密钥并返回 `user_id`、昵称、头像与 token（token 即图库密钥本身，无过期、无会话存储）；该端点与 `/api/timeline/events*`（机器事件令牌）MUST NOT 要求用户凭证。OpenAPI 文档 SHALL 声明全局 HTTP Bearer security scheme 并在豁免路径标注 `security: []`，使生成的客户端自动携带凭证。

#### Scenario: 无凭证访问任意 API
- **WHEN** 不带凭证请求任一非豁免 `/api/*` 端点
- **THEN** 返回 401，响应体含 `detail`

#### Scenario: 登录换取凭证
- **WHEN** 以 `/图库密钥` 签发的有效密钥调用 `POST /api/auth/login`
- **THEN** 返回 user_id 与 token，后续请求携带 Bearer token 可访问全部非豁免 API

#### Scenario: 生成客户端自动携带
- **WHEN** 依据 `/openapi.json` 生成客户端并配置 token
- **THEN** 每个非豁免请求自动附带 Bearer 头，无需逐接口手写

#### Scenario: 豁免路径机器认证
- **WHEN** bot 携带事件令牌上报 `/api/timeline/events`
- **THEN** 不需要用户凭证，事件令牌校验独立生效

#### Scenario: 密钥泄漏处置
- **WHEN** 某用户密钥泄漏并私聊重发 `/图库密钥`
- **THEN** 得到同一把钥匙（确定性签名）；处置手段为全局盐轮换两步——换 `AUTH_SALT`（旧盐暂入 `AUTH_SALT_OLD` 兼容）→ 全体重领后清空 `AUTH_SALT_OLD`，旧钥至此全部失效

### Requirement: 错误响应统一
API 错误响应体 SHALL 为 `{"detail": ...}`（值为错误说明字符串或参数校验错误数组），沿用 FastAPI 默认形态，不引入全局异常处理器。HTTP 状态码属于契约；`detail` 文案不属于契约，客户端 MUST 仅展示不解析、逻辑分支只依赖状态码。

#### Scenario: 参数校验失败
- **WHEN** 请求携带类型错误的查询参数
- **THEN** 返回 422，`detail` 为校验错误数组

### Requirement: 媒体引用可解析
API 载荷中的媒体引用 SHALL 为相对路径或文件名，客户端以部署 base_url 拼接为绝对地址；媒体端点前缀（`/thumb/`、`/media/`、`/forum/media/`、`/archive/`、`/trpg/media/`、`/donate/media/`）SHALL 保持稳定并接受 Bearer 凭证。

#### Scenario: 客户端渲染图片
- **WHEN** 响应含相对媒体路径且客户端配置了 base_url
- **THEN** 拼接后的绝对地址携带凭证可获取媒体内容

### Requirement: 直播流地址查询
`GET /api/live/streams` SHALL 返回 `{"flv": str, "hls": str | null}`：`flv` 恒为配置的 FLV 地址；`hls` 为配置的 HLS 地址，未配置时为 `null`。既有 `/api/live/status|heartbeat|viewers` 行为 MUST NOT 改变。

#### Scenario: 已配置 HLS
- **WHEN** `config.yaml` 设置了 `live.hls_url` 并登录请求 `/api/live/streams`
- **THEN** 返回 flv 与 hls 两个地址

#### Scenario: 未配置 HLS
- **WHEN** 配置缺 `live.hls_url`（旧配置文件）
- **THEN** 启动不报错，`hls` 为 `null`，`flv` 与其余 live API 不受影响
