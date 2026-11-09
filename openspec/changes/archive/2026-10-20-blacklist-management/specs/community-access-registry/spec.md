## MODIFIED Requirements

### Requirement: 黑名单按范围记录且可解除
系统 SHALL 以blacklist(scope,target_id,reason,created_at,operator_id)记录拉黑，scope取值user或group，(scope,target_id)唯一；重复拉黑同一目标 SHALL 幂等且保留原原因、操作者及时间；解除 SHALL 删除该行；查询接口 SHALL 区分user与group。新管理操作 SHALL 保存实际操作者，旧接口可兼容可空操作者。旧表增加operator_id时 SHALL 保留全部旧行，未知操作者以NULL表示，不伪造。空表 MUST NOT 对任何行为产生影响。

#### Scenario: 拉黑后解除
- **WHEN** 拉黑用户 A 后解除用户 A
- **THEN** 查询 A 不再命中黑名单，群范围查询不受影响

#### Scenario: 旧记录迁移
- **WHEN** 升级不含operator_id的旧黑名单表
- **THEN** scope、目标、原因和原时间保持，操作者为空；迁移可重复执行，失败不丢失旧记录

#### Scenario: 重复添加保留首次事实
- **WHEN** 不同超管先后添加同一scope与target_id
- **THEN** 只保留首次原因、时间及操作者，第二次返回已存在
