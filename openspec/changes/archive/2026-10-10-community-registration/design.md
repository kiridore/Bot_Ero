# Design — 注册插件与私聊准入（M1 之一）

## 所有者定稿共识（2026-10-10 三轮质询）

流程链：好友申请（auto_friend 自动通过，不动）→ friend_add 欢迎消息（welcome 插件 + 文案包键）→ 用户私聊 `/注册` → 流程四段（预告/引导/协议合并转发/同意指引）→ `/同意EULA`（大小写不敏感）→ 持久化 + 播种 + 注册完成通知 → 收尾两段 + 资料卡（personal_records 消费，未开放则静默）。

关键裁定：显式 `/注册` 开始（不自动注入流程）；会话内存态、同意凭证持久化；协议独立文件；"完成啦"句按修订文案（基础功能已开放）；停顿 2–3s/转发后 5s；星号 `*写写*` 原样保留；`auto_friend` 与注册职责分离；welcome 保留复用。

## 定稿文案（逐句，实现按此原样）

1. 欢迎键（community.yaml 草稿）：`感谢添加~回复 /注册 开始注册，/菜单 查看功能`（内置默认 = 现私有文案不变）
2. `/注册` 后：
   - `现在开始注册流程，大概需要5分钟~`（sleep 2–3s）
   - `首先需要阅读一下我们的《用户协议》，里面一定有很多你关心的内容，务必看过之后再同意哦`（sleep 2–3s）
   - 合并转发《用户协议》（sleep 5s）
   - `如果看完后同意，请使用 “/同意EULA”指令继续`
3. `/同意EULA` 后：
   - `太好了！感谢你的理解，那我先帮你登记*写写*`（sleep 2–3s）
   - `完成啦，这是你的个人资料卡，基础功能已开放，更多功能会逐步开放，用“/菜单”指令看看现在有什么吧~`
   - 资料卡（若 personal_records 开放）

## 模块与数据

- `plugins/register/__init__.py`：CommandPlugin，`COMMANDS = ("/注册", "/同意EULA")`。ASCII 大小写不敏感在指令匹配层归一化（比较前 `lower()` 命令词的 ASCII 部分）。
- 会话：类级 dict `_sessions: {uid: step}` + 类级锁（参照 `TimedHeartbeatPlugin._last_run_minute` 先例）；步骤枚举 `eula_sent`。
- 停顿：`time.sleep(random.uniform(2, 3))` / 转发后 5s——每事件独立线程，短睡无副作用。
- 播种：`set_user_plugins(conn, uid, FEATURE_PACKS[config.REGISTER_DEFAULT_PACK]["plugins"], True)`（core/db/plugin_settings 既有函数，群聊版函数已有事务回滚先例）。
- 通知：`self.publish_event("register.completed")`（core/base 既有方法）；`plugins/personal_records/events.py` 新增订阅者渲染并发卡。头像获取经 `ApiWrapper.get_qq_avatar`——实现时核对事件外可用性，不可用则走既有无头像降级（不阻塞主线）。
- `user_accounts` 迁移：`init_schema` 幂等 `ALTER TABLE ADD COLUMN eula_version TEXT` / `agreed_at TEXT`（按 PRAGMA table_info 判存在，与库内既有迁移手法一致）；`CommunityManager.agree_eula(uid, version)` 幂等写凭证。
- 配置常量：`REGISTER_REQUIRE`（缺省 False）、`REGISTER_EULA_FILE`、`REGISTER_DEFAULT_PACK`、`REGISTER_REMINDER_MINUTES`（缺省 30）；`validate_config` 补 register 节类型校验；`validate_deployment_policy` 补：require=true 时 eula 文件存在可读、default_pack 在 FEATURE_PACKS 中（启停一致性，两类部署同一规则）。

## 私聊准入（main.py plugin_pool）

```
私聊 message 事件且 REGISTER_REQUIRE：
  未注册 → 插件循环只放行 {"register", "show_menu"} 两个插件键；
           若消息以 "/" 开头且不属注册/菜单指令 → 经限频字典回一句提醒
           （提醒文案：`先完成注册哦，回复 /注册 开始~`；每账号每 REMINDER_MINUTES 分钟一次）
  已注册 → 无限制
```

- 限频字典：`core/context.py` 模块级 `_register_reminder_at: {uid: ts}` + 锁。
- 提醒发送：直接经该事件的 ApiWrapper `send_private_msg`（不进统一输出——非插件产出，属准入层拒绝提示；实现时若与输出模块有更自然接法可调整，不改变行为契约）。
- 群消息、notice、meta 一律不受此检查影响。

## welcome 文案键

`get_text("welcome.friend_add", 内置默认)`；内置默认字符串与现私有文案逐字节相同；`community.yaml` 增键。

## 明确不做

- 协议改版重同意（版本已记录，策略挂起）。
- 打字逐字动画；好友申请频控（拉黑提案范围）。
- 未注册用户的非命令消息提醒（只对 "/" 开头命令样式提醒）。

## 测试设计

`test_register_flow.py`（流程/持久化/播种/通知/文案逐句/停顿存在性——sleep 以 mock 断言调用次数与区间）、`test_register_gate.py`（准入矩阵）、`test_community_db.py` 增迁移与凭证用例、`test_config_validation.py` 增 register 节、`test_deployment_templates.py` 增公开模板含 register、`test_enabled_menu.py` 增 /注册 行与 /同意EULA 不在菜单。

## 风险

- 私有部署唯一风险点是 main.py 改动——require=false 分支必须零行为差异（AC2 专门矩阵覆盖）。
- 发卡依赖头像 API 的事件外调用——降级路径已有，不阻塞。
