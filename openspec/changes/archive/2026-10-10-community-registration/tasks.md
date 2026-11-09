# Tasks

## 1. 数据与配置

- [x] 1.1 `user_accounts` 幂等加列（eula_version/agreed_at）+ `CommunityManager.agree_eula`；`test_community_db.py` 增用例（AC5）
- [x] 1.2 `core/config.py` register 节常量 + `validate_config` 类型校验 + `validate_deployment_policy` 补协议文件与包名校验；`test_config_validation.py` 增用例（AC3）

## 2. 注册插件与流程

- [x] 2.1 `plugins/register/`：/注册 流程（定稿文案逐句、停顿、合并转发、大小写不敏感）、/同意EULA（持久化+播种+通知+收尾）、群聊引导、重复注册重发、已完成回执、内存会话（AC1）
- [x] 2.2 `plugins/personal_records/events.py` 订阅 register.completed 发资料卡（核对头像事件外调用，降级无头像）；未开放静默（AC1）
- [x] 2.3 `plugins/welcome/` 文案键化（内置默认逐字节不变）；`community.yaml` 增 `welcome.friend_add`（AC1）

## 3. 私聊准入

- [x] 3.1 `main.py` 未注册放行矩阵 + 命令样式提醒限频（core/context 限频字典）；require=false 零行为（AC2）
- [x] 3.2 `test_register_gate.py` 准入矩阵：未注册限制/限频提醒/已注册无影响/群消息不受影响/require=false 全放行（AC2）

## 4. 菜单、模板与文档

- [x] 4.1 菜单条目表增 /注册 行（/同意EULA 不进）；`test_enabled_menu.py` 断言（AC4）
- [x] 4.2 `docs/eula/v1.md` 草稿（文件头标注草稿）；公开模板增 register（AC3）
- [x] 4.3 kb/PLUGIN_CATALOG、kb/QUICK_REFERENCE、specs/plugin-catalog、specs/plugins 同步（AC7）

## 5. 验收与归档

- [x] 5.1 bump 1.53.0 + CHANGELOG（AC7）
- [x] 5.2 全量 pytest 绿 + 严格校验 + 临时副本归档演练（AC6、AC7）
- [x] 5.3 验收记录 + 归档与实现同 commit
