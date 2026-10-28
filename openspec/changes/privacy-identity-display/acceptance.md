# 验收记录：隐私·昵称与头像公开开关

## 提交授权补记

用户随后明确要求提交并推送到远端。本次将三项个人偏好实现及配套文档作为1.57.0同批提交到dev，不动master；真实QQ水印验收仍待完成，三个提案保持未归档。以下“未提交/禁止提交”等表述为先前验收阶段记录，不再代表本次交付授权。提交前重新运行全量：821 passed（375.03秒）；OpenSpec严格校验18 passed。

## 结论与版本

2026-10-28，按 proposal/design 的执行 Ruling，与时间线观看偏好、生成图水印同批为 **1.57.0**。本提案功能验收已通过；未 commit/push/archive。同批水印提案的真实QQ验收未完成，不能宣称整批验收全绿或归档。

## 标准逐项对应

| 标准 | 状态 | 证据 |
|---|---|---|
| AC01 | 通过 | `test/test_user_settings.py`：缺省True、规范账号MD5前8位、确定性；纳入最终全量 |
| AC02 | 通过 | `test/test_identicon.py`：同账号一致、选定不同账号样本区分、合法PNG；不承诺全域无碰撞 |
| AC03 | 通过 | `test/scripts/check_identity_privacy.py`：本人/他人/默认公开，时间线作者及占位符、论坛作者/回复对象、图库、活动列表与详情、闹钟、直播、工具、TRPG、周报；由API子进程套件纳入全量 |
| AC04 | 通过 | `test/test_generated_image_privacy.py -k rank` 实际执行榜单入口，逐行匿名、不取真实头像、多人图无水印；绘图回归在 `test/test_gen_image.py`。按实际测试文件修正原独立命令，未降低标准 |
| AC05 | 通过 | `check_profile_checkins.py` 纳入最终API套件，无既有回归失败 |
| AC06 | 通过 | 最终 `python -m pytest -q`：821 passed，372.16秒 |
| AC07 | 通过（真实浏览器自动操作 + 人工看图） | 本机Chrome打开真实设置页；关闭身份公开、重新加载保持；账号111111自看仍为真实昵称，账号222222看其时间线为96e79218与站内图案头像；390px/1440px截图已实际打开，不是模拟页面 |
| AC08 | 通过 | 身份集成脚本覆盖历史活动姓名不回填、直播无需补心跳、周报大奖/三等奖/无人中奖及旧来源缺失局部降级，原JSON不变、原ID与用户正文保留 |
| AC09 | 通过 | `check_settings_preferences.py`：三个新增布尔键严格校验（非法类型422）、局部更新与邮箱保护；纳入最终全量 |
| AC10 | 通过（模拟发送） | `test/test_generated_image_privacy.py`、`test_register_flow.py`、`test_gen_image.py`：两个档案入口无本人豁免，匿名名与图案一致、不请求真实头像，发送参数仍使用实际账号；未发送QQ消息 |

## 自动化执行证据

- 本轮仅运行一次全量：`python -m pytest -q`，通过临时runner设置900秒超时；**821 passed, 40446 warnings in 372.16s (0:06:12)**，进程返回0，外层耗时373.20秒。不是把788基础、17个API集合、15个共享单测与65个图片定向用例相加；这些是前阶段的不同集合，本轮821才是最终全量数字。
- warnings 为当前Python/pytest_asyncio的弃用提示与Pillow `Image.getdata` 弃用提示；未改依赖或范围外测试。
- 日志：`C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\pytest.log`。
- 结果及计时：`C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\pytest_result.json`。
- 全量通过 `test_webapp_api_suites.py` 自动发现集成脚本、`test_dom_render_suites.py` 运行Node回归，包含父阶段修正的活动列表和时间线空页续读。此前父执行身份脚本与Node专项均通过，本轮未重复跑整套。

## 真实浏览器联动环境与证据

- 临时脚本：`C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\browser_check.py`。
- 执行：`python C:/Users/SC2_j/AppData/Local/Temp/botero_final_acceptance_ish85n9_/browser_check.py`，通过。首次检查后为截图滚动到时间线实际内容重新运行浏览器脚本；没有重跑pytest。
- 结果：`C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\browser_result.json`，详细输出 `browser.log` 在同目录。实际设置与时间线API响应均200；无页面外网请求。
- 真实Chrome无头 + 本地单进程uvicorn/webapp，真实页面JS、GET/PUT API、SQLite及无扩展名设置文件。所有配置/数据库/图片/缓存均由 `_env.write_config` 指向OS临时目录；服务仅监听127.0.0.1，浏览器独立临时profile，结束后关闭Chrome与服务。
- 只模拟OneBot昵称/头像来源：公开昵称为“真实昵称+账号”，头像用本地站内图片代替真实QQ头像；API序列化的本人/他人头像区别另由集成脚本断言。Python外部requests被禁止，浏览器拦截非本地请求并禁止外部域名解析。没有启动bot，没有真实QQ发送，没有接触真实data.db/server_data。
- 页面操作关闭三个开关，重新加载后状态保持，检查实际设置JSON；随后开启水印并再次重新加载保持。时间线观看关闭后实际DOM仅3条（本人打卡、本人论坛、他人论坛），另一默认查看者4条；作者本人真实昵称、他人匿名名与图案地址均断言通过。
- 已人工打开6张截图。390px/1440px没有横向溢出，新增开关文本和边框间距正常；现有四态选项在390px换行较密，未修改原布局。时间线未读底色下文字可读；本次无新对话框或前后翻页按钮，未进行其交互验收。截图只代表本机Chrome报纸风，不等于真实手机/QQ客户端。

截图绝对路径：

- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\settings-desktop.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\settings-mobile.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\timeline-owner-desktop.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\timeline-owner-mobile.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\timeline-other-desktop.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\timeline-other-mobile.png`

## 未完成与边界

- 本提案功能AC无待验项；T18同批提交/归档未执行，本轮明确禁止。同批水印AC06真实QQ检查仍待完成。
- 匿名名/图案不提供安全匿名化；账号、链接关联、用户自填正文不隐藏。网站本人豁免不适用于可传播bot图片。图案不保证无碰撞。
- 旧周报缺来源时按已批准规则局部降级头条/中奖者名称，数据库不回写；不扩展历史数据修复。
- 没有修改业务代码/测试；本轮只改BOTERO_VERSION与对应文档。临时浏览器脚本与截图不入仓库；未暂存任何文件。外部独立审查仍由主管安排。

## 仓库与规范检查

- `openspec validate --all --strict`：**18 passed, 0 failed**（含三个独立提案），退出0；日志 `C:/Users/SC2_j/AppData/Local/Temp/botero_final_acceptance_ish85n9_/openspec.log`。
- `git diff --check`：最终通过。此前CRLF新增行被报尾随空白，主管仅将 `core/gen_image/__init__.py` 与 `test/test_gen_image.py` 换行统一为LF，文本逻辑未变；随后图片定向回归44项通过。最终独立复审通过，活动列表匿名及时间线空页停载两项发现均已修复并补回归。
- 本轮版本/文档路径单独 `git diff --check -- core/config.py CHANGELOG.md kb/QUICK_REFERENCE.md kb/PLUGIN_CATALOG.md specs/plugin-catalog.md specs/web-gallery.md specs/timeline-protocol.md specs/image-generation.md` 通过；未跟踪提案文档另以文本尾空格检查覆盖。
- `git diff --cached --name-only` 无输出：无暂存文件。未 commit/push/archive。已按 specs/README 的插件行为同步要求，更新两个插件目录中三个相关条目，未修改指令文本或无关说明。
