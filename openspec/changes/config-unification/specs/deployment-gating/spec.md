# deployment-gating · Spec Delta

## ADDED Requirements

### Requirement: 部署级插件全集

每个部署 SHALL 通过 `bot.allowed_plugins` 声明可运行的插件全集：非空列表时仅该集合内插件可产生任何业务（消息处理、内部通知、请求、通知、心跳）；键缺失或空列表时全集等于全部已注册插件。

#### Scenario: 部署禁用的插件全事件失效

- **WHEN** 插件 X 不在 `bot.allowed_plugins` 内
- **THEN** X 对消息/notice/request/meta 事件均不运行，其心跳任务不执行，其他插件对其发出的内部通知不被消费

#### Scenario: 私有缺省零变化

- **WHEN** 配置不含 `bot.allowed_plugins`
- **THEN** 全部已注册插件保持 1.51.0 行为，含心跳插件

### Requirement: meta 事件统一门控

meta 事件 SHALL 与其他事件类型经过同一启用检查；不存在仅 meta 可用的豁免路径。系统插件保护与部署全集冲突时启动 SHALL 失败并报告冲突插件清单，不得静默取舍。

#### Scenario: 心跳受部署开关约束

- **WHEN** ff_news 不在 allowed_plugins 且到达整点
- **THEN** ff_news 不执行抓取与发送

#### Scenario: 冲突配置启动报错

- **WHEN** `bot.system_plugins` 含 message_logger 但 allowed_plugins 不含
- **THEN** 进程启动失败，错误信息列出 message_logger

## MODIFIED Requirements

### Requirement: 系统插件集可配置

系统插件集合 SHALL 由 `bot.system_plugins` 配置决定（替换语义不变）；系统插件身份免除的是群/账号开关检查，不免除部署全集检查。~~meta 事件照常直达全部插件~~ meta 事件同样受部署全集约束。

#### Scenario: 系统插件仍需在部署全集内

- **WHEN** 某插件在 system_plugins 中但被 allowed_plugins 排除
- **THEN** 启动报错（见冲突场景），运行中不存在该插件任何执行

# config-validation · Spec Delta

## ADDED Requirements

### Requirement: 必填校验按实际启用服务判定

配置必填性 SHALL 由实际启用的外部服务决定（timeline/onebot.http 配置了即要求配套键），与部署描述标签（`bot.edition`）的取值无关；`bot.edition` 仅作描述，不参与任何控制流、校验与默认值选择。

#### Scenario: 版名无关

- **WHEN** 同一份有效配置仅修改或删除 `bot.edition` 的值
- **THEN** 校验结果、默认值、功能可用性、权限与事件处理路径完全一致

# feature-packs · Spec Delta

## ADDED Requirements

### Requirement: 功能包定义可由配置文件替换

功能包表 SHALL 支持经 `bot.feature_packs_file` 指定的 yaml 文件整体替换（精确替换语义）；键缺失或空时回落内置缺省表。指令与监控面板展示的数据源唯一。

#### Scenario: 自定义包表生效

- **WHEN** 配置 `bot.feature_packs_file` 指向仅含打卡包的 yaml
- **THEN** `/功能包 列表` 只显示该包定义，内置包不再出现
