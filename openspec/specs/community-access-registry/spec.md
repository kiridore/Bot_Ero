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
系统 SHALL 为group_requests保存独立请求编号id、群/邀请人、真实flag或手动记录标识、kind（invite/manual）、sub_type、created_at、joined事实、decision和remote_state。flag唯一；不同凭证在同秒到达不得丢失。status支持pending、processing、uncertain、approved、rejected，已批准/拒绝的终态不可逆。待处理查询包含pending及需人工确认的processing/uncertain并显示实际状态。旧请求记录及时间 SHALL 原子迁移并完整保留。

#### Scenario: 同一凭证重复到达
- **WHEN** 相同flag的加群申请事件重复出现
- **THEN** 队列只有一条记录，其他不同凭证不受影响

#### Scenario: 裁决终态
- **WHEN** 对已rejected申请再次执行通过
- **THEN** 状态不变，不产生群激活副作用

#### Scenario: 远端成功而本地失败
- **WHEN** 已记录远端ok但本地激活与播种事务失败
- **THEN** 远端结果保留可恢复，本地全部回滚，管理员可继续本地提交而不重复远端审批

#### Scenario: 进程中断
- **WHEN** 已预留审批但远端结果尚未持久化时进程中断
- **THEN** processing及容量预留保留，重启不自动重发审批或当作成功

#### Scenario: 旧数据库迁移
- **WHEN** 升级只有秒级复合主键的旧表
- **THEN** 历史请求、终态、flag和时间保留；迁移失败整体回滚，重新启动可重试

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
