# 浏览器微博首页抓取验收

分支master，版本1.60.1。所有者明确接受仅手机首页、不翻页及首页之外可能漏推的边界。

|条目|证据|结果|
|---|---|---|
|AC01 浏览器生命周期|test/test_news_browser.py：首批目标响应匹配、全新上下文、无滚动/主动API调用、依赖缺失、启动/导航/正文等待异常、非JSON/坏结构、登录与资源清理、CLI输出与退出码|通过|
|AC02 解析兼容|test/test_news_weibo.py与test/test_news_subscribe.py：首页置顶/重复ID、文本/时间/图片、首次基线与去重、失败不影响FF14、2号独立订阅；三文件合计74 passed|通过|
|AC03 本机真实浏览器|独立虚拟环境Playwright1.64.1、Chromium156.0.8078.4，直接执行生产文件 plugins/news/weibo_browser.py，两次均返回目标账号12条（含置顶）和完整时间；未加载bot配置、未发QQ|通过（Windows）|
|AC04 全量回归|最终 `python -m pytest -q`：516 passed，13980 warnings（pytest_asyncio/Python弃用警告）；严格校验通过|通过|
|独立审查|首轮发现response头事件不涵盖正文超时；已改为有超时的requestfinished，第二轮窄范围复审No issues found|已解决|

## 正文超时实测

使用本机ThreadingHTTPServer返回200及部分JSON后不结束正文，真实Chromium读取；测试将等待时间缩短至1.2秒。观察到200响应头，1.71秒内TimeoutError且browser.close恰好调用一次。回归测试另断言正文未完成时不调用json()。因此不是仅靠模拟异常假定有界。

## 未完成的部署验证

Ubuntu Server仍须按docs/weibo-browser-deployment.md在bot服务账户和实际Python环境安装系统依赖、Chromium，并运行只读CLI。尚未验证Ubuntu出口、OneBot端图片下载或QQ群投递。不提供登录Cookie、不绕过验证码。

## 已接受限制

不滚动、不分页，只读取页面自然加载的首页首批微博；容量不固定，不承诺固定12条或覆盖完整48小时。高频发布或停机可能漏掉首页之外内容。既有48h过滤、源编号、数据与发送确认语义保持不变。
