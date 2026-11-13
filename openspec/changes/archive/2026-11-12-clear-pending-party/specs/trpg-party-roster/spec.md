# trpg-party-roster — 变更（手动清除）

## ADDED Requirements

### Requirement: 清除准备中的记录
系统 SHALL 提供 `DELETE /api/trpg/party/{group_id}`：本群 DM 或超级用户可删除该群的准备状态（`pending.json`）。非本群 DM 的普通用户 MUST 收到 403；没有准备中的记录 MUST 返回 404。记录列表页的「准备中」卡片在可审核身份（`can_audit`）下 SHALL 显示「清除这条准备」按钮，点击需二次确认。

#### Scenario: DM 清除
- **WHEN** 本群 DM 点击「清除这条准备」并确认
- **THEN** 接口返回 200，卡片从列表移除，`pending.json` 被删除

#### Scenario: 旁观者清除
- **WHEN** 与该群无关的登录用户调用该接口
- **THEN** 返回 403，不影响准备状态

#### Scenario: 重复清除
- **WHEN** 已经没有准备中的记录时再次调用
- **THEN** 返回 404
