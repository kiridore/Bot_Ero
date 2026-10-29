# 新闻订阅验收记录

实施分支：master（所有者明确要求）；版本 1.59.0。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 指令 | `python -m pytest test/test_news_subscribe.py -q`：列表/状态、幂等订阅、退订、非法参数、跨群共享与私聊拒绝 | 通过 |
| AC02 推送 | 同一专项共 23 passed：首次基线、无订阅者、48h过滤、逐条推送、失败重试、游标不倒退、半小时调度、默认群路由、AT/称号/图片、分页 | 通过 |
| AC03 更名与清理 | 旧插件源文件删除；功能包与菜单改用 news、/订阅、/退订；旧指令不匹配测试通过 | 通过 |
| AC04 回归与校验 | `python -m pytest -q`：465 passed，11030 warnings（既有 pytest_asyncio/Python 弃用警告）；`openspec validate news-subscription --strict`：valid | 通过 |
| 独立审查 | reviewer 只读检查源码/提案/测试：No issues found，OK，无阻塞项；未重复执行测试 | 通过 |

## 实测与裁定

- 只读请求真实 FF14 官网确认数字编号和日期格式；列表有置顶，pageIndex 为小写，pageSize 服务端上限 50。因此不保留原设计取前 10 条的漏洞，改为完整分页后排序。
- 专项测试采用现有 bot 进程内 pytest 布局，而不是 webapp 集成脚本。
- 按 master 既有框架发送，不引入 dev 的插件开关/黑名单机制；不修改真实配置。
- 不连接真实 QQ 发送消息，不触碰真实 data.db/server_data。没有部署验证。
- 若发送实际成功但确认丢失或保存游标前进程退出，下轮可能重复；修改旧编号公告不当作新消息。分页超过 200 页时会停止该轮并记日志，需要调整抓取策略。
- 更名可能影响部署自行设置的 ff_news 名称，已在 CHANGELOG 提醒改为 news。
