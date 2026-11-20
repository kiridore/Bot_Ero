# app-update Specification

## Purpose
App 内更新能力：webapp 在统一登录门控内向 Flutter 客户端下发一份只读的版本清单（展示版本、单调递增版本码、APK 直链、SHA-256、字节数、更新说明、强制更新阈值、发布时间），客户端据此在启动时静默检查、在设置页手动检查，并对低于阈值的旧版本强制更新。清单完全由 `config.yaml` 的 `app_update` 段驱动：APK 二进制托管在外部对象存储，服务端不存储、不代理、不分发二进制，也不引入数据库；未配置时端点返回 404，客户端静默跳过。

## Requirements

### Requirement: App 版本清单端点
系统 SHALL 提供 `GET /api/app/version`，与其他 `/api/*` 端点一样受全站登录门控（Bearer 头或根域 cookie），未登录 MUST 返回 401 且不泄露清单。成功响应 SHALL 为 JSON 对象，含且仅含以下字段：`version`（string，展示用语义化版本）、`version_code`（integer，客户端比较用单调递增整数）、`apk_url`（string，外部对象存储 http(s) 绝对直链）、`sha256`（string，64 位小写 hex）、`size`（integer，APK 字节数）、`notes`（string，纯文本，可含换行）、`min_supported_version_code`（integer，低于该值的客户端强制更新）、`published_at`（string，`YYYY-MM-DD HH:MM:SS`）。Response MUST 在 OpenAPI 中以具名 schema 出现。

清单来自 `config.yaml` 的可选 `app_update` 段（`version`、`version_code`、`apk_url`、`sha256`、`size`、`notes`、`min_supported_version_code`、`published_at`）。缺该段或 `apk_url` 为空时，端点 MUST 返回 404，`detail` 说明「未配置应用更新」，MUST NOT 返回字段为空的 200 响应。配置非法时，端点 MUST 返回 500 且 `detail` 指明具体配置键，MUST NOT 阻止 bot 或 webapp 进程启动。

配置校验规则：`app_update` 段 MUST 为映射；`version` MUST 非空；`version_code` MUST 为正整数；`apk_url` MUST 为带 host 的 http(s) 绝对直链；`sha256` 非空时 MUST 为 64 位十六进制（大小写不敏感，响应统一小写）；`size` 与 `min_supported_version_code` MUST 为非负整数。

#### Scenario: 已配置清单
- **WHEN** `app_update` 段填好合法的 `apk_url`、`version`、`version_code` 等字段，已登录客户端请求 `GET /api/app/version`
- **THEN** 返回 200 与完整八字段，整数为 JSON number、字符串为 JSON string，`sha256` 为小写 hex

#### Scenario: 未配置应用更新
- **WHEN** `config.yaml` 没有 `app_update` 段，或该段存在但 `apk_url` 为空
- **THEN** 返回 404，`detail` 含「未配置应用更新」，不返回任何清单字段

#### Scenario: 配置非法
- **WHEN** `apk_url` 不是 http(s) 绝对直链、`sha256` 不是 64 位 hex、`size` 为负、`version_code` 不是正整数，或 `app_update` 段不是映射
- **THEN** 返回 500，`detail` 含对应配置键名；bot 与 webapp 的启动不受影响

#### Scenario: 未登录请求
- **WHEN** 不带凭证请求 `GET /api/app/version`
- **THEN** 返回 401，响应体不含清单字段

### Requirement: APK 二进制外部托管
服务端 MUST NOT 提供 APK 的上传、下载或代理路由；`apk_url` SHALL 指向外部对象存储的公开直链。清单中的 `sha256` 与 `size` SHALL 供客户端下载后校验完整性，服务端不参与下载链路。

#### Scenario: 清单不暴露本服务二进制路径
- **WHEN** 检查 `GET /openapi.json` 的路由集合
- **THEN** 不存在 APK 上传/下载/代理路由，客户端只能按响应中的 `apk_url` 直连外部对象存储

### Requirement: 发布流程文档
`docs/app-release.md` SHALL 提供可重复执行的发布 checklist，并在顶部醒目提醒「每次发布新版本都要更新清单」（否则老客户端收不到更新）。checklist SHALL 覆盖：提升 `app/pubspec.yaml` 版本与 buildNumber、`flutter build apk --release -Pkotlin.incremental=false`（Windows 上 Kotlin 增量缓存偶发失败）、上传 APK 到对象存储、计算 SHA-256、更新 `config.yaml` 的 `app_update` 段、重启 webapp、手机验证「设置 → 检查更新」。文档 SHALL 说明 keystore 不可更换（换签名后用户无法覆盖安装升级）。`docs/webapp-api.md` SHALL 登记 `GET /api/app/version` 端点及其 404 语义。

#### Scenario: 发布流程文档齐全
- **WHEN** 审阅 `docs/app-release.md`
- **THEN** 文档含顶部更新清单提醒、七步 checklist 与 keystore 不可更换说明

#### Scenario: API 参考登记端点
- **WHEN** 查 `docs/webapp-api.md` 的端点目录
- **THEN** 存在 `GET /api/app/version` 条目，说明响应字段、登录要求与「未配置返回 404」
