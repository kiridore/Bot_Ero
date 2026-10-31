# 浏览器首页抓取设计

## 取代旧方案

原requests公开API分页在Ubuntu返回432；实测未登录Chromium可读手机首页，滚动翻页跳登录。按所有者最新决定，放弃20页抓取和48h覆盖承诺；48h仅是已有推送年龄过滤。

## 模块边界

`weibo_browser.fetch_homepage()` 返回页面自然加载的JSON。常量UID/首页地址集中在此模块。同步Playwright延迟导入，不让自动导入插件时缺依赖导致bot无法启动。函数使用新的临时BrowserContext，不读取用户浏览器配置或保存Cookie。

正常启动headless Chromium，导航前等待匹配HTTPS m.weibo.cn/api/container/getIndex 且 containerid=1076036279793937 的首批响应，排除个人资料响应和其他账号。导航/等待均45秒超时，启动30秒超时。等待requestfinished而非response事件，确保正文完整下载后才调用json()；仅收到200响应头、正文未结束也会超时，不占住轮询锁。不调用page.request、不滚动、不执行反检测脚本。校验响应成功、JSON ok=1和cards为列表；仍停留在登录/访客域时失败。无有效目标微博的非空卡片也不推进游标。

浏览器创建后以try/finally关闭；成功返回之前释放浏览器。每次轮询使用独立实例，没有常驻进程/跨线程对象/后台队列；existing _poll_lock限制并发。

`_fetch_arknights_weibo()`仅将首页cards转为现有NewsItem，数字ID去重排序。解析函数继续使用绝对发布时间，避免从DOM的“昨天/分钟前”推算。保留HTML和媒体处理，不发送视频、不抓全文。

## 诊断与依赖

根requirements固定playwright==1.64.1，webapp子集不增加依赖。Ubuntu以bot服务账户、同一虚拟环境运行pip install和playwright install chromium；系统依赖由管理员安装，不能只在root缓存装浏览器。独立CLI不导入项目配置，输出版本、目标账号、卡片数与少量id/时间，失败非零退出；不输出整个JSON或令牌。安装/验证写docs/weibo-browser-deployment.md。

## 验证

模拟playwright.sync_api资源对象测试启动、超时、响应过滤、清理、缺依赖、CLI失败退出；复用精简响应测试解析、首次基线与重复去重，重写旧分页测试为首页边界测试。真实本机验证只加载网页，无QQ投递；Ubuntu由用户运行同一CLI验证。
