# 个人中心邮箱绑定设计

日期：2026-09-12 · 状态：已确认（用户裁定）

## 目标

社区站账号（QQ 登录态）可绑定邮箱：填写邮箱 → 收 6 位验证码（10 分钟有效）→ 输码完成绑定；支持换绑（同流程覆盖）与解绑（当前邮箱验证码确认后清空）。复用既有 `core/mail_client.py`（cloud-mail）发信。

## 决策表

| # | 决策 |
|---|------|
| D1 | 入口 = 设置页 `/profile/settings` 新增「账号邮箱」卡片；未绑定 = 绑定表单（邮箱 + 发码 + 输码绑定），已绑定 = 脱敏展示（`ab***@qq.com`）+「换绑」+「解绑」（解绑向当前邮箱发码） |
| D2 | 存储 = `user_settings` 顶层键 `email`（str）与 `email_bound_at`（ISO 时间），深合并既有机制，无 schema 变更；`GET /api/me/settings` 响应扩展 `email` 字段（未绑定为 null），前端据此渲染 |
| D3 | `POST /api/me/email/code` `{email, purpose: bind\|unbind}`：校验邮箱格式（简单 regex）→ 生成 6 位数字码 → `mail_client.send_email` → 200 `{cooldown_seconds: 60}`；`purpose=unbind` 忽略入参 email、只发当前绑定邮箱（未绑定则 400）；**60 秒冷却**按 user+purpose，重发覆盖旧码；mail 未配置（`_configured()` False）→ 503 |
| D4 | `POST /api/me/email/bind` `{email, code}`：码须匹配 user+email+10 分钟内+错误尝试 ≤5 次 → `update_settings` 写入 email/email_bound_at；换绑 = 同流程覆盖（旧码随新码发出即失效） |
| D5 | `POST /api/me/email/unbind` `{code}`：对当前邮箱 pending 码校验通过 → 清空 email/email_bound_at |
| D6 | 验证码状态 = webapp 进程内 dict + `threading.Lock`（单进程是仓库硬约束；重启丢码可接受=重发即可）；条目 `{code, email, purpose, expires_at, attempts, last_sent_at}`，过期/作废即删 |
| D7 | 邮件模板：主题「BotEro 邮箱验证码」，HTML 正文 = 验证码大字 + 「有效期 10 分钟」 + 「若非本人操作请忽略」；`send_email` best-effort 返回 `(False, msg)` 时 API 返回 500 带原因 |
| D8 | 测试 = 脚本套件 `test/scripts/check_profile_email_bind.py`（monkeypatch `core.mail_client.send_email` 捕获调用，不发真邮件；覆盖绑定/换绑/解绑/冷却/过期/次数上限/错码/未配置 503/邮箱格式 400）+ 进程内单测验证码服务纯逻辑（TTL/冷却/attempts）；全部走 `write_config` 临时配置 |
| D9 | 不做：邮箱唯一性（多账号可绑同一邮箱）、验证码哈希存储（进程内存即私有）、解绑二次确认 UI 弹窗之外的服务端状态机、找回密钥/通知等下游功能（YAGNI） |
| D10 | 文档同步：CHANGELOG `[1.47.0]` + `BOTERO_VERSION` minor bump + `specs/web-gallery.md` 路由表 3 行 + `kb/OPERATIONS.md` 无改动（web 路由不在此文件）；`plugins/menu/bot_menu_text.py` 不动（无 QQ 指令） |

## 改动点

- `webapp/profile/email_service.py`（新）：验证码状态机（发送/校验/冷却/过期/作废）+ 邮件模板 + 邮箱脱敏工具
- `webapp/profile/app.py`：3 个新路由 + `SettingsOut` 扩展 `email` 字段
- `webapp/static/settings.html` / `settings.js`：邮箱卡片渲染（绑绑定/换绑/解绑三态）+ 60s 冷却倒计时按钮
- 测试：`test/scripts/check_profile_email_bind.py`、`test/test_email_code_service.py`
- 文档：`CHANGELOG.md`、`core/config.py`、`specs/web-gallery.md`

## 边界

- 所有路由挂 `get_current_user_id`（`/api/me/*` 登录门控既有）
- 冷却与 attempts 状态仅进程内（多实例部署会失效——仓库已禁止 `--workers`，不另做跨进程存储）
- 邮箱格式仅做 `^[^@\s]+@[^@\s]+\.[^@\s]+$` 级校验，不做送达校验（发信失败即反馈）
- bot 侧零改动（纯 webapp 功能）
