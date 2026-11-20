# timeline-feed Specification

## Purpose

时间线信息流（`GET /api/timeline`、`GET /api/timeline/new`）向网页与 Flutter 客户端交付统一的事件卡片载荷：事件字段、作者展示身份、未读状态、打卡可见性变换，以及客户端渲染所需的隐私标记。

## ADDED Requirements

### Requirement: 打卡事件携带与查看者无关的 checkin_state

`GET /api/timeline` 与 `GET /api/timeline/new` 返回的每条 `source=checkin` 事件 SHALL 带 `checkin_state` 字段，取值为作者在该类打卡（`data.private=true` 为私聊/网页打卡，否则群聊）上设置的显示状态原值：`show`、`blur`、`text` 或 `hidden`。该值 MUST NOT 随查看者变化：对同一条被下发的事件，作者与其他查看者取到的值完全一致；作者设置读取失败或非法时按 `show` 输出。非 `checkin` 事件 MUST NOT 带该键（无键 ≠ `null`）。该字段为 additive 契约，既有可见性过滤（hidden 对非作者不下发）、图片展示变换（blur 改写 `?blur=1`、text 剥图并附 `images_hidden`）与 `self_only` 标记 MUST NOT 改变。

`checkin_state` SHALL 在 OpenAPI `EventOut` schema 中显式声明为可选字符串（不在 `required`）。该字段会把作者的打卡显示设置暴露给所有能查看该事件的用户；这是既定的产品语义，而非缺陷。

#### Scenario: 作者与非作者看到相同状态

- **WHEN** 作者把群聊打卡设为 `blur`，作者本人与另一位登录用户分别请求 `GET /api/timeline` 且都能看到同一条打卡事件
- **THEN** 两条响应中该事件的 `checkin_state` 均为 `"blur"`，非作者侧的图片 URL 仍带 `blur=1`

#### Scenario: 隐藏态只对作者下发

- **WHEN** 作者把私聊打卡设为 `hidden`，作者本人与另一位登录用户分别请求 `GET /api/timeline` 与 `GET /api/timeline/new`
- **THEN** 作者看到该事件且 `checkin_state` 为 `"hidden"`、`self_only` 为 `true`；另一位用户的响应不含该事件

#### Scenario: 非打卡事件无状态键

- **WHEN** 信息流中包含 `source=forum` 的事件
- **THEN** 该事件响应对象不含 `checkin_state` 键

#### Scenario: 客户端从契约获得字段

- **WHEN** 客户端以 `GET /openapi.json` 的 `EventOut` schema 生成模型
- **THEN** 模型包含可空的 `checkin_state` 字段，且该字段不在 `required` 中
