# 验收记录（community-registration，2026-10-10，1.53.0）

| 标准 | 执行 | 结果 |
|---|---|---|
| AC1 | `python -m pytest test/test_register_flow.py -q` | 6 passed：定稿文案逐句（含 `*写写*` 星号与修订后的"完成啦"句）、停顿区间与 5 秒转发后停顿、合并转发协议、大小写不敏感同意、凭证持久化、播种基础包成员、注册完成通知发布；群聊引导；重复 /注册 重发；已注册回执；重启丢会话安全侧 |
| AC2 | `python -m pytest test/test_register_gate.py -q` | 6 passed：require=false 零行为；未注册私聊仅放行 register/show_menu；群/notice/meta/已注册/超级用户不受限；提醒仅对被拦命令且限频；状态读取失败 fail-closed |
| AC3 | `python -m pytest test/test_config_validation.py test/test_deployment_templates.py -q` | 15+8 passed：register 节类型校验；require 开启时协议文件缺失/包名未定义启动退出；公开模板含 register 并通过隔离加载（新群/新账号默认关闭、系统恒开） |
| AC4 | `python -m pytest test/test_enabled_menu.py -q` | 12 passed：/注册 进菜单条目；准入开启时未注册菜单只显示注册与菜单行；/同意EULA 不在菜单 |
| AC5 | `python -m pytest test/test_community_db.py -q` | 11 passed：user_accounts 幂等加列；agree_eula 凭证写入与不可改写 |
| AC6 | `python -m pytest -q` | **623 passed** |
| AC7 | `openspec validate community-registration --strict`；`git -c core.whitespace=cr-at-eol diff --check` | 通过；kb/PLUGIN_CATALOG、QUICK_REFERENCE、specs/plugin-catalog、菜单条目、CHANGELOG、1.53.0 一致；plugin-event-dispatch 迁移清单已补登两个新发送文件（register 直发为例外 Ruling） |

私有部署 require 缺省 false：AC2 首条矩阵专门断言零行为变化。注册资料卡事件外头像获取带降级与异常跳过。
