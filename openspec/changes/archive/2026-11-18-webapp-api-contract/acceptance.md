# 验收记录

环境：feat/webapp-api-contract（base master a1c31af），Windows 开发机，2026-11-18。

| AC | 验证命令 | 结果 | 证据 |
|---|---|---|---|
| AC01 | `python test/scripts/check_webapp_api_contract.py`（schema 段） | ✅ | 「openapi.json 登录可取」「全部 /api/* JSON 路由有响应 schema」通过（图片路由 avatar.png/icon 豁免） |
| AC02 | 同上（分页段） | ✅ | 偏移列表 guestbook/checkins/me-checkins 含 items/total/page/page_size；游标流 forum posts/comments 含 next_cursor；timeline/new 为 events/next_after 形态；全站无 limit 参数残留；page=0 与 page_size=0 → 422 含 detail |
| AC03 | 同上（nav 段）；`rg -n "entries\.json" webapp/` | ✅ | /api/nav 登录返回导航数组、未登录 401；rg 仅剩 timeline/app.py 内部数据文件路径与注释说明，无路由/前端引用 |
| AC04 | 同上（live 段） | ✅ | 未配置 hls → `{"flv": ..., "hls": null}`；配置后双地址；status/heartbeat/viewers 行为未动 |
| AC05 | `python -m pytest -q` | ✅ | 976 passed, 0 failed（含更新后的 node DOM 用例与 check_timeline_*、check_forum_comment_threads_api、check_activities_api 适配） |
| AC06 | `openspec validate 2026-11-18-webapp-api-contract --strict`；归档后两能力 `--strict` | ✅ | 归档前变更级校验通过；归档后 `openspec validate webapp-api-contract --strict` 与 `openspec validate web-navigation --strict` 通过（存量 Purpose 过短警告已随扩写消除） |
| AC07 | 同 AC01 脚本（认证段） | ✅ | 全局 bearerAuth scheme + 顶层 security；login 与 timeline events 三路径标注 `security: []`；三个端点无凭证 401（体含 detail）、带凭证非 401；`make_login_key` 密钥经 login 成功换取 user_id 与 token |

补充：`node test/test_timeline_render.js` 单跑通过（entries.json stub 已改 /api/nav）。
