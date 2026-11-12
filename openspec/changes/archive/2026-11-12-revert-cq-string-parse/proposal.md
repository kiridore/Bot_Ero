# 撤销 CQ 码字符串格式支持

## Why

1.82.3（commit ef9aed3）基于「后端把 `message` 配成 CQ 码字符串」的判断实现了 `cq.parse()` 与 `Event.message` 归一化。所有者澄清说错了：实际部署的 LLOneBot 一直下发**消息段数组**，@ 信息以 `{"type":"at","data":{"qq":"100000002"}}` 标准段出现，该路径自 1.69 起就是通的（`TestTargetFormats::test_at_segment` 守护）。字符串格式支持是多余的一层，予以撤销。

## What Changes

- 完整 revert commit ef9aed3：`core/cq.py` 移除 `parse()`，`Event.message` 恢复原样返回，删除 `test_cq_parse.py` 与 `TestCqStringMessage`，移除 `specs/onebot-protocol.md` 的字符串格式说明，删除 `onebot-message` 能力与已归档提案。
- 版本不回退：bump `1.82.4` 并在 CHANGELOG 记录撤销（私有部署按 HEAD 拉取，版本需单调）。
- 1.82.2 的修复（at 段识别、纯文本 `@QQ号` 兜底、null 当前值）全部保留。

## Capabilities

### Removed Capabilities

- `onebot-message`：入站消息只有消息段数组一种形态，无需归一化层。

## Scope and Compatibility

- 现网（数组格式）行为与 1.82.2 完全一致；字符串格式回到「不解析」状态（本来也不会出现）。
- 无数据库变更、无新增依赖。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 撤销完整 | `git diff f326378 HEAD -- core/ plugins/ webapp/` 为空（代码层回到 1.82.2） | 无代码差异 |
| AC02 at 路径仍在 | `python -m pytest test/test_trpg_vitals.py -q` | at 段 / 纯文本 @ / null 值用例全过 |
| AC03 全量回归 | `python -m pytest -q` | 全绿 |
| AC04 文档与归档 | `openspec validate 2026-11-12-revert-cq-string-parse --strict`；归档与实现同一 commit | CHANGELOG `[1.82.4]` 与 `BOTERO_VERSION` 一致 |
