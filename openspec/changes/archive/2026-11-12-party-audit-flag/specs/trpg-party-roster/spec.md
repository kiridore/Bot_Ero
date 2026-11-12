# trpg-party-roster Specification

## Purpose
定义网页「准备中」名单的身份口径与交互：谁能看到什么提示、成员行怎样进入角色卡。

## ADDED Requirements

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
