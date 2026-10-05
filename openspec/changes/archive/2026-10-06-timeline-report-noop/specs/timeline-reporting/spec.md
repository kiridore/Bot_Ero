# timeline-reporting · Spec Delta

## ADDED Requirements

### Requirement: 时间线上报开关

时间线上报客户端 SHALL 以 `timeline.url` 配置为总开关：留空（节缺失或空串）时上报完全关闭。

#### Scenario: 留空配置下事件上报静默跳过

- **WHEN** `timeline.url` 为空，任一插件触发时间线事件（发送或撤回）
- **THEN** 不产生任何 HTTP 请求、不抛出异常、调用方主流程不被阻塞

#### Scenario: 留空配置下运行无告警噪音

- **WHEN** bot 以不含 `timeline` 节的配置（社区形态）启动并运行既有插件

- **THEN** 配置加载成功（不因缺 `timeline` 节退出），运行期不因上报产生错误日志刷屏

### Requirement: 配置形态下行为保持

`timeline.url` 已配置时，上报行为 SHALL 与既有现状一致：按 `specs/timeline-protocol.md` 协议发送/撤回，失败仅记日志（best-effort），绝不阻塞或中断调用方主流程。

#### Scenario: 私有形态回归零变化

- **WHEN** 私有部署（`timeline.url` 与 `timeline.token` 均有值）执行既有上报路径
- **THEN** 行为与本变更前完全一致
