# trpg-party-roster — 变更（DM 昵称实时查询）

## ADDED Requirements

### Requirement: DM 昵称实时查询
渲染准备名单时，系统 SHALL 按群实时查询 DM 的显示名（名片优先，其次 QQ 昵称），查询结果 MUST 带 TTL 缓存（命中 60 秒、未命中 30 秒）以免重复请求与超时叠加。实时查询失败或返回空时 SHALL 回落 `.dm` 时刻保存的昵称，再回落 QQ 号。事件驱动的 `group_card` 刷新 SHALL 绕过缓存取最新值。

#### Scenario: DM 改名后刷新页面
- **WHEN** DM 修改群名片后打开 `/trpg/records`
- **THEN** 卡片显示新名片（缓存过期后最多 60 秒内更新）

#### Scenario: OneBot 不可用
- **WHEN** `get_group_member_info` 不可达
- **THEN** 页面在 2 秒内回落显示 `.dm` 时的昵称，且 30 秒内不再重试

#### Scenario: 名片为空
- **WHEN** DM 没有群名片
- **THEN** 显示其 QQ 昵称
