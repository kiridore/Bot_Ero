# 验收记录：时间线观看偏好

## 提交授权补记

用户随后明确要求提交并推送到远端。本次将三项个人偏好实现及配套文档作为1.57.0同批提交到dev，不动master；真实QQ水印验收仍待完成，三个提案保持未归档。以下“未提交/禁止提交”等表述为先前验收阶段记录，不再代表本次交付授权。提交前重新运行全量：821 passed（375.03秒）；OpenSpec严格校验18 passed。

## 结论

2026-10-28，与另两提案统一为1.57.0，不安排中间版本。本提案功能验收通过；未提交/推送/归档。同批水印提案真实QQ验收仍待完成，不宣称整批全绿。

| 标准 | 状态 | 证据 |
|---|---|---|
| AC01 | 通过 | `test/test_user_settings.py` 缺省True、持久化；`check_settings_preferences.py` 严格bool与互不覆盖；均纳入全量 |
| AC02 | 通过 | `check_timeline_privacy.py`：关闭后他人checkin消失，本人hidden仍可见、他人非打卡保留、缺省不变；超过5页补取上限仍可继续 |
| AC03 | 通过 | 同脚本验证feed/poll/new一致过滤、未读计数、next_after跨被滤批次、不漏后续；`test/test_timeline_render.js` 验证有cursor的空页自动续读（父专项通过且本轮全量纳入） |
| AC04 | 通过 | `check_timeline_unread.py` 既有未读/回执回归，最终全量纳入 |
| AC05 | 通过 | `python -m pytest -q`：821 passed, 40446 warnings in 372.16s；原API集合独立命令不能代表全量，已修正为实际全量入口 |
| AC06 | 通过（真实浏览器自动操作 + 人工看图） | Chrome打开真实设置页，关闭“在时间线显示他人的打卡”后重新加载保持；真实时间线页面仅本人打卡和两条论坛事件，另一默认账号仍见4条；390px/1440px截图已打开检查 |

## 证据路径与隔离

完整公共执行记录、浏览器脚本、6张截图及环境边界见 [身份提案验收记录](../privacy-identity-display/acceptance.md)。本轮pytest只执行一次，计时外层373.20秒，返回0。

- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\pytest.log`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\pytest_result.json`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\browser_check.py`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\browser_result.json`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\settings-mobile.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\timeline-owner-mobile.png`
- `C:\Users\SC2_j\AppData\Local\Temp\botero_final_acceptance_ish85n9_\timeline-owner-desktop.png`

浏览器运行真实HTML/JS、本地webapp API与临时数据库，不是模拟页面；仅OneBot身份资料模拟，所有相关数据路径经临时BOTERO_CONFIG隔离，未启动bot或发送QQ消息。浏览器检查普通过滤场景；超过服务端补页上限的空页续读由专项API与Node回归验证，不冒充浏览器覆盖。

## 剩余事项

- 功能AC无待验项，T11提交/归档未执行：本轮禁止，且同批水印AC06真实QQ检查尚未完成。
- 观看偏好仅收窄时间线他人打卡，不影响本人hidden、他人非打卡、原作者隐私和群指令。隐藏未读不产生已读回执的既有边界不变。
- 40446条warnings为Python/pytest_asyncio/Pillow弃用提示；未在本任务改依赖或测试。
- 不改源码/测试，不新增通用事件过滤框架，不修改数据库；独立审查由主管安排。

## 仓库与规范检查

- `openspec validate --all --strict`：**18 passed, 0 failed**（含三个独立提案），退出0；日志 `C:/Users/SC2_j/AppData/Local/Temp/botero_final_acceptance_ish85n9_/openspec.log`。
- `git diff --check`：最终通过。此前CRLF新增行被报尾随空白，主管仅将 `core/gen_image/__init__.py` 与 `test/test_gen_image.py` 换行统一为LF，文本逻辑未变；随后图片定向回归44项通过。最终独立复审通过，活动列表匿名及时间线空页停载两项发现均已修复并补回归。
- 本轮版本/文档路径单独 `git diff --check -- core/config.py CHANGELOG.md kb/QUICK_REFERENCE.md kb/PLUGIN_CATALOG.md specs/plugin-catalog.md specs/web-gallery.md specs/timeline-protocol.md specs/image-generation.md` 通过；未跟踪提案文档另以文本尾空格检查覆盖。
- `git diff --cached --name-only` 无输出：无暂存文件。未 commit/push/archive。已按 specs/README 的插件行为同步要求，更新两个插件目录中三个相关条目，未修改指令文本或无关说明。
