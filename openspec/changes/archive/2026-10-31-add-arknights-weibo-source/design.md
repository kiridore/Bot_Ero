# 设计

## 决策依据

复用 `plugins/news/__init__.py` 的 NewsSource/NewsItem 和独立 source_id 游标；不加新表或通用爬虫框架。只追加源，保留 FF14编号。配置内不添加凭证；账号是所有者指定的硬编码消息源。

## 解析与边界

- getIndex 固定 HTTPS 域名，containerid=1076036279793937，page 从1开始。样本 cardlistInfo.page=2 不能直接解释为当前页，不用它驱动翻页。
- 仅处理 card_type=9 且 user.id 匹配的顶层微博；忽略非微博卡片及其他账号。转发帖如存在，只输出本账号外层摘要，不递归搬运原帖。
- 数字 id 必须为正 ASCII 整数串；created_at 用标准库 email.utils.parsedate_to_datetime，不依赖系统英文 locale。带时区值转为进程本地时间后去掉 tzinfo，与现有调度 datetime.now() 比较。
- HTMLParser 提取文本、br/p/div 换行与图片 alt 表情，忽略 script/style 内容。保留话题和提及文字，不生成 QQ AT；仅订阅者使用既有 AT 逻辑。列表已截断的长文保持摘要并保留原文链接。
- 图片依次取 pics 首张非视频项的 large.url/url、original_pic；无正文图片才使用 video/article 的 page_info.page_pic.url，不把 topic 超话图标当正文封面。仅允许 http/https 的 sinaimg.cn 域及子域，统一 HTTPS，拒绝带认证信息、端口或其他域名的地址；避免把外部数据变成任意网络请求。
- 原文链接构造 https://m.weibo.cn/status/<数字id>，不使用 scheme 跟踪链接或有时效签名的流媒体地址。
- 每页收集全部条目后判断停止：非置顶条目存在且全部早于48小时则停止，空cards则结束。不能遇到第一条旧置顶就停止。每轮最多20页；重复整页无新ID、无有效微博的非空页、坏字段、登录响应、页数耗尽均失败，不返回已抓部分。
- 保留现有游标比较与首跑基线；正文标题固定，摘要最多1000字，超限加省略号。无需改动公共推送逻辑。

## 测试与风险

新建 test/test_news_weibo.py 以及仅含必要字段的样本夹具，剔除 user_token、头像签名与视频流签名；mock HTTP，全部测试使用 pytest 临时配置/数据库。现有指令测试增2号源独立订阅。通过真实 send_msg 模拟路径断言默认群与AT不回归。

公开接口没有稳定服务承诺，可能432、登录要求或字段变化；失败记日志并保留游标。20页上限为明确保护，超限需要调整抓取策略，不静默截断。非置顶列表按时间倒序是分页停止的假设；置顶以 profile_type_id 的 proweibotop_ 或 mblog.title.text=置顶识别。离线样本成功不等于部署可抓取。
