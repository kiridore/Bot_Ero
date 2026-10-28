# timeline-feed-preference Specification

## Purpose

用户可以选择不在网站时间线看到他人的打卡事件；自己的打卡与他人非打卡事件不受影响。三个时间线接口行为一致。

## ADDED Requirements

### Requirement: 他人打卡显示开关

系统 SHALL 提供个人设置 `timeline.show_others_checkin`（布尔，缺省 True）。缺省或 True 时时间线行为与本变更前完全一致。

#### Scenario: 缺省显示

- **WHEN** 用户未设置 `timeline.show_others_checkin`
- **THEN** 时间线 feed/poll/new 返回内容与未引入本设置时完全一致

#### Scenario: 偏好局部保存与严格布尔校验

- **WHEN** 设置 API 收到 timeline.show_others_checkin 更新
- **THEN** 只接受布尔值，非法类型返回422；合法值深合并保存，刷新后保持，不覆盖身份与水印设置

### Requirement: 关闭后滤除他人打卡

关闭时，三个时间线接口（feed、poll、new）SHALL 一致滤除"事件来源为打卡且作者不是查看者"的事件：feed 不返回、poll 未读计数不计入、new 不返回且续读游标跨过被滤事件（不造成后续事件丢失）。

#### Scenario: feed 过滤与游标

- **WHEN** 关闭用户翻页浏览时间线，某页含他人打卡事件
- **THEN** 该事件不出现在返回中；后续页游标正确跨过被滤事件，非打卡事件不丢失

#### Scenario: 补页上限后的空页续读

- **WHEN** 连续被滤事件超过服务端5页补取上限，feed 返回空 events 但仍有 cursor
- **THEN** 网站自动继续请求后续页，直到出现可见事件或游标取尽，不能把空页误判为已经到底

#### Scenario: poll 与 new 一致

- **WHEN** 关闭用户有新的他人打卡事件
- **THEN** poll 计数不包含它们；new 不返回它们；两者的可见集合与 feed 一致

### Requirement: 叠加边界

本过滤 SHALL 只收窄可见集合：自己的打卡事件（含作者隐私设置为仅自见的）始终保留；他人打卡事件若经作者隐私设置（hidden）本就对查看者隐藏，叠加本设置后依旧隐藏；他人非打卡事件不受影响。

#### Scenario: 自见打卡保留

- **WHEN** 关闭显示他人打卡的用户存在自己的打卡事件（含自己设置为隐藏、仅自见的那类）
- **THEN** 这些事件仍出现在该用户的时间线中

#### Scenario: 他人非打卡不受影响

- **WHEN** 关闭显示他人打卡的用户的时间线存在他人论坛、相册、活动等非打卡事件
- **THEN** 这些事件照常显示，可见性与未读计数不受本设置影响

### Requirement: bot 侧不适用

本设置 SHALL 仅作用于网站时间线接口；bot 群指令输出的公共内容不做按人过滤。

#### Scenario: 群指令不变

- **WHEN** 关闭用户在群内触发 /排名、/本周打卡图 等 bot 指令
- **THEN** 输出与本变更前一致
