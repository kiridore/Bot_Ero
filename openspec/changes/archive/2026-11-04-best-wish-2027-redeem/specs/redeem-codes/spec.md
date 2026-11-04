# redeem-codes 变更（delta）

## RENAMED Requirements

- FROM: `### Requirement: QQ 指令移除`
- TO: `### Requirement: QQ 指令迁移提示桩`

## MODIFIED Requirements

### Requirement: 网页兑换入口
个人主页 SHALL 提供「兑换码」tab：输入框、兑换按钮与行内结果反馈；输入大小写不敏感，服务端按 `XXXX-XXXX-XXXX`（每段为大写字母或数字）格式校验，格式或未知码 MUST NOT 产生数据库写入。

#### Scenario: 登录用户兑换有效码
- **WHEN** 登录用户在 tab 中输入有效兑换码提交
- **THEN** 奖励即时到账，页面展示含奖励说明的成功反馈

#### Scenario: 兑换码含数字段
- **WHEN** 用户提交形如 `BEST-WISH-2027` 的含数字段兑换码
- **THEN** 通过格式校验并按注册表判定有效或未知，不以格式错误拒绝

#### Scenario: 未登录访问
- **WHEN** 未携带登录凭证调用兑换 API
- **THEN** 沿用全站登录门控返回 401，不执行任何兑换逻辑

### Requirement: QQ 指令迁移提示桩
`/兑换码`、`/兌換碼` 指令 SHALL 由提示桩插件处理：撤回触发消息（尽力而为，`delete_msg`），并回复固定迁移提示引导至网页个人主页「兑换码」页签；撤回失败（无群管理员权限、私聊等）MUST NOT 阻止提示发送。提示桩 MUST NOT 读写数据库、MUST NOT 执行任何兑换逻辑。菜单文本保持指向网页个人主页。

#### Scenario: 群内发送旧指令
- **WHEN** 用户在群聊发送 `/兑换码 BEST-WISH-2027`
- **THEN** 机器人撤回该消息，并回复迁移提示，不执行兑换

#### Scenario: 撤回失败
- **WHEN** 机器人无群管理员权限或消息在私聊中，`delete_msg` 失败
- **THEN** 仍发送迁移提示，不重试撤回、不报错
