# 实施与验收任务

> 提案：`proposal.md`；设计：`design.md`；能力规范：`specs/trpg-session-recording/spec.md`、`specs/trpg-record-web/spec.md`。
> 一次实现覆盖全部条目，不中途缩减范围；每条任务标注对应验收标准，完成后在 `acceptance.md` 记证据。

## 1. 数据层

- [x] 1.1 新建 `core/trpg/records.py`：`records_root()`（`core.config.PYTHON_DATA_PATH / "trpg_records"`）、`group_dir()`、`record_dir()`、`media_file()`、`start_dir_name()`、`ensure_record_dir()`、`append_message()`、`rewrite_meta()`、`read_meta()`、`iter_messages()`（逐行解析，坏行跳过并计数）；群号 `^\d+$`、目录名 `^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`、媒体名 `^img_\d{4}\.(jpg|jpeg|png|gif|webp)$` 校验，非法输入抛 `ValueError`。对应 AC01、AC02、AC05、AC06、AC07。
- [x] 1.2 `core/context.py`：录制会话增加 `dir` 字段与 `record_bot_message(group_id, nickname, text)`（无录制时静默返回），沿用 `recording_lock` 保护追加。对应 AC03。

## 2. 插件改造

- [x] 2.1 `plugins/trpg_session/__init__.py`：删除 `TRPG_RECORDS_ROOT` 常量，改走 `core.trpg.records`；开始/强制开始时创建目录、取群名（`get_group_info` 失败降级空串）、写 `meta.json`；`_record_user_message` 追加 `messages.jsonl` 并同步 `participants`（含 `char_name`）；`.dm`/`.ob` 更新 `roles` 并重写 `meta.json`；结束写 `end`；导出从 `messages.jsonl` 生成 `record.md` 并在回执中附 `<WEB_BASE_URL>/trpg/records/<群号>/<目录>`；`_handle_list`/`_handle_view` 改读新路径并展示状态。对应 AC01、AC03、AC04。
- [x] 2.2 图片入档：`_record_user_message` 中图片段先 `get_image_url` + `download_image` 落 `imgs/img_NNNN.<ext>`，成功写相对路径、失败写 `unavailable: true`；下载异常不中断录制。对应 AC02。
- [x] 2.3 `plugins/trpg_dice/__init__.py`：群内输出经统一出口调用 `core.context.record_bot_message` 入档（跑团检定、普通掷骰、暗骰的群内提示不记录结果）；私聊暗骰结果不入档。对应 AC03。

## 3. Web 模块

- [x] 3.1 `webapp/trpg/app.py`：新增 `GET /api/trpg/records`（排序、状态、`mine=1`、坏目录跳过、`message_count`）、`GET /api/trpg/records/{group_id}/{start_dir}?from=`（图片段转 `url`、坏行跳过、404/400）、`GET /trpg/media/{group_id}/{start_dir}/{filename}`（校验后 `FileResponse`）、页面路由 `/trpg/records` 与 `/trpg/records/{group_id}/{start_dir}`。对应 AC05、AC06、AC07。
- [x] 3.2 `webapp/app.py`：`_UNAUTHORIZED_PREFIXES` 增加 `"/trpg/media/"`。对应 AC07。
- [x] 3.3 新建 `webapp/static/trpg_records.html` + `trpg_records.js`（列表 + 「只看我参加的」开关 + 状态徽标）与 `webapp/static/trpg_record.html` + `trpg_record.js`（气泡渲染、5 秒增量轮询、lightbox）；`webapp/static/trpg.css` 追加页签与气泡样式（只用 `:root` token）；`trpg.html` 加页签条。对应 AC08。
- [x] 3.4 `core/web/static/nav.js` 增加「跑团记录」项并把高亮判定改为最长前缀匹配；`webapp/timeline/entries.json` 增加入口卡片。对应 AC08。

## 4. 测试

- [x] 4.1 扩展 `test/test_trpg_session.py`：目录与 `meta.json` 结构、逐条追加与参与者同步、图片成功/失败、机器人消息与暗骰标记、群名成功/失败、结束写 `end`、导出 md 与网页链接；原 `TRPG_RECORDS_ROOT` patch 改为把 `bot.python_data_path` 指向临时目录。对应 AC01–AC04、AC10。
- [x] 4.2 新建 `test/scripts/check_trpg_records_api.py`（`_env.write_config` 重定向 `bot.python_data_path`）：列表排序与三种状态、`mine=1` 过滤、坏目录跳过、详情与 `from` 增量、`reveal` 默认过滤与开启后返回、坏行跳过、404/400、媒体正常与目录穿越拒绝、未登录 401。对应 AC05–AC07、AC10。
- [x] 4.3 新建 `test/test_trpg_records_dom.js`（沿用现有 DOM stub 布局）：自己/他人/机器人气泡类名、DM 与观察者徽标、图片段渲染、页签高亮与导航最长前缀匹配、暗骰默认隐藏与开关后显示。对应 AC08、AC10。

## 5. 文档与交付

- [x] 5.1 `specs/web-gallery.md` 更新模块表与路径分区（新增 `/trpg/records`、`/trpg/media`）；`kb/PLUGIN_CATALOG.md` 与 `specs/plugin-catalog.md` 更新 `trpg_session` 描述（录制即落盘、网页浏览）。对应 AC09。
- [x] 5.2 `CHANGELOG.md` 新增 `[1.62.0]` 节（`[未发布]` 中既有条目保持原样），`core/config.py::BOTERO_VERSION` bump 至 1.62.0。对应 AC09。
- [x] 5.3 全量 `python -m pytest -q` 绿；`openspec validate trpg-record-web --strict` 与 `openspec validate trpg-session-recording --strict` 通过；逐条 AC 证据写入 `acceptance.md`；`openspec archive 2026-11-10-trpg-record-web` 与实现同一 commit。对应 AC09。
