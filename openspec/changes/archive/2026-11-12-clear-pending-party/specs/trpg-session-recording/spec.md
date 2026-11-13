# trpg-session-recording — 变更（准备中残留清理）

## ADDED Requirements

### Requirement: 群解散时清理准备中的记录
心跳 SHALL 检查存在 `pending.json` 的群；当 `get_group_list` 调用成功且返回列表不含该群时，MUST 删除该群的 `pending.json`。接口调用失败时 MUST 保持原状。即使没有任何进行中的录制，只要存在准备中的记录，心跳 SHALL 拉取群列表。

#### Scenario: 群解散
- **WHEN** 某群只做了准备（有 pending.json）就解散，心跳拿到群列表且其中没有该群
- **THEN** 该群 `pending.json` 被删除，网页不再显示「准备中」

#### Scenario: 接口失败
- **WHEN** 心跳拿不到群列表（接口失败）
- **THEN** 不做任何清理

#### Scenario: 群仍在
- **WHEN** 群列表里仍有该群
- **THEN** 准备状态保留
