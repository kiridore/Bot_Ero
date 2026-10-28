# 实施与验收任务

## 1. 网页兑换服务与数据层
- [x] 1.1 `RedeemManager` 增事务内占位方法并删除旧 claim/release；迁移注册表与回调至 `webapp/profile/redeem_service.py`（去 api 参数），单事务占位＋奖励＋回滚。对应 AC01 事务项；先写失败测试再实现。

## 2. API 与集成回归
- [x] 2.1 `GET /api/me/redeem/history`、`POST /api/me/redeem` 接线；新建 `test/scripts/check_redeem_web.py` 覆盖 AC01/AC02（认证、成功、重复、无效、格式、失败回滚重试、历史含预置旧行、跨用户隔离、下架码占位说明）。自动发现纳入统一回归。

## 3. 前端与 QQ 端清理
- [x] 3.1 `profile.js` 增「兑换码」tab、输入/反馈/惰性历史；新建 `test/test_profile_redeem_tab.js` node DOM 冒烟（AC03）。
- [x] 3.2 删除 `plugins/redeem_code/` 与 `test/test_redeem_code.py`；同步菜单文本、kb/QUICK_REFERENCE、kb/PLUGIN_CATALOG、specs/plugin-catalog、specs/web-gallery；rg 核对无 `/兑换码` 残留（AC04）。

## 4. 交付
- [x] 4.1 bump 1.58.0、CHANGELOG、roadmap；全量 pytest、`openspec validate --strict`、临时副本归档验证后真实归档，与实现同一提交；记录 dev 同步警示（AC05）。
