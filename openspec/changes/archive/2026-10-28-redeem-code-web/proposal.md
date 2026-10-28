# 兑换码迁移个人主页：移除 QQ 指令

## Why

所有者指令：移除 `/兑换码` 指令，兑换码功能移至 webapp 个人主页新开一个 tab。兑换是一次性、低频、输入精确的操作，网页表单比群聊指令更合适：即时反馈、可见历史、不占群消息。QQ 群聊不再是兑换入口后，相关插件可整体删除。

## What Changes

- **删除 QQ 插件** `plugins/redeem_code/`：`/兑换码`、`/兌換碼` 不再被任何插件处理，无提示桩；菜单行与指令文档同步移除。
- **新增网页兑换服务** `webapp/profile/redeem_service.py`：兑换码注册表从 `plugins/redeem_code/codes.py` 迁入（新增码 = 改代码 + 重启 webapp，不做管理界面）；占位与奖励写入同一事务，失败整体回滚可重试，不沿用先占位后释放的两段式。
- **新增 API**（沿用全站登录门控与 `get_current_user_id`）：
  - `GET /api/me/redeem/history` — 本人兑换历史
  - `POST /api/me/redeem` — 提交兑换码
- **个人主页新 tab「兑换码」**：输入框（大小写不敏感、服务端格式校验）＋兑换按钮＋行内结果反馈＋本人历史列表（码、时间、奖励说明），tab 切换时惰性加载。
- **数据兼容**：继续使用 `redeem_code_usage` 表，历史兑换记录天然保留并出现在新历史列表中。
- 版本 bump **1.58.0**（新功能 minor）。

## Capabilities

### New Capabilities
- `redeem-codes`：网页端兑换码使用、一次性原子兑换、历史查询、QQ 指令移除边界。

### Modified Capabilities
- 无（master 无既有兑换码规范；dev 分支的黑名单联动属 dev 侧后续同步事项，本提案不实现）。

## Scope and Compatibility

- 基于 master（1.57.0）独立功能分支实施；不自动合并/推送。
- 回调契约简化：`callback(db, user_id) -> str | None`（去掉 QQ api 参数，现有两个回调均未使用它）。
- 不做：网页管理界面、兑换码批量生成、QQ 端引导提示、dev 分支合并（dev 的 `requires`/黑名单联动在后续同步时按其语义重接，记入提案警示）。
- 移除插件不影响 `redeem_shop`（商店）——两者独立。

## Acceptance Criteria

| 编号 | 可执行验证 | 通过条件 |
|---|---|---|
| AC01 | `python test/scripts/check_redeem_web.py` | 登录后兑换成功（称号/积分到账）、重复兑换被拒、无效/格式错码被拒且不写库、回调失败整体回滚可重试、未登录 401 |
| AC02 | `python test/scripts/check_redeem_web.py`（历史段） | 历史含迁移前的旧记录行；仅本人数据；已下架码显示通用文案不泄露详情 |
| AC03 | `node test/test_profile_redeem_tab.js` | 个人主页渲染出「兑换码」tab；切换后加载历史并渲染列表；兑换结果行内展示 |
| AC04 | `rg -n '兑换码' plugins/ plugins/menu/bot_menu_text.py` 与插件目录检查 | `plugins/redeem_code/` 不存在；菜单文本无 `/兑换码` 行；全量 pytest 中旧 `test_redeem_code.py` 已删除或改写 |
| AC05 | `python -m pytest -q`；`openspec validate redeem-code-web --strict` | 全量与提案校验通过；临时副本归档验证后真实归档，与实现同一提交 |

## 维护者可持续性

复用既有登录门控、profile tab 结构与商店服务的同构模式，无新服务、无新表。兑换码维护方式与现状等价（改代码重启 webapp 代替改代码重启 bot）。测试新增一个自动发现的 API 脚本与一个 node DOM 冒烟，纳入统一回归。
