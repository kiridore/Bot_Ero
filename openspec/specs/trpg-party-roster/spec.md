# trpg-party-roster Specification

## Purpose
开团前（`.dm` 已设置、尚未开录）的准备名单需要在网页可见，并允许本群 DM 审核参与者的角色卡。

## Requirements

### Requirement: 准备中名单
系统 SHALL 在 `/trpg/records` 顶部列出当前处于准备中的群（存在 `pending.json` 且含 DM）。每个群 SHALL 展示群号、本团规则、DM、已准备计数与成员列表；成员 MUST 包含 DM、观察者与已准备玩家，逐行显示昵称、身份徽标、角色卡名与查看入口，未准备者显示「等待准备」。列表对所有登录用户可见；当前登录者为该群 DM（或超级用户）时 SHALL 额外显示审核提示。

#### Scenario: 有 DM 且有人准备
- **WHEN** 群内有 DM、一名玩家已 `/跑团 准备`
- **THEN** 记录页顶部出现该群，显示「已准备 1/2」与两行成员，已准备者带「查看角色卡」按钮

#### Scenario: 没有 DM
- **WHEN** 群内没有任何人设置 `.dm`
- **THEN** 该群不出现在准备中列表

#### Scenario: 非参与者查看
- **WHEN** 未参与该团的登录用户打开记录页
- **THEN** 能看到名单，但没有 DM 审核提示

### Requirement: 准备名单内的角色卡权限
准备名单内的角色卡 SHALL 通过 `/api/trpg/party/<群号>/card/<用户>` 获取：本人 MUST 可看；该群 DM 与超级用户 MUST 可看且不受对方隐私设置限制；其他登录用户必须满足对方 `privacy.char_public`。用户不在名单内或该群没有准备时 MUST 返回 404。

#### Scenario: DM 审核私密卡
- **WHEN** 玩家把角色卡设为不公开，本群 DM 点击其「查看角色卡」
- **THEN** 正常显示完整角色卡

#### Scenario: 旁观者被拒
- **WHEN** 非参与者的登录用户尝试打开某成员的私密卡
- **THEN** 返回 403「对方未公开角色卡」

#### Scenario: 名单外用户
- **WHEN** 请求的 user_id 不在该群准备名单里
- **THEN** 返回 404

### Requirement: 身份口径与审核提示
列表接口 SHALL 分别下发 `is_dm`（登录用户是否为本群 DM）、`is_super`（是否为超级用户）与 `can_audit`（两者之一）。页面 MUST 依据 `is_dm` 显示「你是本群 DM」、依据 `is_super` 显示「你是超级用户」，普通登录用户 MUST NOT 看到审核提示。角色卡审核接口的权限判定 MUST 与 `can_audit` 一致。

#### Scenario: 本群 DM
- **WHEN** 本群 DM 打开记录页
- **THEN** 卡片显示「你是本群 DM，可点开每张角色卡审核」

#### Scenario: 超级用户非本群 DM
- **WHEN** 超级用户打开记录页，而本群 DM 是别人
- **THEN** 卡片显示「你是超级用户，可点开每张角色卡审核」，不出现「你是本群 DM」

#### Scenario: 普通登录用户
- **WHEN** 既不是 DM 也不是超级用户的登录用户打开记录页
- **THEN** 卡片不显示任何审核提示

### Requirement: 成员行可点击
已准备成员的整行 SHALL 可点击进入角色卡（`/trpg/char/<用户>/<编号>?party=<群号>`），并保留「查看角色卡」视觉提示；未准备成员 SHALL 以「等待准备」文本呈现，MUST NOT 渲染为链接。

#### Scenario: 点击成员名字
- **WHEN** 用户点击已准备成员的名字或角色名
- **THEN** 进入该角色卡页面

#### Scenario: 未准备成员
- **WHEN** 成员尚未准备
- **THEN** 该行显示「等待准备」，不可点击

### Requirement: 群名片变更实时刷新昵称
收到 OneBot `group_card` 通知时，系统 SHALL 把 `card_new` 写入该群 `pending.json` 的 `role_names`，但 MUST 仅在该用户已有 DM 或观察者标记时写盘；`card_new` 为空或与该用户当前昵称相同时 MUST NOT 写盘。其它 notice 类型 MUST NOT 触发本逻辑。

#### Scenario: DM 改名片
- **WHEN** DM 在本群修改群名片
- **THEN** `pending.json.role_names[DM]` 更新为新名片，网页准备名单显示新名字

#### Scenario: 普通成员改名片
- **WHEN** 没有 DM/观察者标记的成员修改群名片
- **THEN** 不写入任何文件

#### Scenario: 空名片
- **WHEN** 通知里 `card_new` 为空
- **THEN** 保留原有昵称

### Requirement: 无名片时回落昵称
记录 DM/观察者昵称时 SHALL 优先使用群名片，名片为空时使用 QQ 昵称。收到 `group_card` 通知且 `card_new` 为空（用户取消了群名片）时，系统 SHALL 按群查询一次成员显示名并写入 `role_names`；查询失败或返回空时 MUST 保留原昵称。昵称与 QQ 号都取不到时，可回落 `用户<QQ号>`。

#### Scenario: DM 取消群名片
- **WHEN** DM 取消群名片，机器人收到 `card_new` 为空的 `group_card` 通知，且能查到 QQ 昵称
- **THEN** 准备名单显示 QQ 昵称，而不是已取消的旧名片

#### Scenario: 查不到昵称
- **WHEN** 取消名片后接口不可用
- **THEN** 保留原昵称，不影响其它流程

#### Scenario: 从未设置名片就发 .dm
- **WHEN** 没有群名片的成员发送 `.dm`
- **THEN** 记录其 QQ 昵称

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

### Requirement: 角色卡描述按规则生成
准备名单中角色名后的括号 SHALL 按角色卡规则选择字段：`coc7th` 显示「职业 · 年龄」，`dnd5e` 显示「种族 职业 Lv.等级」。字段缺失时 MUST 省略或给出明确占位，MUST NOT 输出连续问号；DND 卡三项均为空且等级为 1 时 MUST NOT 显示括号。旧快照缺少规则字段时 SHALL 按 `dnd5e` 处理。

#### Scenario: 调查员卡
- **WHEN** 准备的是 COC 卡（药剂师，28 岁）
- **THEN** 名单显示「桐島 英二（药剂师 · 28岁）」

#### Scenario: 调查员卡没填职业
- **WHEN** 卡的职业为空
- **THEN** 显示「（无职业）」

#### Scenario: DND 卡
- **WHEN** 准备的是 3 级人类战士
- **THEN** 显示「（人类 战士 Lv.3）」

#### Scenario: 旧快照
- **WHEN** `pending.json` 里的快照是 1.63 之前的格式（无 rules、无种族职业）
- **THEN** 只显示角色名，不出现「? ? Lv.1」

### Requirement: 旧准备快照的括号展示
准备名单 SHALL 按快照渲染「用户 → 角色名（括号）」。当快照缺少 `rules` 字段时，系统 MUST 用该成员当前角色卡（优先 `char_id`，回落当前卡）补齐 `rules`、`race`、`class_name`、`level`、`occupation`、`age` 后再渲染；取不到角色卡时 MUST 只显示角色名，MUST NOT 报错。快照本身 MUST NOT 被改写。

#### Scenario: 旧快照 + COC 卡
- **WHEN** 名单里有 1.81.1 之前准备的快照，其成员当前卡是 COC 调查员（职业「酒保」、27 岁）
- **THEN** 名单显示 `桐島 英二（酒保 · 27岁）`

#### Scenario: 旧快照 + DND 卡
- **WHEN** 该快照成员当前卡是 DND 5E（人类 战士 3 级）
- **THEN** 名单显示 `（人类 战士 Lv.3）`

#### Scenario: 角色卡已删除
- **WHEN** 快照对应的角色卡已被删除
- **THEN** 名单只显示角色名，没有括号，也不报错

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

### Requirement: 准备卡片的 DM / 观察者行不显示角色卡名
准备中的跑团卡片里，成员 `role` 为 `dm` 或 `ob` 时 MUST 只显示群昵称与角色徽标，MUST NOT 渲染角色卡名称，也 MUST NOT 显示「未选角色卡」占位。玩家成员保持昵称 + 角色卡名（未选时显示「未选角色卡」）。

#### Scenario: 观察者成员
- **WHEN** 准备卡片列出观察者
- **THEN** 该行显示「围观 [观察者]」，没有角色卡名称，也没有「未选角色卡」

#### Scenario: 玩家成员
- **WHEN** 玩家已准备并绑定角色卡
- **THEN** 该行仍显示角色卡名并可点开

### Requirement: 准备中的卡片列出群里所有成员
`/api/trpg/parties` 返回的准备中名单 SHALL 包含该群全部真人成员（排除 `is_robot`），顺序为 DM → 观察者 → 已准备者（按准备时间）→ 其余按昵称。群成员接口不可用时 SHALL 退回 `pending.json` 中出现的 DM、观察者与已准备者。`member_count` SHALL 等于名单人数，`prepared_count` SHALL 只统计名单内已准备者。

#### Scenario: 群里有没准备的人
- **WHEN** 群里有 3 名真人与 1 个机器人，其中 1 人已准备
- **THEN** 名单 3 人（不含机器人），`prepared_count` 为 1

#### Scenario: 成员接口不可用
- **WHEN** OneBot 群成员接口返回失败
- **THEN** 名单仍是 DM、观察者与已准备者，页面不报错

### Requirement: 有当前角色卡即可查看
准备中卡片的每个成员 SHALL 解析出可查看的角色卡：已准备者用准备快照的卡，未准备者用其当前角色卡。前端 SHALL 在 `char_id` 存在时把整行做成链接（`/trpg/char/<用户>/<卡号>?party=<群号>`），未准备者额外标「未准备」；没有角色卡的人 MUST NOT 可点，显示「等待准备」。查看权限沿用既有规则：本人、本群 DM、超级用户可看，其他人按对方隐私设置。

#### Scenario: 没准备但设了卡
- **WHEN** 群成员从未 `/跑团 准备`，但网页上已建卡并设为当前
- **THEN** 他在准备中卡片里可点开看自己的卡，DM 也能审核

#### Scenario: 完全没卡
- **WHEN** 群成员还没建角色卡
- **THEN** 该行显示「等待准备」，不可点击

### Requirement: DM 与观察者在准备卡片里不挂角色卡
准备中卡片的成员行，`role` 为 `dm` 或 `ob` 时 MUST 只显示群昵称与角色徽标：MUST NOT 显示角色卡名、MUST NOT 提供角色卡链接、MUST NOT 显示「未准备」。`/api/trpg/parties` MUST NOT 为这两类成员下发 `char_id`/`char_name`；`GET /api/trpg/party/<群>/card/<用户>` 命中这类成员时 MUST 返回 404。

#### Scenario: 观察者行
- **WHEN** 观察者名下有角色卡
- **THEN** 准备卡片里该行只有「旁观者 [观察者]」，接口也不下发 `char_id`

#### Scenario: 请求 staff 的角色卡
- **WHEN** 有人调用 `GET /api/trpg/party/<群>/card/<DM 或观察者>`
- **THEN** 返回 404

### Requirement: 没有角色卡的成员不提示「等待准备」
玩家成员没有角色卡时 SHALL 显示「未设置角色卡」并不可点击，MUST NOT 出现「等待准备」字样；有卡但未准备时才显示「未准备」标记。

#### Scenario: DM 行
- **WHEN** DM 自己有角色卡
- **THEN** 准备卡片里该行只有「守密人 [DM]」，没有角色卡名也没有链接

#### Scenario: 没建卡的玩家
- **WHEN** 群成员还没有角色卡
- **THEN** 该行显示「未设置角色卡」，不可点击，也没有「等待准备」

#### Scenario: 有卡未准备
- **WHEN** 玩家建了卡但还没 `/跑团 准备`
- **THEN** 该行可点开查看角色卡，并带「未准备」标记
