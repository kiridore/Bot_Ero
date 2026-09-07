# 管理仪表盘（/admin）— 设计文档

- 日期：2026-09-02
- 状态：已与用户确认（两轮：插件管理 + 配置编辑增量；A/B/C/D 四点确认）
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-09-02-admin-dashboard.md`

## 背景

插件启停目前只有 QQ 端 `/插件`（仅超管，按群/私聊桶）；config.yaml 只能 SSH 编辑。诉求：网页端管理仪表盘——查看并修改各群与私聊的插件开启状态 + 在线编辑配置文件。

## 现状事实（设计依据）

- `group_plugin_config (group_id, plugin_name)` 白名单表：**有行=启用**；SYSTEM_PLUGINS（`core/context.py`）恒启用；**私聊 = group_id 0 桶**（`is_plugin_enabled` 把 `None→0`）；每次事件实时查库 → web 写库**即时生效**
- 既有坑①：`main.py` 启动调 `migrate_group_plugin_config()` 无条件对默认群 `INSERT OR IGNORE` 全量播种 → 禁用状态**重启复活**
- 既有坑②：`core/context.py::is_plugin_enabled` 与 `plugins/group_manager` 硬编码 `sqlite3.connect("data.db")`，绕过 `config.DB_PATH`（统一配置体系外泄 + 测试隔离失效）
- webapp 进程不能 import plugins（注册表为空）→ 插件清单需文件系统枚举；`SYSTEM_PLUGINS` 在 `core.context` 可安全 import
- 配置在进程 import 时冻结（`core.config._load`），改文件需重启生效

## 已确认决策

| # | 决策 |
|---|------|
| D1 | 页面 `/admin` 两节：插件管理（范围选择器：私聊/各群 → 开关列表 + 🔒 系统插件锁定区）+ 配置编辑（等宽 textarea 原文 + 保存） |
| D2 | 插件 API：`GET /api/admin/plugins?group_id=N`、`PUT /api/admin/plugins`（toggle 写 `group_plugin_config`）；任意 int 群号 ≥0 与 QQ 端一致；系统插件/未知插件 400 |
| D3 | 配置 API：`GET /api/admin/config`（原文）、`PUT /api/admin/config`（safe_load 解析 + `_REQUIRED` 必填校验 → 备份 `config.yaml.bak` → tmp+`os.replace` 原子写）；**不自动重启**，页面固定提示需重启 bot 与 webapp |
| D4 | 范围清单 = `group_plugin_config` distinct 群号 ∪ 默认群（默认群标注）；私聊固定 group_id=0；插件清单 = `plugins/` 目录枚举（包目录 + 裸 .py，排除 `__*`） |
| D5 | 权限：全部 admin API 仅 `SUPER_USER`（`int(uid) in SUPER_USER`，来自 `core.config`），非超管 403——对齐 QQ 端 `/插件` 超管语义；导航「管理」入口常驻 `nav.js`，页内 403 文案提示，不做按角色隐藏导航 |
| D6 | 顺手修两坑：`migrate_group_plugin_config` 改为**仅表新建时**播种；`is_plugin_enabled` 与 group_manager 的连接串改 `str(config.DB_PATH)` |
| D7 | 不做（YAGNI）：功能包批量视图、插件描述映射、自动重启、按角色隐藏导航、新建群范围 |

## ① 页面 `/admin`（新静态 admin.html/js/css，样式照 profile 系）

- 分节一「插件管理」：范围下拉（`私聊`、`群 <gid>`（默认群标 `（默认）`））→ 插件行列表：key + 状态徽章 + toggle 按钮（写库即时切换）；系统插件独立锁定区（🔒 恒开不可点）；未选范围前显示引导文案
- 分节二「配置文件」：等宽 textarea（原始 YAML）+「保存」按钮 + 固定提示「保存后需重启 bot 与 webapp 进程生效」；保存结果/校验错误（缺键名/解析错误）行内提示
- 保存成功后重拉原文（确认服务端内容）

## ② API（新模块 `webapp/admin/app.py`，`webapp/app.py` include）

超管守卫：`_require_super(user_id)`（403「仅超级用户」）。

- `GET /api/admin/plugins?group_id=<int>` → `{"group_id": N, "label": "私聊"|"群 N", "is_default": bool, "plugins": [{"key","enabled","system":bool}]}`（清单=枚举 ∪；enabled 按表行；system 按 SYSTEM_PLUGINS）
- `GET /api/admin/plugins/scopes` → `{"scopes": [{"group_id","label","is_default"}]}`（distinct ∪ 默认群，私聊恒在列）
- `PUT /api/admin/plugins` body `{"group_id": int, "plugin_key": str, "enabled": bool}` → 系统插件 400「系统插件不可禁用」；未知 key 400「插件不存在」；其余 INSERT OR IGNORE / DELETE 后返回最新状态
- `GET /api/admin/config` → `{"yaml": "<原文>", "path": "<文件名>", "restart_hint": true}`
- `PUT /api/admin/config` body `{"yaml": str}` → 校验（非空、safe_load 得 dict、`_REQUIRED` 逐键非 None/""/[]）→ 400 附具体原因（解析异常/缺键列表）且**不落盘** → 通过则备份（复制为 `<path>.bak`，保留一代）→ 写 `<path>.tmp` + `os.replace` 原子覆盖 → `{"ok": true}`

## ③ bot 侧修复（D6）

- `core/context.py::migrate_group_plugin_config`：先查 `sqlite_master` 表是否存在，存在→直接返回（不播种）；不存在→建表+播种默认群全量非系统插件
- `core/context.py::is_plugin_enabled`、`plugins/group_manager`（_get_config/_set_config/_set_pack_config 等全部连接点）：`sqlite3.connect("data.db")` → `sqlite3.connect(str(config.DB_PATH))`

## ④ 边界

- web 写库与 bot 读库并发：SQLite WAL 行级，实时生效无缓存问题
- 保存的配置写入后 webapp/bot 仍用旧值运行（import 冻结）——提示已覆盖；`.bak` 一代手动回滚
- 群号未知/预配置：允许（QQ 端同语义），范围清单下次出现自动显示
- 裸 .py 插件文件计入清单（与 pkgutil 注册的 key 口径一致：模块名）

## ⑤ 测试

- 新 `test/scripts/check_admin_dashboard.py`：三端点非超管 403；scopes 形状（含私聊+默认群）；plugins 列表形状（含系统插件标记）；toggle 启/禁写库验证（读 `group_plugin_config`）；系统/未知插件 400；config GET 原文一致；PUT 坏 YAML 400 且文件未变；PUT 缺必填 400；PUT 合法 → 文件回写 + `.bak` 生成 + GET 回读一致
- 新 `test/test_admin_render.js`：范围下拉渲染、锁定区不可点、toggle 点击调 PUT、textarea+提示渲染
- 新进程内 `test/test_plugin_migrate.py`：建库播种默认群；删一行后重复 migrate **不复活**；表已存在时不播种
- 全量 `pytest`

## ⑥ 文档与版本（同 commit）

- CHANGELOG `[1.36.0]` minor + `BOTERO_VERSION` bump
- `specs/web-gallery.md`：模块数 11→12（模块表/路由表/API 节/页面清单）+ admin 小节
- `AGENTS.md` 与 `CLAUDE.md` 中「11 个模块」表述同步 12
- `kb/DATABASE.md` 不动（`group_plugin_config` 无 schema 变更，仅修复播种语义）
- `kb/OPERATIONS.md` 外部 API 无变化
