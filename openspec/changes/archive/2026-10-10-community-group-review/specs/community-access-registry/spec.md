## MODIFIED Requirements

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
