# 支持字符串格式（CQ 码）消息

## Why

所有者在排查 `.hp 满 @目标` 时指出：QQ 的 @ 是以 **CQ 码**形式出现的，不是 `@QQ号` 文本。

查上游确认：OneBot 11 的 `message` 有两种形态——**消息段数组**（LLOneBot 默认）与**字符串格式**（整条消息是一个 CQ 字符串，`[CQ:at,qq=123]` 混在文本里，见 botuniverse/onebot-11 `message/string.md`；AtSegment 结构为 `{type:"at", data:{qq, name}}`）。如果后端把 `messagePostFormat` 配成 `string`，我们所有插件都假设 `message` 是列表、每段是 dict，会直接崩或读不到 @。

上一版加的「文本 `@QQ号` 兜底」是治错了地方——真实的 @ 是 `[CQ:at,qq=...]`。

## What Changes

- `core/cq.py` 新增 `parse(message)`：把字符串格式解析成消息段列表（识别 `[CQ:type,k=v,...]`，按上游规则反转义 `&amp; / &#91; / &#93; / &#44;`），数组原样返回。
- `core/event.py::message` 统一归一化：`message` 是字符串时走 `cq.parse()`，是列表时原样返回。所有插件因此无需改动即可同时支持两种格式。
- `specs/onebot-protocol.md` 补一节说明两种消息格式与归一化入口，并注明上游链接。

## Capabilities

### New Capabilities

- `onebot-message`：入站消息格式的归一化。

## Scope and Compatibility

- 对数组格式（现网默认）行为零变化：`cq.parse` 对 list 原样返回。
- 字符串格式下所有依赖消息段的插件（骰子、跑团记录、数值、菜单、撤回等）一次性获得支持。
- 文本 `@QQ号` 兜底保留：它不影响 CQ 解析，且能覆盖把 @ 打成纯文本的客户端。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 解析 | `python -m pytest test/test_cq_parse.py -q` | 纯文本、单个 at、文本+at、多段、转义（`&#91;`/`&amp;`）、参数内逗号、数组原样、空值全部符合预期 |
| AC02 事件归一 | 同上 | `Event({"message": "…[CQ:at,qq=100]"})` 的 `.message` 是 `[text, at]`；数组形态原样 |
| AC03 落地效果 | `python -m pytest test/test_trpg_vitals.py -q -k CqStringMessage` | 字符串格式的 `.hp 满 [CQ:at,qq=…]` 作用在目标身上 |
| AC04 文档与归档 | `python -m pytest -q`；`openspec validate onebot-message --strict` | 全量回归绿；`CHANGELOG [1.82.3]` 与 `BOTERO_VERSION` 一致；归档与实现同一 commit |
