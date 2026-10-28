# 设计

## 1. 服务位置与边界

- `webapp/profile/redeem_service.py`：注册表 `REDEEM_CODES`（迁自 `plugins/redeem_code/codes.py`，条目结构不变）＋ `redeem_code(user_id, raw_code)` ＋ `redeem_history(user_id)`。遵守 webapp 规则：**不导入 plugins 包**（同 `shop_service.py`）。
- 回调契约：`callback(db: DbManager, user_id) -> str | None`。返回值作为奖励说明拼进成功消息与历史列表。现有两个回调（测试员称号、一周年称号+10积分）随迁，去掉未使用的 api 参数。
- `redeem_shop`（积分商店）与此无关，不动。

## 2. 原子兑换事务

现状 bot 端是"占位提交 → 回调 → 异常再删占位"两段式，中途崩溃会留下已占位未发奖的行。网页服务改为单事务：

```
BEGIN IMMEDIATE
  INSERT OR IGNORE INTO redeem_code_usage ...  → rowcount=0 即已用过，拒绝
  执行回调（titles.unlock(commit=False)、points.adjust 等）
COMMIT（异常整体 ROLLBACK，占位随事务消失，可直接重试）
```

- `db.titles.unlock` 已有 `commit=False`；积分走 `db.points.adjust`（单语句原子加减，不自动提交——实现时核实，若内部 commit 则改为事务内等价写法）。
- 不新增 RedeemManager 方法也不改其签名：旧 claim/release 留给… 实际上插件删除后 RedeemManager 仅剩网页服务使用。服务内直接以 `db.conn` 执行参数化 SQL 属违规边缘——**改为给 `RedeemManager` 增加事务内方法 `claim_in_transaction(user_id, code) -> bool`**（INSERT OR IGNORE 不提交），旧 `claim/release` 随插件一并删除，DDL 与业务方法仍归 core/db。

## 3. API

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/api/me/redeem/history` | 按 used_at 倒序返回 `[{code, used_at, description}]`；码已不在注册表 → `description: "（已下架）"`，不回退泄漏旧定义 |
| POST | `/api/me/redeem` | body `{"code": "..."}`；规范化为大写；`CODE_PATTERN` 校验 → 未知码 400「兑换码不存在或已失效」；已用过 400「你已使用过该兑换码」；回调异常 500「兑换处理失败，请稍后再试」且占位回滚 |

- 登录：沿用 `login_guard` 中间件与 `get_current_user_id`，未登录 401 由现有门控产生，不做新鉴权。
- 未知码在查注册表阶段拒绝，不产生任何 DB 写入。

## 4. 前端 tab

- `profile.js`：`renderTabShell()` 增 `["redeem", "兑换码"]`；新增 `panelRedeem` 面板：输入框 + 按钮 + 结果区 + 历史列表（惰性加载，同 checkins 模式）；输入端 `toUpperCase()` 归一，提交失败行内展示 detail 文案。
- `profile.html` 无需结构改动（tab 由 JS 渲染）；样式复用 `.tab-panel`、`.title-filters` 等既有类。
- node DOM 冒烟 `test/test_profile_redeem_tab.js`：stub `fetch` 返回 profile/history/redeem 响应，断言 tab 按钮、历史渲染、兑换反馈（沿用既有 `test_*.js` stub 模式，由 `test_dom_render_suites.py` 纳入回归）。

## 5. QQ 端移除清单

- 删 `plugins/redeem_code/`（`__init__.py`、`codes.py`）与 `test/test_redeem_code.py`（覆盖迁至 `check_redeem_web.py`）。
- `plugins/menu/bot_menu_text.py`：删 `/兑换码` 行。
- `kb/QUICK_REFERENCE.md`：删指令行；`kb/PLUGIN_CATALOG.md`：删插件行（编号不重排，留空档并注明移除）；`specs/plugin-catalog.md` 同步。
- `specs/web-gallery.md`：API 表补两行。
- `text_packs/community.yaml` 不涉及（master 无该文件；dev 同步时另行处理）。

## 6. 测试

- `test/scripts/check_redeem_web.py`（自动发现）：环境隔离用 `_env.write_config`；`make_login_key` 构造两用户；覆盖 AC01/AC02 全部断言，包括：预置一行旧 `redeem_code_usage` 数据出现在历史中、另一用户不可见、事务失败注入（建触发器炸 user_titles 写入）后占位与奖励均不存在且可重试成功。
- 旧 bot 测试删除；`test_plugin_migration_inventory.py` 在 master 不存在（dev 侧），无需处理。

## 7. 版本与流程

- bump `BOTERO_VERSION` 1.57.0 → 1.58.0，CHANGELOG 新节，roadmap/KING 同步。
- 独立分支 `feat/redeem-code-web`，验收全绿后归档、同一逻辑提交；合并 master 与推送另行授权。
- **dev 同步警示**（记入 implementation-findings，不在本轮实现）：dev 的 redeem_code 带 `requires` 依赖检查与黑名单快照拦截、走统一输出模块；同步时需把 web 兑换服务接上 dev 的部署许可/黑名单快照（被封账号网页兑换也应拒绝），不能只拿 master 版服务覆盖。
