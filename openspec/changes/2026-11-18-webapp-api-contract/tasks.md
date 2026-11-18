# 实施与验收任务

## 1. 配置层
- [ ] 1.1 `core/config.py` 新增 `LIVE_HLS_URL`（`_sec("live").get("hls_url")` 带空默认，与 154 行 `flv_url` 同模式）；`config.example.yaml` `live:` 节补 `hls_url` 注释示例。对应 AC04。

## 2. API 层（webapp）
- [ ] 2.1 逐模块补 `response_model`（约 76 条 `/api/*` JSON 路由；媒体/页面路由豁免），模型随模块存放，命名沿用 `XxxOut/XxxIn` 风格。对应 AC01。
- [ ] 2.2 分页统一：`/api/forum/posts`、`/api/forum/posts/{id}/comments`（limit→page/page_size）；`/api/timeline`、`/api/timeline/new`（limit→page_size + page，total=null）；`/api/checkins`、`/api/guestbook`、`/api/me/checkins` 响应体补齐 `{items,total,page,page_size}`；审计 `/api/tools` 若有 limit 一并统一。对应 AC02。
- [ ] 2.3 新增 `GET /api/nav`（读 `TIMELINE_DIR/entries.json` 原样返回，缺失 404）；删除 `/entries.json` 路由；`webapp/app.py::static_revalidate` 特判改 `/api/nav`。对应 AC03。
- [ ] 2.4 新增 `GET /api/live/streams`（`{"flv": LIVE_FLV_URL, "hls": LIVE_HLS_URL or None}`）；`/api/live/status|heartbeat|viewers` 与 live.js 不动。对应 AC04。
- [ ] 2.5 统一认证契约：`webapp/app.py` 自定义 `app.openapi()` 注入全局 `bearerAuth` scheme，豁免路径（`/api/auth/login`、`/api/timeline/events`）标注 `security: []`；中间件执行逻辑不变。对应 AC07。

## 3. 前端适配
- [ ] 3.1 forum.js、forum_detail.js、timeline.js、gallery.js、guestbook.js、profile.js、tools.js 取数适配统一分页形态（`.items` 解包、limit→page_size 拼参），渲染逻辑不动。对应 AC02/AC05。
- [ ] 3.2 timeline.js、tools.js 的 `/entries.json` 引用改 `/api/nav`。对应 AC03/AC05。

## 4. 测试
- [ ] 4.1 新增 `test/scripts/check_webapp_api_contract.py`（`_env.write_config` 临时 config + 子进程 webapp + `make_login_key`）：schema 段（AC01）、分页段（AC02）、nav 段（AC03）、live 段两次启动含/不含 hls_url（AC04）、认证段（AC07：全局 scheme 与豁免标注、任选端点无凭证 401/带凭证非 401、login 换 key）；由 `test_webapp_api_suites.py` 自动发现。
- [ ] 4.2 更新受影响 `test/*.js` DOM 用例 stub 为统一分页响应形态。对应 AC05。

## 5. 文档与交付
- [ ] 5.1 bump `BOTERO_VERSION` 2.0.0、CHANGELOG `[2.0.0]` 节、`specs/web-gallery.md` API 表（/api/nav、/api/live/streams、分页/错误约定）、`kb/QUICK_REFERENCE.md` API 行为节。对应 AC05。
- [ ] 5.2 扩写 `openspec/specs/web-navigation/spec.md` Purpose（消除存量 `--strict` 警告）；全量 `python -m pytest -q` 绿；`rg -n "entries\.json" webapp/` 零残留；归档前 `openspec validate 2026-11-18-webapp-api-contract --strict` 通过，归档后 `openspec validate webapp-api-contract --strict` 与 `openspec validate web-navigation --strict` 通过；AC 证据记 `acceptance.md` 后 `openspec archive`，与实现同一 commit。对应 AC05/AC06。
