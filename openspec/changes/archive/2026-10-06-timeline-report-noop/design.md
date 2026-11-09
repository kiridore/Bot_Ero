# 设计 · 时间线上报可关（T0.3）

## 现状（实现已随 1.45.2 / `70f1e2d` 落地）

- `core/config.py:135-136`：`TIMELINE_URL = str(_timeline.get("url") or "").rstrip("/")`、`TIMELINE_TOKEN` 同理——缺省空串；`timeline` 节的必填性已由 T0.1 按 edition 分侧（社区形态不要求该节）
- `core/timeline_client.py`：模块级 `from core.config import ... TIMELINE_URL`；`_post`（L27）与 `_request`（L44）两个出网出口各有 `if not TIMELINE_URL: return` 守卫
- 公开函数 `emit_event` / `activity_event_args` / `retract_event` 全部经 `_post`/`_request` 出网，无旁路调用 `requests`——一处守卫全覆盖

## 关键决策

1. **守卫放 `_post`/`_request` 两个模块内出口**而非各公开函数：调用方零感知，未来新增上报函数自动继承守卫。
2. **维持模块级 import 绑定读取**（不改结构）：与现状一致，测试用 `mock.patch("core.timeline_client.TIMELINE_URL", "")` 即可覆盖两个出口。
3. **不做运行期开关**（配置热重载/动态启停）：社区形态生命周期内该值不变，YAGNI。

## 剩余工作（本提案实际执行内容）

- 测试 `test/test_timeline_noop.py`：
  - 空 `TIMELINE_URL` 下 `emit_event(...)` 与 `retract_event(...)`：断言 `requests.post` / `requests.request` 不被调用、不抛异常（各自覆盖 `_post` 与 `_request` 两条出口）
  - 有 `TIMELINE_URL` 下回归：mock `requests`，断言请求 URL 拼接（`{url}/api/timeline/events`）与 `Authorization: Bearer` 头
- 文档：勾选 `docs/community/development-plan.md` 进度追踪 T0.3，任务标题挂本提案链接

## 风险与边界

- 私有形态零变化：守卫条件 `not TIMELINE_URL` 在私有配置下恒为 False，逻辑不触达；conftest 生成的即私有形态配置，全量 pytest 天然是私有回归
- `rstrip("/")` 对空串无操作，无边界问题；token 为空仅在 url 也为空时出现（配置了 url 不配 token 属既有配置错误语义，不在本任务范围）
