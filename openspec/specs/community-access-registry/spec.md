# community-access-registry Specification

## Purpose
记录公开实例的准入事实：谁已注册、哪个群已批准接入、哪个加群申请待处理、谁被拉黑。为后续注册插件、群审核、事件入口检查提供唯一数据来源；数据层自身不产生任何行为。

## Requirements

### Requirement: 注册账号记录唯一且幂等
系统 SHALL 以 `user_accounts(user_id PRIMARY KEY, created_at)` 记录已注册账号；重复注册同一账号 MUST NOT 产生第二行，也 MUST NOT 更新首次注册时间。

#### Scenario: 重复注册
- **WHEN** 同一 user_id 第二次执行注册写入
- **THEN** 表中仍只有一行，created_at 保持首次值，操作不报错

### Requirement: 群登记状态与移出保留
系统 SHALL 以 `group_registry(group_id PRIMARY KEY, name, invited_by, approved_at, status)` 记录已批准群，`status` 取值 active 或 removed。激活同一群 MUST 幂等（不重复插入、不改首次批准时间）；机器人被移出群 SHALL 仅将 status 置为 removed 并保留全部字段；查询"群是否激活"只认可 active；遍历激活群 MUST NOT 包含 removed。

#### Scenario: 激活后移出再重新批准
- **WHEN** 群激活→标记移出→再次激活
- **THEN** 状态回到 active，approved_at 与审核历史不被清除

### Requirement: 加群申请队列完整且终态不可逆
系统 SHALL 以 `group_requests(group_id, user_id, flag, sub_type, status, created_at)` 保存每次加群申请及其 OneBot 凭证；status 取值 pending、approved、rejected。同一凭证重复入队 MUST 去重；裁决 SHALL 只把 pending 改为 approved 或 rejected，终态申请 MUST NOT 再次变更；待审列表只返回 pending。

#### Scenario: 同一凭证重复到达
- **WHEN** 相同 flag 的加群申请事件重复出现
- **THEN** 队列中只有一条 pending 记录

#### Scenario: 裁决终态
- **WHEN** 对已 rejected 的申请再次执行通过
- **THEN** 状态不变、返回失败，不产生群激活副作用

### Requirement: 黑名单按范围记录且可解除
系统 SHALL 以 `blacklist(scope, target_id, reason, created_at)` 记录拉黑，scope 取值 user 或 group，(scope, target_id) 唯一；重复拉黑同一目标幂等；解除 SHALL 删除该行；查询接口 SHALL 区分 user 与 group 两个范围。空表 MUST NOT 对任何行为产生影响。

#### Scenario: 拉黑后解除
- **WHEN** 拉黑用户 A 后解除用户 A
- **THEN** 查询 A 不再命中黑名单，群范围查询不受影响

### Requirement: 四表与部署无关地随启动创建
四张表 SHALL 在所有部署的启动建表流程中幂等创建（CREATE TABLE IF NOT EXISTS）；不按部署标签建表或跳过建表；既有数据库升级仅新增空表，既有功能零变化。

#### Scenario: 私有部署升级
- **WHEN** 现有私有 data.db 升级到含本表的版本
- **THEN** 启动成功，新增 4 张空表，全部既有测试与行为不变
