# 设计

## 1. 数据来源：配置驱动，不建库

清单只有 8 个标量（版本号、版本码、APK 直链、SHA-256、大小、说明、强制更新阈值、发布时间），一次发布改一次，读取方只有 webapp 一个端点，没有历史、查询、并发写入需求。因此放 `config.yaml` 的 `app_update` 段：

```yaml
app_update:
  version: "0.19.0"
  version_code: 37
  apk_url: ""
  sha256: ""
  size: 0
  notes: ""
  min_supported_version_code: 0
  published_at: ""
```

不建表、不做 DB 迁移的理由：SQLite 会引入建表/迁移/写入方（谁写、怎么并发、半写残留），而本数据的发布节奏是「每次发版改一次配置 + 重启 webapp」，配置文件的原子替换与版本控制已经满足需求；将来若需要历史版本或网页后台管理，再引入表属于新的提案。

读取：`core/config.py` 在 import 时 `_sec("app_update")` 求值，缺段得到 `{}`。配置在进程启动时冻结，**改完必须重启 webapp**（`python -m webapp` / `systemctl restart botero-web`），与项目其它配置项同一行为。bot 进程同样会读取该段（共享 `core/config.py`）但无任何消费方，因此 bot 对此零感知。

跨进程：唯一读取方是 webapp；bot 不读也不写，不存在并发与半写问题。

## 2. 接口与响应

- 路由：`GET /api/app/version`，新增 `webapp/appversion/app.py`（`APIRouter`，只导出 `router`），在 `webapp/app.py` `include_router`。
- 鉴权：`Depends(get_current_user_id)`（`core/web/auth_deps.py` 唯一权威副本），与其它 API 一致；全站 `login_guard` 中间件在路由前拦截未登录请求（`/api/` 前缀 → 401 JSON），**不改白名单、不加 OpenAPI security 豁免**。
- 响应模型（pydantic，字段名即契约）：

```json
{
  "version": "0.19.0",
  "version_code": 37,
  "apk_url": "https://oss.example.com/botero/app-release.apk",
  "sha256": "<64 位小写 hex>",
  "size": 58976234,
  "notes": "更新说明纯文本，可含换行",
  "min_supported_version_code": 30,
  "published_at": "2026-11-20 18:00:00"
}
```

- `version_code` 是客户端比较用的单调递增整数；`version` 仅供展示，服务端不做语义化版本解析。
- `min_supported_version_code`：客户端 `version_code <` 该值时强制更新；服务端不参与比较，只下发阈值。
- 服务端**不托管二进制**：没有 APK 上传/下载/代理路由，`apk_url` 必须是外部对象存储的 http(s) 绝对直链。

## 3. 未配置语义：404，不返回空壳 200

缺 `app_update` 段或 `apk_url` 为空 → `404 {"detail": "未配置应用更新"}`。

理由：

- 客户端「启动静默检查」需要一个零歧义信号：404 = 服务端未启用应用内更新，静默跳过，不需要额外判断字段是否为空。
- 空壳 200 会把「功能未启用」与「已启用但清单半填（空 URL/空版本）」混在一起，客户端只能自己猜，猜错就会把空 URL 交给下载器。
- 404 也让运维一眼看出「清单没配」；配置了但写错则走下面的 500，两类问题互不混淆。

`apk_url` 作为启用开关（而不是单独 `enabled` 布尔）：少一个键、少一种「开关开了但 URL 空」的矛盾状态；`config.example.yaml` 里 `apk_url: ""` 即默认关闭。

## 4. 配置校验：请求期校验，500 + 字段级 detail

启动**不校验、不退出**。理由：`core/config.py` 由 bot 与 webapp 共享，一个 webapp 专属可选段写错不应拖垮 bot 进程；webapp 也不应因为一个发布配置的笔误整站起不来（社区站还有其它 11 个模块在用）。错误在请求 `GET /api/app/version` 时以 500 暴露，`detail` 直接写明哪个键不合法，发布时手机点一次「检查更新」即可定位。

校验规则（顺序执行，首个失败即返回）：

| 键 | 规则 | 失败 detail |
|---|---|---|
| `app_update` 段 | 必须是映射 | `app_update 配置必须是映射` |
| `apk_url` | 非空、`urlsplit` scheme ∈ {http, https} 且有 host | `app_update.apk_url 必须是 http(s) 绝对直链` |
| `sha256` | 非空时须 `[0-9a-fA-F]{64}`；响应统一小写 | `app_update.sha256 必须是 64 位十六进制` |
| `version` | 非空 | `app_update.version 不能为空` |
| `version_code` | 可按 `int()` 解析且 > 0 | `app_update.version_code 必须是整数` / `必须是正整数` |
| `size` | 可按 `int()` 解析且 ≥ 0 | `app_update.size 必须是整数` / `不能为负数` |
| `min_supported_version_code` | 可按 `int()` 解析且 ≥ 0 | 同上模式 |

选项与边界：

- `sha256` 大小写不敏感（hex 本身无语义大小写），统一输出小写，客户端只需按一种形态比较；不校验「是否有等号前后缀」——写错自然不匹配 64 hex。
- `size` / `min_supported_version_code` 缺省按 0；`size: 0` 合法（客户端可跳过进度显示，但 SHA-256 仍用于校验）。
- `notes` / `published_at` 原样字符串透传（`notes` 支持换行；`published_at` 格式 `YYYY-MM-DD HH:MM:SS`，不做时间解析——服务端不需要用它排序或判定）。
- `version_code` 单调递增、与 `app/pubspec.yaml` 的 buildNumber 一致、对象存储上的文件与 `sha256`/`size` 一致，都是**发布流程责任**，服务端无法验证 APK 实体，只能由 `docs/app-release.md` 的 checklist 约束。

## 5. 发布流程文档

新增 `docs/app-release.md`，顶部醒目提醒「每次发布新版本都要更新清单」，正文 7 步 checklist：

1. 提升 `app/pubspec.yaml` 的 `version`（`x.y.z+buildNumber`，buildNumber 递增，与 `version_code` 一致）
2. `flutter build apk --release -Pkotlin.incremental=false`（Windows 上 Kotlin 增量缓存偶发构建失败）
3. 上传 APK 到对象存储，取得公开 https 直链
4. 计算 SHA-256（Linux `sha256sum` / Windows `certutil -hashfile ... SHA256`）
5. 更新 `config.yaml` 的 `app_update` 段（含 `min_supported_version_code` 与 `notes`）
6. 重启 webapp（配置在 import 时冻结）
7. 手机上验证「设置 → 检查更新」，再验证低于阈值的客户端被强制更新

并写明 **keystore 不可更换**：换签名后新旧 APK 签名不一致，用户无法覆盖安装（只能卸载重装、丢本地数据），keystore 与密码须备份、本地与 CI 使用同一把。

文档同时登记到 `docs/webapp-api.md`（端点目录）与 `KNOWLEDGE_BASE.md`（快速入口），避免只有发布者知道的孤岛文档。

## 6. 测试清单

`test/test_app_version.py`（进程内 pytest，TestClient 走真实中间件 + 路由 + pydantic 序列化；`core.config.APP_UPDATE` 用 `mock.patch.object` 逐用例注入，不触碰真实 `config.yaml` / `server_data`，conftest 已保证进程配置指向临时目录）：

1. 未配置（conftest 临时配置本就无该段）→ 404 + detail。
2. 段存在但 `apk_url` 为空 → 404（不返回空壳 200）。
3. 合法配置 → 200，八字段值/类型逐一断言；大写 SHA-256 归一为小写。
4. `apk_url` 非 http(s) / 非绝对 → 500 + detail 含 `apk_url`。
5. `sha256` 非 64 hex → 500 + detail 含 `sha256`。
6. `size` 负数 / 非整数 → 500 + detail 含 `size`。
7. `version_code` 为 0 / 非整数 → 500 + detail 含 `version_code`。
8. `min_supported_version_code` 负数 → 500 + detail 含该键。
9. `app_update` 段非映射 → 500。
10. 未登录 → 401（中间件在路由前拦截），响应不含清单字段。

## 7. 边界与失败路径

- 配置段缺失：`_sec` 返回 `{}` → 404；bot/webapp 启动不受影响。
- 配置非法：仅该端点 500；其它模块与 bot 不受影响。
- 对象存储不可达：与本服务无关——客户端直接访问 `apk_url`，服务端不代下载、不缓存；URL 可随时更换，客户端每次取清单。
- 强制更新判定全在客户端：服务端只给阈值，`version_code` 回退或写 0 会表现为「老客户端被判强制更新」，由 checklist 约束。
- 旧客户端不调用本端点：零影响；新客户端遇 404 静默跳过。
