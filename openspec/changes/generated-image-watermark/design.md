# 设计：生成图水印

## 关键决策与依据

1. **键名 `watermark.enabled`，缺省 True**：所有者裁定默认开启（Q5:B，全员防盗）；独立顶层分组（非 privacy——水印是署名不是隐私）。
2. **作用面 = 单主体生成卡**：当前为个人档案卡的两个入口（`plugins/personal_records/__init__.py` 的 `/档案` 与 `events.py` 的注册图 → `core/gen_image.gen_personal_record_card`）。多人卡（排行榜/打卡板）排除——整图平铺水印只承载一个名字（所有者 Q4:A）。判定方式：`gen_image` 公开函数新增可选参数 `watermark_text: str | None`，只有单主体生成函数接受它；多人卡函数不暴露该参数，从接口上排除误用。
3. **gen_image 保持纯粹**：`core/gen_image/watermark.py::apply_watermark(img, text) -> Image` 只做叠加；设置读取与文字决定（真实名 vs 匿名名）在插件侧完成——两个入口均读 `core.user_settings.watermark_enabled(uid)` 与 `identity_public(uid)`，传入展示名或 None。公开的 `/档案` 保留现有名称，公开注册图保留 `str(uid)`；隐藏时卡头与水印都用 `anonymous_name(uid)`，头像用 `generate_identicon(uid)`，不取真实头像。可传播图片无网站本人豁免。`watermark_text=None` 为绘图函数默认值，旧调用不受影响；用户默认开启由插件传参实现。
4. **样式实现**（固定常量）：RGBA 覆盖层上以 `core/gen_image/fonts.py` 取字体，字号随图宽比例；单行文字先渲染再旋转 45°（`Image.rotate(expand=True)`），按行距平铺、每行横向错位半周期；白色、alpha 固定 64/255；`Image.alpha_composite` 合成并保持输入图尺寸/模式、不修改原图。字体复用 `load_font`，间距等常量集中在本模块顶部。水印文字先限定 128 字符，再复用 `truncate_text` 按半幅图宽省略，避免超长昵称造成无界文字测量与旋转画布；和卡头一样允许显示省略号，但两者使用同一身份名称。实际 `CARD_BG=(245,245,245)`，空白处白字对比很低，不能据像素变化宣称可见性验收通过。
5. **确定性**：无随机成分；同名称同图幅输出一致，便于测试断言（与基线逐像素比较）。
6. **设置页**：共享基础已在 `webapp/static/settings.js` 实现“图片水印”开关，文案为“在我的个人生成图上加水印”；读写走 `/api/me/settings`。`SettingsIn` 与存储层均严格校验新增布尔值，不能以旧 dict 模型假设自动放行。本图片阶段不修改网站与共享设置。
7. **bot 读个人设置**：与提案 1 相同，`core/user_settings.py` 进程无关，插件直接 import。

## 不做的事

- 不给缩略图/原图服务加任何变换（所有者定义限生成图）。
- 不做暗色/亮色自适应，不改浅灰底、不加暗描边。白字在绿色格子上可辨，浅灰空白处很淡；这是实际 read 样图检查的限制，不承诺防盗效果。
- 不缓存水印层（生成即弃；文字测量和画布大小有界，有长中文名测试）。
- 不改 bot 文字或发送目标。两种排行榜只在构建图片行时匿名，保留原 entries 供图片失败后的文字回退；不接受水印参数。

## 验证边界

`test/test_generated_image_privacy.py` 实际执行四个入口并生成图片，隔离设置/输出目录，模拟头像请求与发送；验证两个档案入口的展示参数、公开默认与关闭水印、真实发送目标，以及榜单逐行匿名/无水印/文字回退。`test/test_gen_image.py` 验证绘图、长中文名资源边界与旧调用兼容，并输出 `test/gen_image_output/watermark_{baseline,public,anonymous}.png`。

已 read 三张实际 PNG；最终回归与浏览器证据见 acceptance.md。真实QQ仍未验收，不能由脚本或图片像素差替代。

## 执行 Ruling：1.57.0 同批个人偏好发布与验收边界

- 三个独立提案 `privacy-identity-display`、`timeline-feed-preference`、`generated-image-watermark` 保留各自能力与验收标准，但作为同一批个人偏好变更统一发布 **1.57.0**（基线1.56.0）；原先按实施顺序写出的中间版本安排作废，不代表曾发布或需要分别发布。
- 代码、版本及文档在同批交付中同步；本次仅更新版本与文档、执行验证，不 commit/push/archive。不得因自动测试通过而删除真实客户端验收标准。
- 网站本人豁免与可传播 bot 图片不豁免分别适用；匿名身份只隐藏昵称头像，不隐藏账号关联、不替换用户正文或回写历史数据。两种多人图只逐行匿名、无水印；两个个人档案入口共用展示身份与水印规则，上传原图不变。
- 实际 Chrome + 临时配置/数据库 + 本地 webapp API 的联动与截图检查可以验证网站行为；OneBot身份资料/发送模拟不等于真实QQ客户端。真实QQ群聊、私聊档案及注册图视觉验收仍保留待验收，不归档。逐条证据与剩余事项见 [acceptance.md](acceptance.md)。
