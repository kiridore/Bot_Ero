# 验收记录：生成图水印

## 提交授权补记

用户随后明确要求提交并推送到远端。本次将三项个人偏好实现及配套文档作为1.57.0同批提交到dev，不动master；真实QQ水印验收仍待完成，三个提案保持未归档。以下“未提交/禁止提交”等表述为先前验收阶段记录，不再代表本次交付授权。提交前重新运行全量：821 passed（375.03秒）；OpenSpec严格校验18 passed。

## 结论

2026-10-28，与身份公开、时间线观看偏好统一为1.57.0。实现与自动回归通过，浏览器开关联动通过；**AC06真实QQ群聊/私聊档案及注册图仍未验收**，T10保持未勾选，不宣称完整验收、不归档。没有真实QQ发送。

| 标准 | 状态 | 证据 |
|---|---|---|
| AC01 | 通过 | `test/test_gen_image.py` watermark测试：保存图对比、None与旧调用一致、45°/交错/白色半透明/确定性；像素差不等于视觉验收 |
| AC02 | 通过 | `test/test_generated_image_privacy.py -k rank`：两种多人卡逐行匿名、不取真实头像、没有水印调用、文字回退不变 |
| AC03 | 通过（模拟发送） | 同文件watermark_text测试实际执行两个档案入口，覆盖缺省/公开/隐藏身份和缺省/开启/关闭水印；卡头与水印同名，公开注册图仍用账号 |
| AC04 | 通过 | `test/test_user_settings.py` 缺省True与持久化；API严格bool、三组局部更新测试纳入全量 |
| AC05 | 通过 | `python -m pytest -q`：821 passed, 40446 warnings in 372.16s，返回0；本轮只执行一次全量 |
| AC06 | **部分通过，整体待验收** | 真实Chrome页面关闭/开启水印、重新加载保持、真实API写入临时设置JSON均通过；实际渲染样图已由父阶段打开查看。未用真实QQ群聊、私聊运行 `/档案`，未真实接收注册图，不删除此标准 |
| AC07 | 通过 | `test/test_gen_image.py -k long_chinese` 已纳入全量：超长中文名称测量/画布有界、尺寸不变、确定性 |
| AC08 | 通过（模拟发送） | `test_generated_image_privacy.py` 与 `test_register_flow.py`：两入口发送参数仍为实际账号/原群，注册图固定私聊实际账号，未将匿名名用作@目标或文件账号；不等于QQ可达性验收 |

## 证据

此前图片阶段定向命令 `python -m pytest test/test_gen_image.py test/test_generated_image_privacy.py test/test_register_flow.py test/test_user_settings.py test/test_identicon.py -q` 为65 passed；该集合是阶段证据，不能与最终821相加。

最终全量日志与耗时：

- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\pytest.log`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\pytest_result.json`（外层373.20秒，超时限900秒）

浏览器实际API联动：

- 命令：`python C:/Users/SC2_j/AppData/Local/Temp/botero_final_acceptance_ish85n9_/browser_check.py`。
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\browser_result.json`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\settings-desktop.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\settings-mobile.png`

实际Chrome、真实webapp路由、临时SQLite/设置文件，OneBot身份来源模拟；关闭水印与其他两项后重新加载保持，重新开启水印后再加载仍勾选，实际文件值同时验证。截图已人工打开，390px/1440px无横向溢出。未用模拟页面截图代替联动，未启动真实bot、未触真实data.db/server_data、未产生业务外网请求。完整隔离与截图清单见 [公共验收证据](../privacy-identity-display/acceptance.md)。

父阶段已打开检查的真实渲染样图（非QQ客户端截图）：

- `F:\Coding\Python\project\BotEro\test\gen_image_output\watermark_public.png`
- `F:\Coding\Python\project\BotEro\test\gen_image_output\watermark_anonymous.png`
- `F:\Coding\Python\project\BotEro\test\gen_image_output\watermark_baseline.png`

45°交错半透明白字在绿色热力格上可见，在 `(245,245,245)` 浅灰底上很淡。保留已批准样式，不改背景、不加暗描边，不承诺防盗效果。原上传图、缩略图与两种多人图不加此水印。

## 未完成与后续验收条件

- **AC06/T10待验收**：获准使用真实QQ后，分别在群聊、私聊查看 `/档案`，并检查真实注册图；核对公开/隐藏姓名与头像、水印开启/关闭、45°交错白字实际可见程度。浏览器部分已有证据，真实客户端部分不得用模拟发送或像素差代替。
- T12同批提交/归档未执行，本轮明确禁止 commit/push/archive；同批发布不能绕过上述未完成标准。
- 模拟测试验证的是账号参数正确，不证明消息成功送达或QQ压缩后的视觉效果。个人图无网站本人豁免，账号/文件关联与bot文字不隐藏。
- 40446条warnings属于Python/pytest_asyncio/Pillow弃用提示，未在本任务扩大到依赖清理；本轮未修改业务代码或测试，独立审查由主管安排。

## 仓库与规范检查

- `openspec validate --all --strict`：**18 passed, 0 failed**（含三个独立提案），退出0；日志 `C:/Users/SC2_j/AppData/Local/Temp/botero_final_acceptance_ish85n9_/openspec.log`。
- `git diff --check`：最终通过。此前CRLF新增行被报尾随空白，主管仅将 `core/gen_image/__init__.py` 与 `test/test_gen_image.py` 换行统一为LF，文本逻辑未变；随后图片定向回归44项通过。最终独立复审通过，活动列表匿名及时间线空页停载两项发现均已修复并补回归。
- 本轮版本/文档路径单独 `git diff --check -- core/config.py CHANGELOG.md kb/QUICK_REFERENCE.md kb/PLUGIN_CATALOG.md specs/plugin-catalog.md specs/web-gallery.md specs/timeline-protocol.md specs/image-generation.md` 通过；未跟踪提案文档另以文本尾空格检查覆盖。
- `git diff --cached --name-only` 无输出：无暂存文件。未 commit/push/archive。已按 specs/README 的插件行为同步要求，更新两个插件目录中三个相关条目，未修改指令文本或无关说明。
