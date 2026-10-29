# 实施与验收任务

## 1. 数据层
- [x] 1.1 `core/db/_base.py::init_schema` 增 `news_subscriptions`、`news_push_state` 两表；新建 `core/db/news.py::NewsManager`（subscribe/unsubscribe/is_subscribed/subscribers/get_cursor/save_cursor）；`core/database_manager.py` 装配。对应 AC01/AC02 的数据基础。

## 2. 插件改造
- [x] 2.1 `plugins/ff_news/` → `plugins/news/`：注册名 `news`；模块级 `NewsSource`/`NewsItem`/`_SOURCES` 注册表（FF14 源复用现有接口，完整分页抓取并按数字编号排序）；删除 `/FF新闻` 指令路径；新增 `/订阅`（列表+编号订阅）、`/退订 编号` 指令（私聊拒绝提示、任何群成员可用、幂等）。对应 AC01、AC03。
- [x] 2.2 心跳推送：`minute in (0, 30)` 轮询全部源；游标去重（首跑只记位置、无人订阅或超龄跳过推进，发送失败不推进、数值比较）；48 小时过滤；有订阅者逐条推送、AT 全部订阅者、正文沿用现有格式；单源失败跳过不中断。对应 AC02。

## 3. 测试
- [x] 3.1 新建 `test/test_news_subscribe.py`（进程内 unittest，沿用 `test/helper.py` 夹具，注入假 fetch）：覆盖 AC01 指令段（列表含编号+名称+订阅状态、订阅/重复幂等、退订/未订阅提示、私聊拒绝不写库、/FF新闻 不再匹配）与 AC02 推送段（无人订阅不推、有订阅者 AT+正文、同条不重推、首跑不补推、超 48h 不推、多条逐条、单源失败跳过且游标不动）。pytest 原生收集纳入统一回归。

## 4. 文档与交付
- [x] 4.1 `plugins/menu/bot_menu_text.py` 增 `/订阅`、`/退订` 行；`kb/PLUGIN_CATALOG.md`、`specs/plugin-catalog.md`、`kb/QUICK_REFERENCE.md` 指令表同步（27 号插件行更名改述）；`kb/DATABASE.md`、`specs/database.md` 增两表；CHANGELOG 新节 + bump 1.59.0；roadmap 补一节；`core/feature_packs.py` 休闲娱乐包 `ff_news`→`news`；历史社区计划保留原名并标明更名说明。对应 AC03、AC04。
- [x] 4.2 全量 `pytest -q`：465 passed；专项 23 passed；`openspec validate news-subscription --strict` 通过；独立审查无阻塞项。验收见 acceptance.md，归档与实现同一提交。
