# 任务：隐私·昵称与头像公开开关

对应验收标准见 proposal.md；逐项完成并全绿后方可归档。勾选仅表示已实际验证，不把共享基础或网站阶段视为完整提案交付。

- [x] T1 `core/user_settings.py`：新增 `identity_public()`、`anonymous_name()`、`display_identity()`；模块文档字符串补键说明（AC01，共享基础已有实现，本阶段复验）
- [x] T2 `test/test_user_settings.py`：缺省 True、匿名名确定性、`display_identity` 网站本人豁免（AC01）
- [x] T3 `core/gen_image/identicon.py`：确定性 identicon 生成（PIL，网站/bot 共用）（AC02，共享基础已有实现，本阶段复验）
- [x] T4 `test/test_identicon.py`：确定性/选定样本区分度/合法 PNG，不保证全域无碰撞（AC02）
- [x] T5 `webapp/app.py`：`GET /identicon/{user_id}.png` 端点（登录范围内；共享基础已有实现，check_settings_preferences.py 经 API suites 复验）
- [x] T6 `webapp/timeline/app.py`：`_serialize_rows` users dict 接 `display_identity`（作者 + 占位符一次覆盖，不加入观看过滤）（AC03）
- [x] T7 论坛、相册、活动、闹钟、直播、工具、TRPG、周报展示面接 `display_identity`；相册区分筛选用户与查看者，论坛回复对象同步处理，TRPG 保留 char_public 权限（AC03）
- [x] T8 `plugins/leaderboard`、`plugins/week_list`：行级判定，关闭者匿名名 + identicon、不拉真实头像，文字回退不变（AC04）
- [x] T9 `test/test_generated_image_privacy.py -k rank`：实际执行排行榜/打卡板入口，行级匿名、匿名者不拉头像、无水印、文字回退不变；`test/test_gen_image.py` 保留绘图回归（AC04 的入口验证使用此新增文件）
- [x] T10 `test/scripts/check_identity_privacy.py`：独立进程集成脚本，覆盖全部网站面本人/他人及默认公开；用 `_env.write_config` 隔离全部路径、模拟 OneBot、不真实网络（AC03、AC08）
- [x] T11 `webapp/static/settings.js`：隐私分组新开关 + 提示文案；真实 Chrome 操作设置、刷新保持、切换查看者验证姓名/图案，人工打开390px及桌面截图（AC07；临时真实 API 环境，OneBot来源模拟）
- [x] T12 网站回归：`python -m pytest test/test_webapp_api_suites.py -q`，包含 check_profile_checkins.py、check_settings_preferences.py 与新增身份脚本（AC05、AC09；不是全量回归）
- [x] T13 同批版本文档：CHANGELOG `[1.57.0]` + `BOTERO_VERSION` + `kb/QUICK_REFERENCE.md` 个人设置键清单；网站/时间线/图片规范及插件目录同步（尚未提交，交付操作见T18）
- [x] T14 两个档案图入口 `/档案` 与注册图均遵守图片身份开关，不以本人触发豁免；`test/test_generated_image_privacy.py` 实测参数、图案头像、真实发送目标，注册公开名仍为账号字符串（AC10，结合既有 test_register_flow.py/test_gen_image.py）
- [x] T15 最终全量回归 `python -m pytest -q`：821 passed，372.16秒（AC06；只运行一次，证据见acceptance.md）
- [x] T16 周报响应深拷贝处理结构化身份；按中奖来源重建大奖/三等奖头条，完整无人中奖来源保持原样；仅需匿名时重建，正文与原数据不变（AC08）
- [x] T17 旧周报缺来源只降级整个头条；缺失/非法 user_id 的中奖者 name 为“身份资料缺失”，有效 ID 仍按查看者处理；补本人/他人、缺字段及存储不变测试（AC08）

- [ ] T18 同批验收完成后提交并归档：本轮禁止 commit/push/archive；水印提案真实QQ检查未完成，保持未归档

## 最终集成验收

1.57.0 同批发布裁定见 proposal.md/design.md；逐条证据见 acceptance.md。网站真实 Chrome/API 联动与人工截图检查已完成，全量821通过。以下为此前阶段的历史记录，其“尚未”只描述当时状态，不覆盖最终记录。

## 执行 Ruling 与阶段证据

网站本人豁免与可传播图片规则分别表述；设置文件无扩展名、新增布尔严格校验、图案碰撞边界和最终全量命令均按源码事实修正。完整裁定见 proposal.md / design.md 的“执行 Ruling：网站身份与历史周报兼容”。不改数据库姓名，不做昵称全文替换，保留原始 ID，本功能不是安全匿名化。

已执行：独立身份脚本通过；共享设置与图案单测 15 passed；API suites 17 passed（包含既有回归及新增脚本）。首次 API 集合命令因 200 秒外层限时中断，增加命令限时后完整通过。该网站阶段未执行图片、页面手测、最终全量与版本交付；未 commit/push/archive。

图片阶段补充：`python -m pytest test/test_gen_image.py test/test_generated_image_privacy.py test/test_register_flow.py test/test_user_settings.py test/test_identicon.py -q` → **65 passed**。已覆盖四个图片入口、公开缺省/隐藏、水印缺省/关闭、匿名不取真实头像、发送目标及文字回退不变；因此勾选 T8/T9/T14。本地公开/匿名档案样图已 read 检查，浅底白字很淡；浏览器/真实 QQ 手测、最终全量与版本交付仍未执行，未勾选对应任务。不 commit/push/archive。
