# config-unification 验收记录（2026-10-08，版本 1.52.0）

## 结论

AC01–AC11 全部通过。25/25 任务完成，提案随实现同 commit 归档。
本提案交付"部署边界 + 群/账号逐步开放 + 心跳遵守开关 + 有效菜单"；注册、群审核、黑名单等运营能力仍属后续计划，不等于公开服务上线验收。

## 逐条执行结果

命令均以 `python -m pytest` 开头、`-q` 结尾；完整日志在 `.git/config-unification-acceptance/`（不入库）。

| 标准 | 测试 | 结果 | 核查要点 |
|---|---|---|---|
| AC01 | test/test_deployment_gating.py | 4 passed | 部署禁止先于 match/handle/内部消费者；cleanup 不能绕过；系统冲突与未知标识启动失败 |
| AC02 | test_plugin_controls.py test_plugin_management.py test_web_panel.py | 38 passed | A群/B群/账号互不影响；覆盖可从默认关变开；管理命令与面板拒绝开启部署禁止项；仅超管可改 |
| AC03 | test/test_scoped_heartbeats.py | 9 passed | 闹钟/活动/仙人彩按所属对象过滤且检查先于状态推进；商店公告/新闻/论坛/周报按目的地；共享维护不受单群影响；部署禁止对心跳生效 |
| AC04 | test/test_heartbeat_pending_tasks.py | 2 passed | 关闭不删记录不动资金；恢复后按原到期规则处理；重复执行防护；已付注单可定位 |
| AC05 | test_config_loader.py test_config_wiring.py test_config_validation.py | 27 passed | 旧配置可加载；版名标签无关；成对服务校验；启动与面板存盘共用校验；错误名单/文件明确失败不扩大范围 |
| AC06 | test/test_feature_packs_config.py | 8 passed | 内置/自定义同一解析；整体替换；相对路径基准；错误即退出；包引用未注册插件报错；改包定义不播种开关 |
| AC07 | test/test_enabled_menu.py | 8 passed | 按群/账号快照过滤；管理员段仅超管；新插件不自动出现；逐条覆盖不改可见性；旧 menu_text 告警忽略 |
| AC08 | test_plugin_dependency_gating.py test_reward_compatibility.py | 10 passed | 卧底战绩照记不发新称号；兑换码依赖拒绝不核销；局部历史撤销例外保留且受部署边界限制 |
| AC09 | test/test_deployment_templates.py | 8 passed | 模板经共享校验；名单精确=系统5+监控+打卡基础9；无私域/经济插件；包成员合法；标签无关；子进程隔离加载：新群/新账号默认关闭、系统恒开；首版菜单无经济指令 |
| AC10 | 全量 | **592 passed** | 无生产数据访问；对旧错误开关行为采用新断言 |
| AC11 | `openspec validate config-unification --strict`；`git -c core.whitespace=cr-at-eol diff --check`；临时副本归档 + `openspec validate --all --strict` | 通过 | 规范按能力独立存放；kb/QUICK_REFERENCE、specs/plugins 附录、config.example、开发计划警示均已同步；版本 1.52.0 与 CHANGELOG 一致 |

## 行为修正说明（提案范围内的既定变化）

- 心跳任务不再绕过开关（含商店公告、新闻抓取等"白跑"路径）。
- 菜单不再向所有用户展示管理员指令清单；普通用户菜单按开放集合裁剪。
- 旧 `menu_text` 整段文案包覆盖停用（告警并忽略），改为逐条覆盖。
- 旧私有配置零迁移即可加载；`bot.edition` 任意值均不再影响校验与默认值。
