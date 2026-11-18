# web-navigation Specification

## Purpose
定义站点顶部导航与主页网格如何暴露各功能分区，避免同一功能在顶层出现多个入口；导航数据经认证 API `GET /api/nav` 提供给各端客户端（web 前端、移动端 App、PC 端 App）。

## Requirements

### Requirement: 分区的顶层入口唯一
每个功能分区 SHALL 在顶部导航与主页网格中各只有一个入口。跑团分区 MUST 只有一个顶层入口 `/trpg`；跑团记录 SHALL 作为该分区内的页签（`/trpg/records`）出现，MUST NOT 在顶部导航重复列出。访问分区内的子路径时，顶部导航 SHALL 高亮该分区的入口，且同时只有一个高亮项。

#### Scenario: 顶部导航
- **WHEN** 用户打开任意页面
- **THEN** 顶部导航中「跑团」指向 `/trpg`，不存在「跑团记录」项

#### Scenario: 记录页高亮
- **WHEN** 用户访问 `/trpg/records`
- **THEN** 顶部「跑团」为高亮项，页内「跑团记录」页签为选中态

#### Scenario: 主页网格
- **WHEN** 用户查看主页功能网格
- **THEN** 只有一张「跑团」卡，描述包含车卡与跑团记录，点击进入 `/trpg`

### Requirement: 导航数据经认证 API 提供
导航数据 SHALL 由 `GET /api/nav` 提供，响应为既有 `entries.json` 的原样结构，处于全站登录门控之内；非 API 命名的 `/entries.json` 路由 MUST 移除，web 前端消费方 SHALL 全部迁移至 `/api/nav`。

#### Scenario: 登录获取导航
- **WHEN** 携带有效凭证请求 `GET /api/nav`
- **THEN** 返回 entries.json 原样结构，各端客户端以同一契约渲染导航与主页网格

#### Scenario: 数据文件缺失
- **WHEN** `entries.json` 文件不存在时请求 `GET /api/nav`
- **THEN** 返回 404 与 `{"detail"}` 错误体

#### Scenario: 旧路由移除
- **WHEN** 请求 `/entries.json`
- **THEN** 404（登录门控下），仓库内无任何对该路径的引用
