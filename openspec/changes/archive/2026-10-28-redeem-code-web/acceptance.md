# 验收记录

## 基线与边界

基于 master 1.57.0 独立分支实现，版本 1.58.0；未合入 dev 社区代码。测试全部使用临时配置与临时数据库，未触碰真实 data.db。

## 逐项结果

| 标准 | 实际命令 | 结果 |
|---|---|---|
| AC01 | `python test/scripts/check_redeem_web.py` | 19 项断言通过：401 门控、格式/未知码零写入、小写归一兑换成功、称号+积分到账、重复拒绝、回调失败占位与奖励双回滚后可重试 |
| AC02 | 同上（历史段） | 迁移前旧记录行原样可见且倒序；下架码显示占位说明；跨用户隔离；另一用户可兑换同码（按用户一次性） |
| AC03 | `node test/test_profile_redeem_tab.js` | 12 项断言通过：tab 渲染、默认隐藏、惰性加载、历史行字段、成功/失败行内反馈、空输入不发请求 |
| AC04 | `rg -n '兑换码' plugins/ plugins/menu/bot_menu_text.py`；目录检查 | `plugins/redeem_code/` 已删；`test_redeem_code.py` 已删；菜单无 `/兑换码` 指令行（仅入口指引文字，不含指令语法、无响应桩） |
| AC05 | `python -m pytest -q`；`openspec validate redeem-code-web --strict` | 全量 442 passed；严格校验通过；归档与版本一致性见下文 |

## 一致性

- `BOTERO_VERSION` 与 CHANGELOG 首节均为 1.58.0；插件目录 46 个（45 号留空档并注明）。
- specs/database（新读写层）、specs/web-gallery（两行 API）、kb/DATABASE、kb/QUICK_REFERENCE、kb/PLUGIN_CATALOG、菜单文本、roadmap 已同步。

## 归档

先临时副本归档验证规范可合并，再真实归档与实现同一提交；不自动合并 master/dev 或推送。

## 限制

- 未做真实浏览器与 QQ 客户端人工验证（用户侧以自动回归为准）；部署需重启 webapp（bot 进程不变，但同机更新需拉取代码后按进程分别重启）。
- dev 同步警示见 implementation-findings.md：dev 合并时需在网页服务重接受限账号拒绝与依赖关闭拒绝语义。
