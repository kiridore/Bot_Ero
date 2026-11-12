# plugin-management Specification

## Purpose
定义功能包与插件开关的管理权限：超级用户可管理一切；QQ 群主可在自己所在的群自助开启白名单功能包，用于解决「新群默认全关、必须超管进群」的问题。

## ADDED Requirements

### Requirement: 功能包管理权限
系统 SHALL 区分三种身份：超级用户（可对任意群开启/关闭任意功能包与单个插件）、QQ 群主（`sender.role == "owner"`，只能对**当前群**开启白名单功能包）、其他成员（无管理权限）。群主权限 MUST NOT 覆盖「关闭」操作、单个插件管理、指定其它群号，也 MUST NOT 扩展到 `role == "admin"` 的群管理员。

#### Scenario: 群主开启跑团包
- **WHEN** 群主在群内发送 `/功能包 跑团`
- **THEN** 回复「已开启功能包「跑团」：trpg_dice、trpg_session、trpg_char、trpg_vitals」，并写入本群配置

#### Scenario: 群主开启白名单外的包
- **WHEN** 群主发送 `/功能包 休闲娱乐`
- **THEN** 回复「群主只能开启：基础包、跑团；其余功能包请联系超级用户」，不写入任何配置

#### Scenario: 群主尝试关闭
- **WHEN** 群主发送 `/功能包 跑团 off`
- **THEN** 回复「群主只能开启功能包，关闭请联系超级用户」，配置不变

#### Scenario: 群主指定其他群
- **WHEN** 群主发送 `/功能包 跑团 987654`
- **THEN** 回复「群主只能操作自己所在的群」，不写入配置

#### Scenario: 群管理员不是群主
- **WHEN** `sender.role == "admin"` 的用户发送 `/功能包 跑团`
- **THEN** 回复「仅超级用户可管理插件」

### Requirement: 跑团功能包内容
「跑团」功能包 SHALL 包含 `trpg_dice`、`trpg_session`、`trpg_char`、`trpg_vitals` 四个插件。

#### Scenario: 开启跑团包
- **WHEN** 任一有权限的身份开启「跑团」包
- **THEN** 上述四个插件全部标记为启用
