# 任务：时间线观看偏好

对应验收标准见 proposal.md；未完成最终验收不得归档。

- [x] T1 `core/user_settings.py`：`show_others_checkin()` 缺省 True + 文档说明（AC01）
- [x] T2 `test/test_user_settings.py`：缺省与持久化断言；设置 API 严格布尔校验和三组局部更新（AC01）
- [x] T3 `webapp/timeline/app.py`：三接口每请求读取一次偏好，共用 `_visible_entry`，保留补页与原始批次游标（AC02、AC03）
- [x] T4 `test/scripts/check_timeline_privacy.py`：关闭、恢复、自见 hidden、他人非打卡、连续过滤超过补页上限和 new 取尽测试；专项通过（AC02、AC03）
- [x] T5 `webapp/static/settings.js`：时间线偏好分组、开关及保存回滚交互；DOM 回归通过
- [x] T6 `python test/scripts/check_timeline_unread.py` 通过（AC04）
- [x] T7 完成最终全量 `python -m pytest -q`，含 API 集合：821 passed，372.16秒（AC05）
- [x] T8 真实 Chrome + 本地 webapp API 联动检查：设置关闭/刷新保持，实际时间线只保留本人打卡及非打卡，390px/桌面截图已打开检查（AC06）
- [x] T9 同步1.57.0 CHANGELOG、BOTERO_VERSION、kb/QUICK_REFERENCE.md 与时间线规范；逐条证据见 acceptance.md
- [x] T10 服务端补页上限后的空页仍有 cursor 时前端自动续读，`test/test_timeline_render.js` 回归已纳入最终全量（AC02/AC03分页边界）
- [ ] T11 同批验收全绿后提交并归档；本轮禁止 commit/push/archive，水印真实QQ检查未完成

## 最终集成验收

按 proposal.md/design.md 的同批裁定，目标版本统一1.57.0，不单独发布中间版本。网站联动和最终回归已完成；真实QQ未测、不归档。完整证据及环境边界见 acceptance.md。

## 执行记录

新增观看偏好测试先出现四项预期失败（feed/poll/两种分页），加入过滤后全部通过；既有时间线隐私和未读回归均通过。测试夹具表名误写已改为实际 `timeline_user_watermarks`。
