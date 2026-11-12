# trpg-party-roster Specification

## Purpose
开团前（`.dm` 已设置、尚未开录）的准备名单需要在网页可见，并允许本群 DM 审核参与者的角色卡。

## ADDED Requirements

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
