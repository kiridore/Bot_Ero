# 实施与验收任务

## 1. 配置层
- [x] 1.1 `core/config.py` 新增 `_app_update = _sec("app_update")` 与 `APP_UPDATE` 暴露（缺段 = `{}`），`BOTERO_VERSION` 2.2.0 → 2.3.0。对应 AC01、AC06。
- [x] 1.2 `config.example.yaml` 新增带注释的 `app_update` 段（8 键，`apk_url` 留空 = 未启用）。对应 AC01、AC05。

## 2. Web 层
- [x] 2.1 新增 `webapp/appversion/__init__.py`、`webapp/appversion/app.py`：`APIRouter` 只导出 `router`；`AppVersionOut` pydantic 模型 8 字段；`GET /api/app/version` 带 `Depends(get_current_user_id)`。对应 AC02、AC04。
- [x] 2.2 请求期校验：未配置/`apk_url` 空 → 404「未配置应用更新」；段非映射、`version` 空、`version_code` 非正整数、`apk_url` 非 http(s) 绝对直链、`sha256` 非 64 hex、`size`/`min_supported_version_code` 负数 → 500 + 字段级 detail；SHA-256 统一小写输出；启动不校验。对应 AC01、AC03。
- [x] 2.3 `webapp/app.py` 注册 `appversion_router`（不改门控白名单与 OpenAPI security 豁免）。对应 AC02、AC04。

## 3. 测试
- [x] 3.1 新增 `test/test_app_version.py`：未配置 404、`apk_url` 空 404、合法清单全字段与类型、SHA-256 小写归一、各非法配置 500 + detail 含键名、未登录 401。对应 AC01–AC04。
- [x] 3.2 全量 `python -m pytest -q`。对应 AC07。

## 4. 文档
- [x] 4.1 新增 `docs/app-release.md`：顶部更新清单提醒、七步 checklist、强制更新规则、keystore 不可更换、停用与排错说明。对应 AC05。
- [x] 4.2 `docs/webapp-api.md` 端点目录新增 App 更新条目（字段、登录、404 语义）。对应 AC05。
- [x] 4.3 `KNOWLEDGE_BASE.md` 快速入口新增一行指向 `docs/app-release.md`。对应 AC05。
- [x] 4.4 `CHANGELOG.md` 顶部新增 `[2.3.0]` 节。对应 AC06。

## 5. 验收与交付
- [x] 5.1 逐条执行 AC01–AC08，把命令与结果记入 `acceptance.md`。对应 AC01–AC08。
- [x] 5.2 `openspec validate 2026-11-20-app-version-manifest --strict` → `openspec archive 2026-11-20-app-version-manifest --yes` → `openspec validate --all --strict`；归档、代码、测试、文档同一 commit（不提交 `app/` 子模块指针）。对应 AC08。
