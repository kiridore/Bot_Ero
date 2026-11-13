# trpg-party-roster — 变更（DM/观察者与无卡成员）

## ADDED Requirements

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
