# T0.2 发送兜底适配 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 社区形态（无默认群）下，无群上下文的三个群发方法（`send_group_msg` / `send_group_forward_msg` / `send_group_forward_nodes`）丢弃发送并告警，私有形态回落默认群行为不变。

**Architecture:** `core/api.py` 新增私有助手 `_group_target()`（上下文群号 → 默认群 → None），三个群发方法统一消费；`None` 即 warning + return 0。无任何 edition 判断（形态差异由 T0.1 配置接缝承担）。

**Tech Stack:** 纯同步 Python，unittest 风格 pytest；FakeWS 同步回注 echo 响应解除 call_api 阻塞。

**Spec:** `docs/superpowers/specs/2026-09-08-send-fallback-drop-design.md`（权威；任务来源 `docs/community/development-plan.md` §T0.2）

## Global Constraints

- **私有形态零行为变化**：既有全部 pytest 用例原样通过（`DEFAULT_GROUP_ID` 在 private 恒 int，回落路径逐字节等价）。
- **无 `if EDITION`**：api.py 只对 `None` 防御（接缝白名单合规，spec P4）。
- **一个逻辑变更一个 commit**：单任务单 commit `fix(发送): 无默认群部署丢弃群发并告警`（代码 + 测试 + CHANGELOG [未发布] + kb 行，不 bump）。
- 测试不建真实 WS、不触碰真实 `server_data`/`data.db`（conftest 临时配置）。
- 提交消息中文 Conventional Commits。

---

### Task 1: 群发兜底丢弃 + 助手收敛

**Files:**
- Modify: `core/api.py:95-101`（`send_group_msg`）、`core/api.py:168-173`（`send_group_forward_msg`）、`core/api.py:189-194`（`send_group_forward_nodes`）、新增 `_group_target` 方法（置于 `send_msg` 之前）
- Create: `test/test_api_send_fallback.py`
- Modify: `CHANGELOG.md`（[未发布] 节）、`kb/QUICK_REFERENCE.md`（`default_group` 行）

**Interfaces:**
- Consumes: T0.1 的 `DEFAULT_GROUP_ID: int | None`（`core.context.DEFAULT_GROUP_ID`，社区形态 `None`）。
- Produces: `ApiWrapper._group_target(self) -> int | None`（私有助手；三个群发方法 `None` 时 return 0）。

- [ ] **Step 1: Write the failing tests**

创建 `test/test_api_send_fallback.py`：

```python
"""无默认群部署（社区形态）的群发兜底：丢弃 + 告警；私有形态回落默认群不变。"""
import json
import sys
import unittest

import core.api as api
import core.context as runtime_context
from core.api import ApiWrapper
from core.cq import text


class _FakeWS:
    """记录发送帧并同步回注 echo 响应，解除 call_api 的 30s 队列阻塞。"""

    def __init__(self):
        self.frames = []

    def send(self, data):
        self.frames.append(data)
        payload = json.loads(data)
        api.echo.match({"echo": payload["echo"], "status": "ok", "data": {"message_id": 42}})


class TestSendFallback(unittest.TestCase):
    def setUp(self):
        api.echo = api.Echo()
        self.ws = _FakeWS()
        api.WS_APP = self.ws
        self.wrapper = ApiWrapper({})  # 裸上下文：无 group_id / user_id
        self._old_default = runtime_context.DEFAULT_GROUP_ID

    def tearDown(self):
        runtime_context.DEFAULT_GROUP_ID = self._old_default

    def test_drop_when_no_default_group(self):
        runtime_context.DEFAULT_GROUP_ID = None
        with self.assertLogs("core.logger", level="WARNING"):
            self.assertEqual(self.wrapper.send_group_msg(text("hi")), 0)
            self.assertEqual(self.wrapper.send_group_forward_msg([text("hi")]), 0)
            self.assertEqual(self.wrapper.send_group_forward_nodes([{"type": "node", "data": {}}]), 0)
        self.assertEqual(self.ws.frames, [])

    def test_fallback_to_default_group_when_configured(self):
        runtime_context.DEFAULT_GROUP_ID = 12345
        self.assertEqual(self.wrapper.send_group_msg(text("hi")), 42)
        self.assertEqual(len(self.ws.frames), 1)
        frame = json.loads(self.ws.frames[0])
        self.assertEqual(frame["action"], "send_group_msg")
        self.assertEqual(frame["params"]["group_id"], 12345)


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_api_send_fallback.py -v`
Expected: `test_drop_when_no_default_group` FAIL（现状把 `group_id=None` 发进 WS → FakeWS 回注 ok → 返回 42 ≠ 0，且 frames 非空）；`test_fallback_to_default_group_when_configured` PASS（私有回落是现状行为）。

- [ ] **Step 3: Implement the helper and rewire three senders**

`core/api.py`，`send_msg` 方法之前插入：

```python
    def _group_target(self) -> int | None:
        """群发目标：上下文群号优先，回落默认群；社区形态无默认群返回 None（调用方丢弃计 0）。"""
        gid = self.context.group_id
        if gid:
            return gid
        fallback = runtime_context.DEFAULT_GROUP_ID
        if fallback is None:
            logger.warning("无群上下文且未配置默认群，丢弃群消息发送")
        return fallback
```

三处 `send_group_msg` / `send_group_forward_msg` / `send_group_forward_nodes` 开头的：

```python
        group_id = self.context.group_id
        if not group_id:
            group_id = runtime_context.DEFAULT_GROUP_ID
```

统一替换为：

```python
        group_id = self._group_target()
        if group_id is None:
            return 0
```

（`send_group_msg` 后续的录制分支使用局部 `group_id`，仅在同值路径到达，不受影响。）

- [ ] **Step 4: Run tests to verify they pass, then full suite**

Run: `python -m pytest test/test_api_send_fallback.py -v` → 2 passed
Run: `python -m pytest -q` → 全绿（预期 348 passed = 346 + 2）

- [ ] **Step 5: CHANGELOG + kb，提交**

`CHANGELOG.md` `## [未发布]` 节顶部追加：

```markdown
- **发送兜底分形态**：无群上下文的群发（send_group_msg / 群合并转发×2）在未配置默认群（社区形态）时不再把 `group_id=None` 发往 OneBot，改为记 warning 并丢弃（返回 0）；私有形态回落默认群行为不变。社区版任务 T0.2，spec/plan 见 `docs/superpowers/`
```

`kb/QUICK_REFERENCE.md` 配置键表 `default_group` 行说明末尾追加"；无群上下文的群发丢弃（社区形态）"。

```bash
git add core/api.py test/test_api_send_fallback.py CHANGELOG.md kb/QUICK_REFERENCE.md
git commit -m "fix(发送): 无默认群部署丢弃群发并告警"
```

---

## Self-Review 结论

- **Spec 覆盖**：P1（丢弃+告警+0）→ Step 1/3；P2（助手收敛）→ Step 3；P3（私有零变化）→ Step 1 第二用例 + Step 4 全量；P4（无 edition 判断）→ Step 3 代码；P5（FakeWS）→ Step 1；文档（§③）→ Step 5。
- **占位符扫描**：无 TBD/待补；测试与实现代码完整。
- **类型一致性**：`_group_target() -> int | None` 与三处消费（`None → return 0`）及 spec §① 一致；FakeWS 回注 `message_id=42` 与断言 42 一致。
