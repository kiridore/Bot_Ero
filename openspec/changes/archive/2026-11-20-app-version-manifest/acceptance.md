# 验收记录

环境：master（HEAD `1fc128a`，Windows 开发机），2026-11-20。bot 进程、数据库、`app/` 子模块零改动（子模块指针不提交）。

| AC | 验证命令 | 结果 | 证据 |
|---|---|---|---|
| AC01 | `python -m pytest -q test/test_app_version.py -k unconfigured` | ✅ | `2 passed, 13 deselected`：「缺 `app_update` 段 → 404」「段存在但 `apk_url` 为空 → 404 且响应无 `version` 字段」，`detail` 均为「未配置应用更新」 |
| AC02 | `python -m pytest -q test/test_app_version.py -k valid_manifest` | ✅ | `2 passed, 13 deselected`：八字段与注入值逐项相等（整数字段 `isinstance(..., int)`、字符串字段 `isinstance(..., str)`）；大写 `sha256` 响应归一为小写 |
| AC03 | `python -m pytest -q test/test_app_version.py -k invalid` | ✅ | `10 passed, 5 deselected`：`apk_url` 非 http(s) / 非绝对直链、`sha256` 非 64 hex、`size` 负数 / 非整数、`version_code`=0 / 非整数、`version` 空、`min_supported_version_code` 负数、`app_update` 非映射，均 500 且 `detail` 含对应键名；注入非法配置期间 TestClient 正常（启动/导入未抛异常） |
| AC04 | `python -m pytest -q test/test_app_version.py -k unauthenticated` | ✅ | `1 passed, 14 deselected`：无凭证 → 401，响应体不含 `apk_url` |
| AC05 | `rg -n "每次发布新版本都要更新清单\|keystore\|kotlin.incremental\|sha256\|重启 webapp" docs/app-release.md`；`rg -n "api/app/version" docs/webapp-api.md KNOWLEDGE_BASE.md` | ✅ | `docs/app-release.md:3` 顶部醒目提醒；七步 checklist（① pubspec ② 构建 ③ 上传 ④ SHA-256 ⑤ 更新清单 ⑥ 重启 webapp ⑦ 手机验证）齐全；`docs/app-release.md:107-113` 写「keystore 一旦定下不可更换」；`docs/webapp-api.md:198` 端点条目；`KNOWLEDGE_BASE.md:22` 快速入口指向发布文档 |
| AC06 | `rg -n 'BOTERO_VERSION = "2.3.0"' core/config.py`；`sed -n '7,16p' CHANGELOG.md` | ✅ | `core/config.py:17:BOTERO_VERSION = "2.3.0"`；CHANGELOG 顶部 `[2.3.0]` 节描述新接口、配置段与发布文档 |
| AC07 | `python -m pytest -q` | ✅ | `1027 passed, 0 failed`（基线 1012 + 新增 15） |
| AC08 | `openspec validate 2026-11-20-app-version-manifest --strict`；`openspec archive 2026-11-20-app-version-manifest --yes`；`openspec validate --all --strict` | ✅ | 归档前：`Change '2026-11-20-app-version-manifest' is valid`；归档后：`--all --strict` 27 passed, 0 failed（基线 26 + 新增能力 `app-update` 1）；归档与实现同一 commit |

## 行为验证说明

- **真实调用**：AC01–AC04 与下方接口示例均通过 `TestClient` 走完整登录中间件 → 路由 → `response_model` 序列化，不是直接调用 `_manifest`。
- **接口 JSON 示例**（临时配置 + 临时 DB，`BOTERO_CONFIG` 指向 `test/scripts/_env.write_config` 产物，未触碰真实 `config.yaml` / `server_data`）：

```json
{
  "version": "0.19.0",
  "version_code": 37,
  "apk_url": "https://oss.example.com/botero/botero-0.19.0-37.apk",
  "sha256": "2f1c0a91d3b8e4f5a6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
  "size": 58976234,
  "notes": "本次更新：\n- 新增深色模式\n- 修复若干问题",
  "min_supported_version_code": 30,
  "published_at": "2026-11-20 18:00:00"
}
```

- **404 与 500 的分工**：未配置（缺段 / `apk_url` 空）= 404，客户端静默跳过；已配置但字段写错 = 500 + 字段级 detail，发布时手机点一次「检查更新」即可定位，且不拖垮 bot/webapp 启动（配置只在请求期读取，`core/config.py` 只新增可选段读取）。
- **既有部署**：`app_update` 为可选段，旧 `config.yaml` 无需修改；未配置时端点 404，其它模块与 bot 不受影响。

## 归档记录

- `openspec validate 2026-11-20-app-version-manifest --strict`：`Change '2026-11-20-app-version-manifest' is valid`。
- `openspec archive 2026-11-20-app-version-manifest --yes`：Specs updated successfully（新增能力 `app-update`）。
- `openspec validate --all --strict`：`Totals: 27 passed, 0 failed (27 items)`。
