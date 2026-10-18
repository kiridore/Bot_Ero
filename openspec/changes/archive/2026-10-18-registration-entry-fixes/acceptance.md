# 验收记录

版本：1.54.2。

## 上游核查

实施前读取LLOneBot权威页面：
- https://api.luckylillia.com/schema-189483968.md ：FriendRequestEvent，post_type=request、request_type=friend、flag/user_id等字段。
- https://api.luckylillia.com/schema-189483970.md ：FriendAddNoticeEvent，post_type=notice、notice_type=friend_add、user_id等字段。

只新增事件样本与入口调用条件，不修改API参数或已有插件的好友协议处理。

## 复现与关联修复

新测试先在旧实现运行：2 failed、3 passed，分别复现未注册菜单不可达与欢迎模板缺失。

修正menu和welcome模板后仍1 failed：真实resolve_event_type将request沿用message调度分类，main的注册限制拦住auto_friend。将注册检查限定post_type=message后5项全部通过。保持全局调度分类不变，不把auto_friend加入未注册消息允许集合。

## 独立验收结果

| 标准 | 结果 |
|---|---|
| AC01 menu_entry | 1 passed（含/菜单与/菜單）；无提前账户/同意/插件覆盖写入 |
| AC02 boundary | 2 passed；未注册预开打卡也拒绝，提醒限频；部署禁止、已注册/超管/require关闭和群消息兼容 |
| AC03 welcome_flow | 2 passed；申请只同意、通知只欢迎、主动注册才开始协议；欢迎禁用不发消息 |
| AC04 指定6个测试文件 | 57 passed |
| AC05 全量pytest | 689 passed |

所有子进程由_env.write_config生成配置，数据库和媒体路径全部改为临时绝对路径；导入插件前断言DB及消息日志DB位于配置目录内。真实plugin_pool及resolve_event_type由源码编译运行；使用真实注册表标识和开关逻辑，网络API mock，未启动WebSocket或控制面板。

## 范围与交付

- 内置欢迎文字、社区文案包、协议正文、停顿、同意发包及资料卡逻辑未改。
- 模板两份名单增加welcome，不强制修改自定义部署配置；已有实例按registration-entry-operations.md补齐并重启。
- 先前社区文档整理仍单独保留，不混入本修复提交；当前工作区中的R1/R2状态同步更新。
- 严格校验通过；临时副本归档验证后正式归档，正式规范合并与实现同提交。

## 未验证与风险

未进行真实QQ联调，仍属M2试运行事项。不实现上游重复好友通知去重，不承诺消息发送失败自动重试。pytest警告仍为既有第三方pytest-asyncio弃用告警，未屏蔽。
