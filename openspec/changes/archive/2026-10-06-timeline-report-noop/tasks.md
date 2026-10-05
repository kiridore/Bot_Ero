# Tasks · 时间线上报可关（T0.3）

> 每完成一项勾选；全量 pytest 绿为前置出口（红线：主干逐 commit 私有形态安全）。

- [x] 1. 新增 `test/test_timeline_noop.py`：
  - 空 `TIMELINE_URL`（`mock.patch("core.timeline_client.TIMELINE_URL", "")`）下 `emit_event` / `retract_event` 断言 `requests.post` / `requests.request` 零调用且不抛异常
  - 有 `TIMELINE_URL` 下 mock `requests` 断言 URL 拼接与 Bearer 头（回归既有行为）
- [x] 2. 全量 `pytest` 绿
- [x] 3. `docs/community/development-plan.md`：T0.3 任务节勾选 + 挂本提案链接，进度追踪行同步
- [x] 4. CHANGELOG `[未发布]` 记内部条目（测试+文档收尾，不 bump `BOTERO_VERSION`）
- [x] 5. commit：`test(时间线): 空配置上报 no-op 断言并收尾 T0.3`
