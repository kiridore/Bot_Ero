# web-navigation Specification

## Purpose
定义站点顶部导航与主页网格如何暴露各功能分区，避免同一功能在顶层出现多个入口。

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
