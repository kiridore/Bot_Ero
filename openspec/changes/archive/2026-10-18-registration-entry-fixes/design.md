# Design

## 现状与根因

main.plugin_pool按runtime_context.plugin_key(plugin_cls)选择执行插件；该函数从模块名取目录标识。MenuPlugin所在plugins.menu返回menu，而类name为show_menu。注册允许列表与部分测试沿用了类name，导致入口跳过菜单；菜单内部handle已有未注册专用显示，不能代替入口放行。

公开模板配置了auto_friend、register，但没有welcome。三者全量导入不等于都能运行：只有列入部署允许名单并在相应上下文启用才会执行。新好友没有账号设置，因此welcome需同时进入公开模板系统集合。

## 实施发现：好友申请被误当作私聊消息限制

真实入口测试在修正菜单标识与welcome模板后，welcome_flow仍失败：auto_friend未收到请求。resolve_event_type对request沿用message分类，注册检查仅看此分类因而限制到register/menu。修复仅在main调用注册检查时增加post_type=message条件，不重分类其他插件的事件，也不扩大未注册消息允许集合。测试同时编译真实resolve_event_type和plugin_pool，避免人为把请求传成request掩盖缺陷。

## 最小实现

1. REGISTRATION_ALLOWLIST改用register/menu；保留plugin_key及MenuPlugin.name，避免无必要改名或修改已存插件设置。
2. 修正plugins/menu中将show_menu称作“插件键”的注释，不改变菜单正文与过滤方式。测试必须断言实际plugin_key(MenuPlugin)处于允许集合，而不是只比较另一份字符串集合。
3. config.public.example.yaml中allowed_plugins与system_plugins各加入welcome。继续使用现有welcome.friend_add和内置回退，不让register监听好友通知，不让auto_friend兼做欢迎。
4. test_plugin_query_scope当前将menu显示为账号未注册的断言随修复更新；其只读状态逻辑继续复用允许集合，不另设例外。
5. 公开模板SYSTEM/ALLOWED期望集合更新；知识库与操作说明标注既有实例须人工将welcome加入两份配置并重启，不写升级时自动修改配置代码。

## 测试设计

新增test/test_registration_entry.py，用临时配置和实际事件分发函数运行真实插件；外部API全部mock，测试中不得建立真实WebSocket或启动监控面板。优先复用已有main入口测试的加载方法，但保留真实plugin_key、开关快照与注册判断，不通过假allowlist掩盖根因。

- 普通未注册用户使用与超管不同的账号；人为预先开启checkin，以证明拒绝来自注册要求而不是插件恰好关闭。
- /菜单、/菜單均从入口到菜单发送，验证只含必要条目、不产生注册提醒或业务写入。
- 比较查询前后user_accounts及user_plugin_config；注册会话状态与协议凭证不得被欢迎或菜单创建。
- 公开模板在独立子进程或等效严格隔离环境下加载：用test/scripts/_env.py生成临时配置，覆盖所有派生DB/媒体路径，在导入插件前断言关键路径在临时目录，不复制模板的data.db相对路径直接在项目根运行。
- 一次request_type=friend后检查只发生同意；一次notice_type=friend_add后检查只一条欢迎并匹配文案包。之后用户主动/注册才输出协议步骤，time.sleep可mock，不能跳过实际注册状态判断。
- require关闭、已注册和超管保持行为；群消息仍按群审核与群开关，不因私聊修复放宽。部署禁止menu/welcome时依然无对应输出。

事件样本涉及OneBot字段，实施前按specs/onebot-protocol.md核对权威好友请求及好友添加通知文档并记录来源，不修改接口协议。

## 不处理的事项

不做全部文本外置、不做黑名单/频控、不改变名单冲突校验、不做welcome重复通知去重。未发送成功的重试语义保持原有行为。新配置范例是部署操作说明，不表示已在现有实例生效。

## 交付

同步开发清单R1/R2状态时必须附测试证据；当前其他未提交的文档整理保留，不混成此次已实现内容。验收完成更新patch版本、CHANGELOG、相关文档，临时副本验证归档后正式归档。未经用户要求不推送。
