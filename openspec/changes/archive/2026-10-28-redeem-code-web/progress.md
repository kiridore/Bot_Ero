# 实施进度

基线：master 1.57.0（17cdd7b），独立分支 feat/redeem-code-web；不自动合并/推送。

## 完成（5/5 任务）

- `RedeemManager` 重写为 `claim_in_transaction()`（事务内原子占位）＋ `history()`，删除旧 `claim()/release()` 两段式。
- 注册表与两个回调迁至 `webapp/profile/redeem_service.py`（回调去 api 参数；称号/积分均 `commit=False` 入同事务）；`BEGIN IMMEDIATE` 单事务占位＋奖励，异常整体回滚。
- API：`GET /api/me/redeem/history`、`POST /api/me/redeem`；登录门控复用 `get_current_user_id`。
- 前端：`profile.js` 第三 tab「兑换码」（输入＋行内反馈＋惰性历史），样式入共享 `core/web/static/profile.css`。
- QQ 端：删除 `plugins/redeem_code/` 与 `test/test_redeem_code.py`；菜单行改入口指引（不含指令语法，无提示桩）；插件目录/数据库/指令表/API 表同步（46 插件，编号留空档）。
- 版本 1.58.0、CHANGELOG、roadmap、specs/database、specs/web-gallery、kb/DATABASE、kb/QUICK_REFERENCE、kb/PLUGIN_CATALOG。

## 测试

- `test/scripts/check_redeem_web.py`（自动发现）：19 项断言全过——401 门控、格式/未知码不写库、小写归一成功、重复拒绝、组合奖励、历史兼容（旧行＋下架占位＋倒序＋隔离＋跨用户按用户一次性）、回调失败占位与奖励双回滚、重试成功。开发中修正过一处测试断言缺陷（注入回调误选用户已拥有称号，改为未拥有的 502 才能证明回滚）。
- `test/test_profile_redeem_tab.js`（自动发现）：12 项断言全过。初期 3 项失败为测试桩缺陷（className 字符串与 classList 集合未联动），修桩后通过；另补 `lightboxShare` 元素缺失。
- 全量 pytest：442 passed（旧插件 8 项测试删除，新增 2 项参数化套件）。

## 未做（明确）

- 真实浏览器与 QQ 客户端人工验证；dev 分支合并（见 implementation-findings 同步警示）；网页管理界面/批量生成（范围外）。
