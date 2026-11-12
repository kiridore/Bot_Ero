# trpg-vitals — 变更（目标与空值）

## ADDED Requirements

### Requirement: @ 目标的三种写法
`.hp` / `.san` / `.mp` / `.sc` SHALL 识别三种目标写法：消息里的 at 段、文本 `.hp 满 @123456789`、文本 `.hp 满@123456789`。文本兜底 MUST 只匹配 5–12 位数字，匹配到的片段 MUST 从数值参数中剔除。

#### Scenario: at 段
- **WHEN** DM 发送 `.hp 满` 并 @ 某成员
- **THEN** 目标的 HP 回满

#### Scenario: 文本 @
- **WHEN** 客户端把 @ 拼进文本（无空格）
- **THEN** 同样作用在目标身上，而不是发送者

### Requirement: 当前值缺省
当前 HP/MP/SAN 为 `null` 或缺失时，指令 SHALL 按默认值结算：HP/MP 取上限，SAN 取初始意志并受 `99−克苏鲁神话` 约束。结算结果 MUST NOT 因空值报错。

#### Scenario: MP 从未初始化
- **WHEN** 卡上 `current_mp` 为 null 时发送 `.mp -3`
- **THEN** 回执「MP 13 → 10」

### Requirement: 未设当前角色卡
用户有多张角色卡但未指定当前卡时，系统 SHALL 提示「还没设置当前角色卡」并给出 `/跑团 角色 列表`、`/跑团 角色 切换 <编号>` 的指引，MUST NOT 提示去网页端新建。

#### Scenario: 有卡未设当前
- **WHEN** DM 自己没有当前角色卡却发送 `.hp 满`
- **THEN** 收到设置当前卡的指引
