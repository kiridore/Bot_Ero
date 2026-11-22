# 实施与验收任务

## 1. 数据层（`webapp/gallery/repository.py`）
- [x] 1.1 `CheckinImage` 增加 `is_private: bool = False`；`fetch_checkins_paginated` 的查询补选 `is_private` 列并按 `bool(row["is_private"])` 填充（其余查询不参与隐私判定，保持不动，`CheckinImage` 默认值兼容）。对应 AC01、AC04。
- [x] 1.2 `fetch_checkins_paginated` 增加 `keep: Callable[[CheckinImage], bool] | None = None`，在切片前过滤；不传时行为与现状逐字节一致。对应 AC05、AC06。

## 2. 路由层（`webapp/gallery/app.py`）
- [x] 2.1 `api_checkins` 加 `Depends(get_current_user_id)` 取查看者；请求级缓存每作者 `user_settings.checkin_display()`。对应 AC01。
- [x] 2.2 `keep` 谓词：作者本人恒真；非作者只保留 `show`/`blur`（`text`/`hidden` 剔除）。对应 AC02、AC05。
- [x] 2.3 输出改写：非作者且该记录态为 `blur` 时 `thumbnail_url` 与 `image_url` 均为 `/thumb/<作者>/<文件名>?blur=1`；其余情况 URL 与现状一致。对应 AC01、AC03、AC04。

## 3. 测试
- [x] 3.1 新增 `test/scripts/check_gallery_privacy.py`（`write_config` 临时配置，独立进程）：`show` 段、`blur` 段、`text`/`hidden` 段、私聊/群聊分流段、`total`/分页段、媒体路由不变段。对应 AC01–AC05。
- [x] 3.2 既有脚本回归：`check_profile_checkins.py`、`check_special_filename_media.py`、`check_webapp_api_contract.py`。对应 AC06、AC07。
- [x] 3.3 全量 `python -m pytest -q`。对应 AC08。

## 4. 文档与版本
- [x] 4.1 `specs/web-gallery.md`：删去「图库页 `/gallery` 不受此设置影响」，新增图库侧四态规则、作者不过滤、过滤在切片前、媒体直链不强制（已知边界）。对应 AC09。
- [x] 4.2 `docs/webapp-api.md`：`GET /api/checkins` 行写明按查看者下发与三态结果。对应 AC09。
- [x] 4.3 `core/config.py::BOTERO_VERSION` `2.4.0 → 2.4.1`；`CHANGELOG.md` 顶部新增 `[2.4.1]` 节。对应 AC10。

## 5. 验收与交付
- [x] 5.1 逐条执行 AC01–AC11，命令与结果记入 `acceptance.md`。对应 AC01–AC11。
- [x] 5.2 `openspec validate 2026-11-23-gallery-privacy --strict` → `openspec archive 2026-11-23-gallery-privacy --yes` → `openspec validate checkin-gallery --strict`；归档与实现同一 commit（不提交 `app/` 子模块指针）。对应 AC11。
