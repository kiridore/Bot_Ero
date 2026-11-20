# App 内更新发布流程（Flutter 客户端）

> ⚠️ **每次发布新版本都要更新清单。** 客户端只认 `config.yaml` 的 `app_update` 段：只把 APK 传到对象存储、不更新清单，老客户端**永远收不到更新提示**（启动静默检查与设置页手动检查都只会看到旧版本）。

本仓库（服务端）在应用内更新里只做一件事：向 App 下发版本清单。APK 二进制托管在**外部对象存储**，服务端不存储、不上传、不代理下载。客户端（`app/` 子模块，Flutter）拿到清单后自行下载 APK、校验 SHA-256，再拉起系统安装器。

- 端点：`GET /api/app/version`（需登录，App 已登录即可；契约见 [`docs/webapp-api.md`](webapp-api.md)）
- 检查时机：App **启动时静默检查** + 设置页**手动检查**
- 强制更新：`当前 version_code < min_supported_version_code` 时客户端强制更新，不允许跳过

## 清单字段

| 字段 | 类型 | 含义 | 来源 |
|---|---|---|---|
| `version` | string | 展示用语义化版本 | `app/pubspec.yaml` 的 `version` 前半段 |
| `version_code` | int | 客户端比较用的单调递增整数 | `pubspec.yaml` 的 `version` 后半段（buildNumber） |
| `apk_url` | string | APK 直链，**必须 http(s)**；留空 = 未启用应用内更新（接口 404） | 对象存储 |
| `sha256` | string | APK 的 SHA-256（64 位 hex，大小写均可） | 构建产物 |
| `size` | int | APK 字节数 | 构建产物 |
| `notes` | string | 更新说明纯文本，支持换行 | 手写 |
| `min_supported_version_code` | int | 低于此版本码的客户端强制更新 | 手写 |
| `published_at` | string | 发布时间 `YYYY-MM-DD HH:MM:SS` | 手写 |

## 发布 checklist（每次发版按顺序做）

### ① 提升 `app/pubspec.yaml` 的 version

```yaml
version: 0.19.0+37   # 语义化版本+buildNumber
```

`buildNumber` 必须比上一版**大**（客户端靠它比较），并原样填进清单的 `version_code`。首发是 `0.18.3+36` 时，下一版就是 `0.19.0+37`。

### ② 构建 release APK

```bash
cd app
flutter build apk --release -Pkotlin.incremental=false
```

- Windows 上 Kotlin 增量缓存偶发导致构建失败（`Could not close incremental caches` 之类），固定加 `-Pkotlin.incremental=false` 关闭增量。
- 签名用 `app/android/key.properties` + `app/android/app/release.jks`（两者都不入库）；没有 keystore 时会回退 debug 签名，**debug 签名的包不能用于发布**（见文末签名说明）。
- 产物：`app/build/app/outputs/flutter-apk/app-release.apk`。

### ③ 上传 APK 到对象存储

上传到外部对象存储（OSS/S3/R2 等），拿到一个公网可访问的 **https 直链**，填进 `apk_url`。要求：

- 直链不带登录、不落到 HTML 页面（客户端直接按二进制下载）。
- 文件名带版本（如 `botero-0.19.0-37.apk`），避免对象存储缓存旧文件。
- 每次发版都重新上传并换 URL；客户端每次都会重新取清单，URL 可以随便变。

### ④ 计算 SHA-256 与大小

```bash
# Linux / macOS
sha256sum app-release.apk            # macOS 无 sha256sum 时用：shasum -a 256 app-release.apk
stat -c%s app-release.apk
```

```powershell
# Windows PowerShell
(Get-FileHash .\app-release.apk -Algorithm SHA256).Hash   # 大写 hex，服务端会归一为小写
(Get-Item .\app-release.apk).Length
```

`sha256` 必须与**上传后的那个文件**一致（先上传后计算，或算完确认真实上传的是同一个文件）。客户端下载失败校验会拒绝安装。

### ⑤ 更新 `config.yaml` 的 `app_update` 段

```yaml
app_update:
  version: "0.19.0"
  version_code: 37
  apk_url: "https://oss.example.com/botero/botero-0.19.0-37.apk"
  sha256: "<第④步算出的 64 位 hex>"   # 可大写，服务端响应会归一为小写
  size: 58976234                    # 第④步结果
  notes: |
    本次更新：
    - 新增 xxx
    - 修复 xxx
  min_supported_version_code: 37    # 37 = 所有低于本版的客户端强制更新；只强制很老的版本就填更小的值
  published_at: "2026-11-20 18:00:00"
```

- `version` 建议加引号，避免 YAML 把 `0.20` 这类值当数字解析。
- `min_supported_version_code`：填**本版 version_code** = 老客户端全部强制更新；填更小的值（如 `30`）= 只强制低于该版本的客户端。
- 不想强制更新时填 `0`。
- 留空 `apk_url` 即停用应用内更新：接口返回 404，App 静默跳过检查。

### ⑥ 重启 webapp

配置在进程 import 时读取、**不会热加载**：

```bash
systemctl restart botero-web        # 或：./scripts/botero-services.sh restart
# 本地联调：python -m webapp
```

### ⑦ 手机上验证

1. 打开新版 App：**设置 → 检查更新**，应看到第⑤步的版本号与 `notes`。
2. 下载安装，确认覆盖安装成功（签名一致）且版本号变为新版本。
3. 若设置了 `min_supported_version_code`，用一台低于阈值的旧版 App 验证：启动即弹**强制更新**、不能跳过。
4. 反向验证：把 `apk_url` 临时留空重启 webapp，App 检查更新应静默无提示（接口 404，不报错）。

## 签名：keystore 不可更换

`app/android/app/release.jks` 与 `app/android/key.properties` 是**唯一**的发布签名。Android 只允许签名相同的 APK 覆盖安装：

- **keystore 一旦定下不可更换。** 换了签名，已安装用户无法覆盖升级，只能卸载重装（本地数据丢失）。
- `release.jks`、`key.properties` 及密码必须备份（仓库外私密保存）；本地与任何 CI 构建都必须使用同一把 keystore。
- 没有 keystore 时构建会回退 debug 签名——debug 签名的包与正式包签名不同，同样无法覆盖安装，不能发布。

## 排错

| 现象 | 原因 / 处理 |
|---|---|
| App 检查更新无反应（静默） | 接口 404：`config.yaml` 缺 `app_update` 段或 `apk_url` 为空；补齐后重启 webapp |
| 接口 500 | `detail` 直接点名哪个键不合法：`version` 空、`version_code` 非正整数、`apk_url` 非 http(s) 绝对直链、`sha256` 不是 64 位 hex、`size` / `min_supported_version_code` 负数 |
| 客户端下载后拒绝安装 | `sha256` / `size` 与对象存储上的文件不一致（换过文件没重算），或签名与已安装版本不同 |
| 改了清单没生效 | 没重启 webapp（配置 import 时冻结） |
| 老客户端收不到更新 | 清单没更新（本文顶部提醒的就是这件事），或客户端 `version_code` 已 ≥ 清单版本 |
