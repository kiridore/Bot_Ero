# bot 内置监控面板（web_panel）— 设计文档

- 日期：2026-09-02
- 状态：已与用户确认（v1.36.0 webapp 仪表盘迁移为 bot 进程内置面板；局域网访问、不暴露公网）
- 前序：`2026-09-02-admin-dashboard-design.md`（v1.36.0，webapp 形态——本设计是其迁移）；其中 bot 侧修复（D6）已独立交付并保留
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-09-02-web-panel.md`

## 背景与决策

v1.36.0 把管理仪表盘做进了 webapp（社区站）。用户裁定：**不应并入 webapp**，改为 **QQ 机器人进程启动时自带的 web 监控面板**——部署在局域网（bot 与 OneBot 同网段），无需公网暴露。

| # | 决策 |
|---|------|
| P1 | 新 `core/web_panel.py` 单文件：`ThreadingHTTPServer`（stdlib，每请求一线程，契合纯同步多线程模型）+ 守护线程，`main.py` 启动时拉起；页面 HTML/CSS/JS **全部内嵌字符串**（零静态文件/零新依赖） |
| P2 | 鉴权：复用图库密钥（`verify_login_key` + `int(uid) in SUPER_USER`）；Bearer 头；无/坏钥匙 401、非超管 403；页面壳无数据可免鉴权，页内登录框存 localStorage |
| P3 | 五端点语义照搬 v1.36.0：scopes（distinct ∪ {0, 默认群}）、plugins 列表、toggle（白名单表 INSERT/DELETE，系统插件 400）、config GET/PUT（safe_load+`_REQUIRED` 校验→`.bak` 一代→tmp+`os.replace`）；**插件清单改读 `plugin_registry`**（`plugin_key` + 真实 `description` + SYSTEM_PLUGINS 判定） |
| P4 | 配置：`config.yaml` 可选节 `panel: {host: "0.0.0.0", port: 8790}`（局域网全接口监听；仅本机可改 127.0.0.1）；启动失败（端口占用等）**仅告警不阻断 bot** |
| P5 | 移除 webapp 侧仪表盘（新 commit 前向删除，不重写已推历史）：`webapp/admin/`、`admin.html/js/css`、nav「管理」入口、webapp/app.py 接线、相关测试与文档计数（回 11 模块）；**保留** v1.36.0 的 bot 侧独立修复（禁用复活/DB_PATH/硬编码清扫/测试守卫） |
| P6 | 配置保存提示改为「重启 bot 进程生效」（面板属 bot；webapp 若共用配置项另说，提示文案带一句） |

## 非目标

- 不做公网暴露/HTTPS（局域网 + 密钥鉴权足够；要暴露时用户自行反代）
- 不做面板内重启 bot 按钮、运行时状态监控（uptime/内存）——仅两节：插件启停 + 配置编辑
- 不动 `group_plugin_config` 表结构与启停语义（v1.36.0 已交付的行为不变）

## ① 模块结构（`core/web_panel.py`）

- `make_server() -> ThreadingHTTPServer`（按 `config.PANEL_HOST/PANEL_PORT` 构造；测试可改绑 127.0.0.1:0 拿 ephemeral 端口）
- `start_panel()`：main.py 调用；daemon 线程 `serve_forever`，OSError 仅 logger.warning
- `PanelHandler(BaseHTTPRequestHandler)`：`GET /`（内嵌页面）、`GET /api/scopes`、`GET /api/plugins?group_id=`、`PUT /api/plugins`、`GET /api/config`、`PUT /api/config`；JSON 统一 `_json(status, obj)`；log 噪声抑制（override log_message）
- 业务函数与 v1.36.0 webapp/admin/app.py 同构（`_enabled_set/_scope_label/_validate_config` 等），插件清单换 registry 来源

## ② 页面（内嵌）

单页：登录框（密钥输入→localStorage）→ 两节（插件管理：范围下拉+开关列表+🔒 系统插件区；配置编辑：等宽 textarea+保存+重启提示+行内错误）。401 时清 localStorage 重弹登录框。样式内嵌 `<style>`（纸墨风格变量内联降级——无共享 CSS 可用，取中性简洁样式）。

## ③ 边界

- 并发：SQLite 行级（同 v1.36.0）；http.server 每请求一线程与 bot 线程模型同构
- registry 为空（异常态）：列表为空即可，不崩
- 端口冲突/绑定失败：告警继续跑 bot
- 面板进程内读 config 常量为启动时值（配置编辑改盘不热更——与既有语义一致）

## ④ 测试

- 新 `test/test_web_panel.py`（进程内）：`make_server()` 绑 127.0.0.1:0 + 线程 serve；urllib 断言——页面 200 含标题；五端点 401（无钥匙）/403（非超管）；插件列表（注入假 registry 类：key/description/system 判定）；toggle 启禁往返写 `group_plugin_config`（conftest 临时库）；config GET=磁盘、坏 YAML 400 不落盘、合法保存回写 + `.bak` 生成 + 回读一致
- 移除 `test/scripts/check_admin_dashboard.py`、`test/test_admin_render.js`（随 webapp 模块删除）
- 全量 `pytest` 全绿

## ⑤ 文档与版本（同 commit）

- CHANGELOG `[1.37.0]` minor（管理仪表盘自 webapp 迁出为 bot 内置监控面板；部署说明变更）+ `BOTERO_VERSION` bump
- `config.example.yaml` panel 节；`kb/OPERATIONS.md` 面板部署段（局域网访问 + `/图库密钥` 取钥）
- web-gallery/AGENTS/CLAUDE/README/KNOWLEDGE_BASE/deployment：模块计数回 11、移除 admin 条目（v1.36.0 CHANGELOG 节保留为历史记录）
