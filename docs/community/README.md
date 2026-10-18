# 社区版文档入口

当前代码基线1.54.2。社区与私有部署共用实现，仅实际配置不同；首版只开放打卡基础与积分系统，不开放经济扩展。

## 当前有效文档

| 顺序 | 文档 | 用途 |
|---|---|---|
| 1 | [需求与开放范围](community-edition-plan.md) | 已确认规则、首版包含/排除内容、各阶段目的 |
| 2 | [开发与完成清单](development-plan.md) | 已交付证据、尚未完成项、逐项原因及验收条件 |
| 3 | [计划一致性核对表](config-only-plan-review.md) | 防止重新引入被取代设计，不是另一套待办清单 |
| 上线 | [逐步开放操作](rollout-operations.md) | 群/账号设置与公共默认查询、模板使用 |
| 上线 | [注册入口修复配置说明](registration-entry-operations.md) | 既有实例补齐welcome配置与真实QQ检查 |
| 上线 | [群审核操作及恢复](group-review-operations.md) | QQ审批、未知结果与故障处理 |
| 每批必读 | [维护者可持续性守则](sustainability.md) | 季度功能节奏、维护成本与上线检查 |

**状态边界**：注册与审核主体、查询修复已交付；注册入口和欢迎模板已于1.54.2修复；防滥用、公开补卡权限、固定版本升级及真实QQ验收仍见开发清单，不把候选配置等同于正式可上线。

## 历史背景（非实施依据）

- [旧架构分析](../archive/community-background/architecture-overview.md)：原始耦合证据，包含已失效事实。
- [旧市场构想](../archive/community-background/market-expansion-plan.md)：产品背景，不能据此扩大首版或放开管理权限。
- [OpenSpec归档](../../openspec/changes/archive/)：保留当时决策及验收；当前行为以正式规范、实际代码和上述需求为准。

被取代的方案已从活跃计划移除，不再采用“正文保留旧实现、页首说明勿用”的方式维护。
