# App 版本清单接口与应用内更新发布流程（2.3.0）

## Why

所有者原始指令（不得改写）：

> 能不能在app内推送更新，不需要用户手动下载新的apk

背景事实：

- 客户端 `app/`（Flutter，独立子模块，当前 `pubspec.yaml` 为 `0.18.3+36`）目前只能由用户自行找 APK 手动安装更新。
- 主仓库 webapp 已有统一登录门控与 118 条 API 路径，但**没有任何与 App 版本相关的端点**，也没有 `config.yaml` 的 App 发布配置段；客户端无法询问「现在最新是哪个版本」。
- 已定裁决（本次不得更改）：Q1:B —— App **启动时静默检查** + 设置页**手动检查**；`version_code < min_supported_version_code` 时客户端**强制更新**；Q4:C —— **APK 存外部对象存储**，服务端只下发清单，不托管、不代理二进制。

本次要解决的是服务端缺口：提供一个登录保护、配置驱动、只读的版本清单端点，并给出可重复执行的发布流程文档（所有者显式要求文档写清「每次发布新版本都要更新清单」）。

## What Changes

- `core/config.py`：新增可选配置段读取 `APP_UPDATE = _sec("app_update")`（缺段 = `{}`，不因缺段启动失败）；`BOTERO_VERSION` 2.2.0 → **2.3.0**。
- 新增 `webapp/appversion/__init__.py` + `webapp/appversion/app.py`：`APIRouter`，只导出 `router`；`GET /api/app/version`，`response_model=AppVersionOut`（pydantic 强类型），`Depends(get_current_user_id)`，与其它 API 同受全站登录门控。
- 新增配置校验（请求期，不阻塞启动）：`version` 非空、`version_code` 正整数、`apk_url` 为 http(s) 绝对直链、`sha256` 非空时须 64 位 hex（大小写不敏感，响应统一小写）、`size` 与 `min_supported_version_code` 非负。配置非法 → **500 + 指明字段的 `detail`**；未配置（缺段或 `apk_url` 为空）→ **404「未配置应用更新」**，不返回空壳 200。
- `webapp/app.py`：注册 `appversion` router（不改门控白名单、不改 OpenAPI security 豁免）。
- `config.example.yaml`：新增带注释的 `app_update` 段（8 个键）。
- `docs/app-release.md`（新增）：发布 checklist（bump `app/pubspec.yaml` → `flutter build apk --release -Pkotlin.incremental=false` → 上传对象存储 → `sha256sum` → 更新 `config.yaml` → 重启 webapp → 手机验证「设置 → 检查更新」），顶部醒目提醒「每次发布新版本都要更新清单」，并写明 **keystore 不可更换**（换了用户无法覆盖升级）。
- `docs/webapp-api.md`：端点目录新增 App 更新条目（响应字段与 404 语义）。
- `KNOWLEDGE_BASE.md`：快速入口表新增一行指向 `docs/app-release.md`。
- `test/test_app_version.py`（新增，进程内 pytest + TestClient）：未配置 404、合法清单全字段与类型、各非法配置 500、未登录 401。
- `CHANGELOG.md`：顶部新增 `[2.3.0]` 节。
- 不改 `app/` 子模块、不改 `android/**`、不改任何 bot 插件、不改数据库 schema。

## Capabilities

### New Capabilities

- `app-update`：App 内更新清单能力——`GET /api/app/version` 下发版本号、APK 外部直链、SHA-256、大小、更新说明、强制更新阈值与发布时间；清单完全由 `config.yaml` 的 `app_update` 段驱动，无数据库、无二进制托管。

### Modified Capabilities

无。现有 `webapp-api-contract` 的通用约束（登录、错误体、additive 演进）已覆盖本端点，本端点只是新增一条 `/api/*` JSON 路由并遵循既有约定，无需改写该能力规范。

## Scope and Compatibility

- **社区版与私有版两者一致**：改动全在 webapp 与新配置段，不读 `edition`、无分支；两个部署用同一套实现，差异只可能来自各自 `config.yaml` 是否填了 `app_update`。
- **既有部署与旧数据**：`app_update` 为可选段，缺失即未配置（端点 404），旧 `config.yaml` 无需修改、无需迁移，bot 进程零改动（`core/config.py` 只多读一个可选段）。
- **配置不合法不阻塞任何进程启动**：bot 与 webapp 启动不因 `app_update` 内容错误而退出；错误只在请求该端点时以 500 + 具体字段名暴露。
- **旧客户端**：不请求该端点的客户端完全不受影响；新客户端拿到 404 时静默跳过（视为功能未启用）。
- **不做什么（Non-goals）**：不在服务端托管/上传/代理 APK 二进制；不做灰度发布、多渠道/多平台清单、版本历史表、自动下载安装、bot 侧推送通知；不改客户端代码与子模块指针；不新增数据库表。
- **版本 bump**：新增 API + 新配置段属新功能 → **minor**，2.2.0 → 2.3.0。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python -m pytest -q test/test_app_version.py -k unconfigured` | 缺 `app_update` 段与「段存在但 `apk_url` 为空」两种情形均返回 404，`detail` 含「未配置应用更新」，且不返回空壳 200 |
| AC02 | `python -m pytest -q test/test_app_version.py -k valid_manifest` | 返回 200，`version/version_code/apk_url/sha256/size/notes/min_supported_version_code/published_at` 八字段齐全，整数为 JSON number、字符串为 JSON string；大写 SHA-256 响应归一为小写 |
| AC03 | `python -m pytest -q test/test_app_version.py -k invalid` | `apk_url` 非 http(s)/非绝对直链、`sha256` 非 64 位 hex、`size` 负数、`version_code` 非正整数、`min_supported_version_code` 负数、`app_update` 段非映射，逐项返回 500 且 `detail` 含对应配置键名；导入/启动不抛异常 |
| AC04 | `python -m pytest -q test/test_app_version.py -k unauthenticated` | 不带凭证请求 `/api/app/version` 返回 401 且不泄露清单 |
| AC05 | `rg -n "每次发布新版本都要更新清单|keystore|kotlin.incremental|sha256|重启 webapp" docs/app-release.md`；`rg -n "api/app/version" docs/webapp-api.md KNOWLEDGE_BASE.md` | `docs/app-release.md` 顶部提醒、7 步 checklist、keystore 不可更换说明齐全；`docs/webapp-api.md` 有端点条目；`KNOWLEDGE_BASE.md` 快速入口指向该文档 |
| AC06 | `rg -n 'BOTERO_VERSION = "2.3.0"' core/config.py`；`sed -n '7,20p' CHANGELOG.md` | 版本号为 2.3.0；CHANGELOG 顶部 `[2.3.0]` 节描述本次新功能 |
| AC07 | `python -m pytest -q` | 全量通过（0 failed，含新增 `test_app_version.py`） |
| AC08 | `openspec validate 2026-11-20-app-version-manifest --strict`；`openspec archive 2026-11-20-app-version-manifest --yes`；`openspec validate --all --strict` | 归档前变更级 `--strict` 通过；归档后能力 `app-update` 进入 `openspec/specs/`；`--all --strict` 27 项全过（基线 26 + 新增 1）；归档与实现同一 commit |

## 维护者可持续性

清单只有 8 个标量、一次发布改一次，用 `config.yaml` 单一来源即可：不新增表、不新增迁移、不新增服务，也不新增第二个读取方。发布流程文档把「改清单」写进每一步 checklist 并在顶部提醒，避免「APK 传了但清单没更新」这类静默失效；校验在请求期做，发布时手机上点一次「检查更新」就能看到字段级错误提示。
