# 设计

## 1. 范围与不变量

- 只改 webapp 与 `core/config.py`（新增 `live.hls_url` 读取）；bot 进程、`plugins/`、数据库 schema、`server_data` 布局零改动。
- webapp 维持单进程（禁 `--workers`）、全站登录门控、`/api/timeline/events*` 事件令牌白名单现状。
- 不加 `/api/v1` 前缀、不做 CORS——Flutter 原生客户端用 `Authorization: Bearer` 头，与 web cookie 双模式并存（`login_guard` 现有逻辑已支持）。

## 2. OpenAPI 契约（AC01）

- 逐路由补 `response_model`：现有 14 条已有（profile 的 DayCheckinsOut/CheckinPageOut、trpg 的 CharOut、gallery 的 UserIdsOut/CheckinListOut），其余约 76 条按模块补 pydantic 模型。模型放各模块内或模块旁 `schemas.py`，命名 `XxxOut/XxxIn`，沿用现有风格。
- 媒体/缩略图/页面路由（`FileResponse`，非 JSON）不强行套模型——契约只约束 `/api/*` 前缀的 JSON 路由（AC01 断言范围即此）。
- `/openapi.json`、`/docs` 维持登录门控：无凭证 302/401。Flutter 侧采用**快照工作流**（Q3:A）：登录后 `curl -H "Authorization: Bearer <密钥>" <站点>/openapi.json > openapi.json` 导出，提交进 Flutter 仓库，契约变化在 Flutter PR diff 可见；快照导出属 Flutter 仓库工作流，不属本提案代码范围。
- 失败路径：`response_model` 会启用 FastAPI 运行期响应过滤——若响应字段与模型不符返回 500。补模型时逐端点核对现响应（契约检查脚本 AC01 顺带抓这类错配，因为它要求真实调用返回的结构断言）。

### 2.1 认证 scheme 与豁免标注（AC07）

- `webapp/app.py` 自定义 `app.openapi()`（FastAPI 标准模式）：生成后注入 `components.securitySchemes.bearerAuth = {type: http, scheme: bearer}` 与顶层 `security: [{bearerAuth: []}]`，缓存进 `app.openapi_schema`；豁免路径 `/api/auth/login`（POST）与 `/api/timeline/events`（POST/DELETE 系列）在 `paths` 中改标 `security: []`。
- 认证执行仍由 `login_guard` 中间件唯一承担（页面 302 / API 401、体 `{"detail": "未登录"}`），不迁移到 FastAPI 依赖——避免改动页面重定向语义；schema 声明只服务代码生成与契约可读性。
- token 语义（Q1:A）：`POST /api/auth/login` 入参图库密钥，返回 token 即同一密钥，无过期、无会话存储。密钥为确定性 HMAC（同 QQ 号重发 `/图库密钥` 得到同一把钥匙）：**单用户吊销不支持**，唯一吊销手段是全局轮换，两步——换 `AUTH_SALT`（旧盐暂入 `AUTH_SALT_OLD` 保持兼容，期间旧钥仍有效）→ 确认全体重领后清空 `AUTH_SALT_OLD`，旧钥至此失效。该限制记入规范与风险台账。
- 密钥签发链不动：`plugins/gallery_login_key`（私聊 `/图库密钥`）→ `make_login_key(uid)`。

## 3. 分页统一（AC02）

统一形态：

```
GET ...?page=1&page_size=20        # page ≥ 1（Query(1, ge=1)）；page_size 沿用各端点现有上限
200 {"items": [...], "total": <int|null>, "page": 1, "page_size": 20}
```

| 端点 | 参数改动 | 响应改动 | total |
|---|---|---|---|
| `GET /api/forum/posts` | `limit(20/50)` → `page/page_size` | 补 `{"items", "total", "page", "page_size"}` | 精确 COUNT |
| `GET /api/forum/posts/{id}/comments` | `limit(30/100)` → 同上 | 同上 | 精确 COUNT |
| `GET /api/timeline` | `limit` → `page_size`，新增 `page` | 补统一结构 | `null`（隐藏事件过滤 + 窗口翻页使精确计数无意义，契约标注可选） |
| `GET /api/timeline/new` | 同上 | 同上 | `null` |
| `GET /api/checkins`（画廊） | 无（已 `page/page_size`） | 補齐结构 | 精确 |
| `GET /api/guestbook` | 无 | 补齐结构 | 精确 |
| `GET /api/me/checkins` | 无 | 补齐结构（CheckinPageOut 已有，按统一形态核对/调整） | 精确 |
| `GET /api/tools` | 实现时审计：若为 `limit` 则统一 | 同步 | 精确 |

- timeline 窗口机制（`_FEED_FETCH_PAGES` 跨隐藏带补页）不动，仅参数改名与响应包裹。
- 边界：`page=0` / `page_size=0` → 422（Query 的 ge 约束，detail 为校验数组）；页码超出 → `items: []`，不报错。
- 前端消费方同步：forum.js、forum_detail.js、timeline.js、gallery.js、guestbook.js、profile.js、tools.js——仅取数适配（`.items`、去 `limit` 拼 `page_size`），渲染逻辑不动。

## 4. 导航数据 API（AC03）

- 新增 `GET /api/nav`：读取 `TIMELINE_DIR / "entries.json"` 并原样返回 JSON（结构不变，避免前端/Flutter 双端解析改动）。
- 文件缺失 → 404 `{"detail": "导航数据不存在"}`（与现状 FileResponse 404 语义一致）。
- 删除 `GET /entries.json` 路由；`webapp/app.py::static_revalidate` 的 `path == "/entries.json"` 特判改为 `path == "/api/nav"`（导航改名需重验证的同一理由）。
- 跨进程读写：entries.json 为手工维护的静态数据文件，webapp 只读、bot 不写；不存在半写问题（文件由人编辑、落盘后生效）。

## 5. live 流地址 API（AC04）

- `config.yaml`：

```yaml
live:
  flv_url: https://live.littlero.tech/live/livestream.flv
  hls_url: ""   # 可选；SRS 开 HLS 后填 m3u8 地址，Flutter 移动端用
```

- `core/config.py`：`LIVE_HLS_URL = str(_sec("live").get("hls_url") or "")`（154 行 flv 同模式，缺键不报错）。
- `GET /api/live/streams` → `{"flv": LIVE_FLV_URL, "hls": LIVE_HLS_URL or None}`。登录门控内。
- 部署前置：SRS 需启用 HLS 输出才有真实地址可填；未填时 `hls: null`，Flutter 端隐藏 HLS 播放入口或回落 FLV（桌面端 `media_kit` 可播 FLV）。
- 不动 live.js（web 播放器维持硬编码现状）；`/api/live/status|heartbeat|viewers` 不变。

## 6. 错误与媒体契约（纯声明 + 审计）

- 错误体 = FastAPI 默认 `{"detail": str | list}`；本提案不引入全局异常处理器。契约边界（Q5:A）：**HTTP 状态码属于契约，`detail` 文案不属于**——客户端仅展示不解析，逻辑分支只看状态码。审计点：新增契约检查脚本对 401/422 两个确定路径断言体形态；HTTPException 174 处已同构，不逐个改。
- 媒体：六个前缀不变；API 载荷内媒体引用保持现状（相对路径/文件名），契约文档写明「客户端以 base_url 拼接」。

## 7. 测试清单

- 新增 `test/scripts/check_webapp_api_contract.py`（`_env.write_config` 生成临时 config，子进程起 webapp，`make_login_key` 造凭证）：
  - schema 段（AC01）：Bearer 取 `/openapi.json`，断言全部 `/api/*` JSON 路由 2xx 响应有非空 schema；
  - 分页段（AC02）：对清单端点断言参数集（openapi 参数名恰含 page/page_size、无 limit）+ 空库响应结构 + `page=0` 422 含 detail；
  - nav 段（AC03）：预置 entries.json → `/api/nav` 结构回读一致；未登录 401；
  - live 段（AC04）：两次启动（含/不含 `hls_url`）断言两形态。
- 更新受影响 `test/*.js` stub（forum、guestbook、timeline、gallery、profile、tools 相关用例改为统一分页响应形态），`test_dom_render_suites.py` 自动纳入。
- `python -m pytest -q` 全量回归；`rg -n "entries\.json" webapp/` 零残留。

## 8. 版本与流程

- bump `BOTERO_VERSION` 1.99.0 → **2.0.0**；CHANGELOG 新增 `[2.0.0]` 节；`specs/web-gallery.md` API 表补 `/api/nav`、`/api/live/streams` 与分页/错误约定；`kb/QUICK_REFERENCE.md` API 行为节同步。
- 契约演进策略（Q2:A）：默认只允许 additive 变更（加字段/加端点）；破坏性变更必须 minor bump + CHANGELOG 显著标注 + 旧形态保留至少一个版本。
- 归档：AC 全绿 + 全量 pytest 绿 + 归档前 `openspec validate 2026-11-18-webapp-api-contract --strict` 通过 → `openspec archive`，与实现同一 commit；归档后两能力合并规范 `--strict` 校验通过。
