# coc-character-sheet — 变更（点数超预算的卡）

## ADDED Requirements

### Requirement: 点数超预算不阻止保存
职业点或兴趣点超过预算、或未选职业却分配了职业点时，保存 MUST 成功，响应 MUST 通过 `illegal` 字段给出原因。结构性错误（属性范围、信用评级区间、非本职技能加点、可选池越界、武器/物品/资产/年龄一致性）仍 MUST 阻止保存。

#### Scenario: 职业点超支
- **WHEN** 玩家提交一张职业点 500/200 的卡
- **THEN** 保存成功，响应 `illegal` 含「职业点超出预算（500/200）」

### Requirement: 不合法的卡不能当作当前角色
`illegal` 非空的卡 MUST NOT 能被设为当前角色：网页 `activate` 接口、QQ `/跑团 角色 切换`、`/跑团 准备` 与开录校验都 MUST 拒绝并说明原因。

#### Scenario: 网页设为当前
- **WHEN** 对超支卡调用 `POST /api/me/characters/{id}/activate`
- **THEN** 返回 400「这张卡还不能设为当前角色：职业点超出预算…」

#### Scenario: 群里切换
- **WHEN** 玩家发送 `/跑团 角色 切换 <超支卡编号>`
- **THEN** 回执说明还不能设为当前角色及原因，当前卡不变

#### Scenario: 准备
- **WHEN** 当前卡点数超预算时发送 `/跑团 准备`
- **THEN** 拒绝准备，提示到网页修正
