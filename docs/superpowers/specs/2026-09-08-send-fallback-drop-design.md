# 发送兜底适配（T0.2）— 设计文档

- 日期：2026-09-08
- 状态：依据总计划 `docs/community/development-plan.md` §T0.2 与既有决策（D4/D5/D6）设计，未引入新待决项
- 前序：`2026-09-08-config-edition-split-design.md`（T0.1，已交付：`DEFAULT_GROUP_ID` 社区形态可为 `None`）
- 后续：writing-plans 生成实施计划 `docs/superpowers/plans/2026-09-08-send-fallback-drop.md`

## 背景与决策

T0.1 后社区形态（纯 bot、无默认群）`DEFAULT_GROUP_ID` 为 `None`，但 `core/api.py` 三处群发兜底（`send_group_msg:98`、`send_group_forward_msg:170`、`send_group_forward_nodes:190`）仍把 `None` 塞进 `group_id` 参数发 WS——OneBot 端报错，发送语义含混。本任务：无默认群时**丢弃 + 告警**，私有形态回落默认群行为不变。

| # | 决策 |
|---|------|
| P1 | 兜底语义分层：**上下文群号 → 默认群 → None 即丢弃**（`logger.warning` + 返回 0，与既有"失败返回 0"同型：`send_group_msg` 失败返回 0，两个群转发失败返回 0） |
| P2 | 三处逐字重复的兜底收敛为私有助手 `ApiWrapper._group_target() -> int \| None`（消重复优先于三处各贴 4 行） |
| P3 | 私有形态零行为变化：private 必填 `default_group`（T0.1 必填分侧），`DEFAULT_GROUP_ID` 恒 int，回落路径与现状逐字节等价 |
| P4 | 本任务**不含任何 `if EDITION` 判断**——api.py 只对 `None` 值防御，形态差异由配置接缝（T0.1）承担，符合接缝白名单 |
| P5 | 测试不建真实 WS：`FakeWS.send` 记录帧并同步回注 `api.echo.match` 响应解除 `call_api` 30s 队列阻塞；断言帧列表与返回值契约，不绑定日志文本（日志仅 assertLogs 确认存在） |

## 非目标

- 不动 `send_msg`/`send_forward_msg` 的路由顺序；`send_forward_msg` 无上下文时走私聊（`user_id=None`）是两形态同状的既有边缘，另行处理
- 不动 echo 机制与 30s 超时；不改私聊发送路径
- 不处理 `group_id=0` 语义（事件层不存在 0 群号；`if gid` 真值判断与旧 `if not group_id` 等价）

## ① 助手契约

```python
def _group_target(self) -> int | None:
    """群发目标：上下文群号优先，回落默认群；社区形态无默认群返回 None（调用方丢弃计 0）。"""
```

三个群发方法统一改为：`group_id = self._group_target()`，`None` 即 `return 0`。

## ② 测试（`test/test_api_send_fallback.py`，新增）

- 社区形态（`DEFAULT_GROUP_ID=None`）：三个群发方法零 WS 帧、返回 0、发 warning（assertLogs）
- 私有形态（`=12345`）：`send_group_msg` 回落默认群，帧内 `group_id=12345`、返回 FakeWS 回注的 message_id

## ③ 文档与版本（同 commit）

- CHANGELOG `[未发布]`（不 bump）；`kb/QUICK_REFERENCE.md` `default_group` 行说明补"无群上下文的群发丢弃"
- `config.example.yaml` 的 `default_group` 注释在 T0.1 已写"将被丢弃——见 api.py 兜底"，本任务后自洽，无需再改
