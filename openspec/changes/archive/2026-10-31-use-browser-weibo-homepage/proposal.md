# 微博源改用浏览器读取手机首页

## Why

部署环境直接请求微博API返回432。普通Chromium新访客上下文能正常加载手机主页正文及页面自身发起的内容响应；正常滚动则进入登录页。所有者明确接受仅首页、不翻页及可能漏掉首页之外内容的边界。

## What Changes

- 在master将微博源从requests直连分页改为同步Playwright+Chromium正常加载手机主页，只取页面自然发出的首批账号内容响应，不主动调用API、不滚动、不登录。
- 独立 `plugins/news/weibo_browser.py` 负责浏览器资源生命周期和响应验证，并提供只读CLI检查；不导入bot配置，不触数据库、不发QQ。
- 保留2号源与稳定key、摘要/媒体解析、去重及48h过滤；FF14完全不变。
- 固定Playwright版本1.64.1；懒导入，缺少依赖/浏览器只令微博轮询失败。Ubuntu需同一bot账户安装Chromium与系统库。
- 版本1.60.1，同步部署文档与规范。原20页、完整近期覆盖方案废止。

## Capabilities

### New Capabilities
- 无。

### Modified Capabilities
- `news-subscription`：微博获取方式与首页范围、资源管理、失败保护。

## Acceptance Criteria

|编号|执行|通过条件|
|---|---|---|
|AC01|`python -m pytest test/test_news_browser.py -q`|仅正常打开手机主页；捕获正确账号内容响应；新上下文、无登录/导入Cookie/滚动/API主动请求；成功、超时、HTTP/JSON/坏响应都释放浏览器|
|AC02|`python -m pytest test/test_news_weibo.py test/test_news_subscribe.py -q`|首页置顶/重复/空列表/坏字段、摘要时区图片与源间隔离保持正确；2号订阅与FF14兼容|
|AC03|临时环境运行 `python plugins/news/weibo_browser.py`|本机实际浏览器获取目标账号微博，诊断只输出账号、数量、id与时间，无Cookie/令牌；此证据不替代Ubuntu验证|
|AC04|`python -m pytest -q`、`openspec validate use-browser-weibo-homepage --strict`|全量通过，部署文档/版本/验收一致并归档|

## Non-goals / Risks

不导入或持久化登录凭证，不绕过验证码，不反检测，不翻页，不补抓首页之外内容，不修改bot多线程同步模型。浏览器正常执行访客脚本可能使用仅存在本轮上下文内的访客Cookie，退出即销毁。首页容量不固定，不能承诺12条或完整48h；轮询间新增过多或长时间停机可能漏推。Ubuntu连通性与QQ投递须部署验收。
