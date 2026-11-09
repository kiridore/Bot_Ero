# 任务：生成图水印

前置依赖：共享设置与 `privacy-identity-display` 的匿名名/图案头像已有实现，本阶段完成 bot 图片部分。勾选只代表实际可验证的实现，不将图片检查替代浏览器或真实 QQ 手测。

- [x] T1 `core/gen_image/watermark.py`：纯 PIL `apply_watermark()`，45°、交错平铺、半透明白字、常量集中；长名称有界处理（AC01、AC07）
- [x] T2 `core/gen_image/__init__.py`：`gen_personal_record_card` 新增可选 `watermark_text=None`，保存前叠加，旧调用兼容（AC01）
- [x] T3 `plugins/personal_records/__init__.py` 与 `events.py`：两个入口读取 `watermark_enabled()` 和身份开关；卡头/水印同名、匿名头像且不取真实头像；不改变真实发送目标（AC03、AC08）
- [x] T4 `core/user_settings.py`：共享基础已有 `watermark_enabled()` 和键文档，本阶段复验，不重复修改（AC04）
- [x] T5 `test/test_gen_image.py` 与 `test/test_generated_image_privacy.py`：叠加/关闭/确定性/45°交错/长中文名/旧调用、四入口参数与发送目标、多人卡逐行匿名且无水印、文字回退不变（AC01–AC03、AC07–AC08）
- [x] T6 `test/test_user_settings.py`：共享基础已有缺省 True、持久化和非法值测试，本阶段复验（AC04）
- [x] T7 `webapp/static/settings.js`：“图片水印”分组 + 开关 + 文案，源码核对共享基础已有实现；页面手测另列 T10，不能据此标记 AC06 通过
- [x] T8 最终全量回归：`python -m pytest -q` → 821 passed，372.16秒（AC05；最终集成只运行一次）
- [x] T9 同批1.57.0版本文档：CHANGELOG + `BOTERO_VERSION` + `kb/QUICK_REFERENCE.md` 键清单，图片规范/插件目录同步；尚未提交
- [ ] T10 浏览器设置与真实 QQ `/档案`、注册图手测（AC06）：真实 Chrome 开关关闭/开启及刷新保持已完成；真实QQ群聊、私聊档案与注册图未测，不能勾选整体完成
- [x] T11 生成并 read 公开、匿名、无水印真实档案卡样图，记录浅底白字可见性限制（仅本地视觉检查，不等于 AC06）

- [ ] T12 同批验收全绿后提交并归档；本轮禁止 commit/push/archive，AC06真实QQ部分未完成

## 最终集成验收

目标版本统一1.57.0，三个独立提案同批发布，不另设中间版本。完整裁定见 proposal.md/design.md；最终全量和浏览器证据见 acceptance.md。模拟发送只证明目标账号与参数，不代表真实QQ可达或视觉效果，AC06保持待验收。

## 定向验证证据

命令：`python -m pytest test/test_gen_image.py test/test_generated_image_privacy.py test/test_register_flow.py test/test_user_settings.py test/test_identicon.py -q` → **65 passed**。首轮新增入口断言把既有 @ 账号整数误写为字符串，修正测试后通过，生产消息结构未改。数据和设置目录隔离、网络与发送模拟。

样图（已有忽略目录，非版本文件）：
- `test/gen_image_output/watermark_baseline.png`
- `test/gen_image_output/watermark_public.png`
- `test/gen_image_output/watermark_anonymous.png`

已实际打开上述 PNG：白字在绿色格子上可见，在 `(245,245,245)` 浅灰空白区很淡。保持白色/透明度、不改底色或加暗描边；不声称防盗可读性已通过真实客户端验收。
