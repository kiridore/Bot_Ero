# Spec: 图片生成

> 关联规范: [plugins.md](plugins.md) | [web-gallery.md](web-gallery.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-10-28（1.57.0：图片身份与个人水印；真实QQ视觉验收待完成）

---

## Constraint: 模块结构

`core/gen_image/` 是基于 Pillow 的图片生成子系统；绘图完全本地，真实头像获取可依赖外部请求，隐藏身份时禁止获取真实头像。

```
core/gen_image/
  __init__.py          ← 便捷导出和编排函数
  models.py            ← 数据模型 (PersonalRecordStats)
  year_heatmap.py      ← 年度热度图渲染
  profile_card.py      ← 完整档案卡生成
  rank_card.py         ← 多人排行榜/打卡板（不接受水印参数）
  identicon.py         ← 确定性几何头像
  watermark.py         ← 纯 PIL 单主体平铺水印
  avatar_helper.py     ← 头像裁剪（圆形遮罩）
  fonts.py             ← 字体加载（跨平台回退）
  heatmap_colors.py    ← 热度图颜色映射
```

---

## Constraint: 数据模型 (`models.py`)

```python
@dataclass(frozen=True)
class PersonalRecordStats:
    year: int
    total_distinct_days: int     # 打卡总天数
    total_checkin_images: int    # 打卡总图片数
    current_weekly: int          # 当前连续周数
    longest_weekly: int          # 最长连续周数
    current_daily: int           # 当前连续天数
    longest_daily: int           # 最长连续天数
    points: int                  # 当前积分
```

不可变数据类（`frozen=True`），仅用于数据传输。

---

## Constraint: 年度热度图 (`year_heatmap.py`)

GitHub 风格的打卡热度图（12 个月网格布局）。

### 主函数

```python
def render_year_heatmap(
    year: int,
    day_checkin_count: list[int],  # 366 格，索引为 day_of_year - 1
    *,
    include_heading: bool = True,
) -> Image.Image:
```

### 颜色映射 (`heatmap_colors.py`)

```python
def github_green_level(val: int) -> tuple[int, int, int]:
    # val == -1  → (255, 223, 186)  桃色（补救日）
    # val == 0   → (235, 237, 240)  浅灰（无打卡）
    # val == 1   → (198, 228, 139)  浅绿
    # val == 2   → (123, 201, 111)  中绿
    # val == 3   → (35, 154, 59)    深绿
    # val > 3    → (25, 97, 39)     最深绿
```

### 布局常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `CELL` | 18 | 格子尺寸 (px) |
| `PAD` | 4 | 格子间距 (px) |
| `LEFT_MARGIN` | 80 | 左边距 |
| `TOP_MARGIN` | 60 | 上边距 |
| `TODAY_OUTLINE` | `(212, 175, 55)` | 当天高亮边框（金色） |
| `BG` | `(245, 245, 245)` | 背景色 |

### 布局

- 12 个月按 3×4 网格排列
- 每周为一列（Sunday–Saturday）
- 当天格子用金色圆角矩形高亮
- `include_heading=True` 时顶部渲染标题

---

## Constraint: 档案卡 (`profile_card.py`)

组合热度图 + 统计信息 + 头像，生成完整档案图片。

### 主函数

```python
def build_personal_record_image(
    year: int,
    day_checkin_count: list[int],
    stats: PersonalRecordStats,
    *,
    user_display_name: str,
    avatar: Image.Image | None = None,
) -> Image.Image:

def save_personal_record_png(user_id: int, image: Image.Image) -> str:
    # 保存到 {python_data_path}/personal_records/{user_id}_calendar_heatmap_monthly.png
```

### 布局常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `CARD_BG` | `(245, 245, 245)` | 卡片背景 |
| `TEXT_MAIN` | `(45, 45, 45)` | 主文字颜色 |
| `TEXT_DIM` | `(110, 110, 110)` | 次要文字颜色 |
| `SEPARATOR` | `(210, 210, 210)` | 分隔线颜色 |
| `AVATAR_SIZE` | 56 | 头像尺寸 |
| `FOOTER_TEXT` | `f"Powered by {NICKNAME}"` | 底部署名，与用户平铺水印独立 |

### 布局流程

1. 顶部：头像（圆形裁剪）+ 用户名 + 年份
2. 中部：统计信息（打卡天数、图片数、连续周/天数、积分）
3. 底部：年度热度图
4. 最底部：水印文字

---

## Constraint: 头像处理 (`avatar_helper.py`)

```python
def raster_circle_avatar_on_rgb(
    im: Image.Image,
    size: int,
    *,
    background: tuple[int, int, int] = (245, 245, 245),
) -> Image.Image:
```

- LANCZOS 缩放至 `(size, size)`
- 创建圆形 Alpha 遮罩
- 合成到纯色 RGB 背景上

---

## Constraint: 字体加载 (`fonts.py`)

```python
def load_font(size: int) -> FontType:
    # 尝试顺序:
    # 1. Windows: msyh.ttc, msyhbd.ttc, simhei.ttf
    # 2. Linux: wqy-microhei.ttc, NotoSansCJK-Regular.ttc
    # 3. 裸文件名
    # 4. PIL 默认字体

def truncate_text(draw, text: str, font, max_width: float) -> str:
    # 超出宽度用 "..." 截断
```

**跨平台兼容:** 字体通过 `os.path.join` 拼接常见系统路径并回退。

---

## Constraint: 集成点

### Bot 端

- `plugins/personal_records/__init__.py::PersonalRecords`：响应 `/档案 [年份]`，生成后通过现有 API 发送 @ 与图片，群聊/私聊目标保持不变。
- `plugins/personal_records/events.py::_render_card` / `send_registration_card`：注册完成通知生成档案卡，经现有输出模块私聊真实账号；公开时保留 `str(uid)` 显示名，不新增外部昵称依赖。
- `plugins/leaderboard`、`plugins/week_list`：构建 `RankRow` 时逐行判断身份开关，随后调用 `render_rank_card` / `save_rank_png`。图片失败的文字回退仍使用原姓名列表，不改变 bot 文字。

**四个图片入口均为可传播产物，无网站本人豁免。** `core.user_settings.identity_public(uid)` 缺省 True；关闭时图上名称取 `anonymous_name(uid)`，头像取 `core.gen_image.identicon.generate_identicon(uid)`，不得获取真实头像。两种档案入口的卡头与水印使用同一名称，实际账号仍用于数据查询、文件名与消息目标。

### Web 端

`webapp/profile/profile_service.py::build_profile()` 返回统计与热力图数据，不调用此 PNG 生成流程。用户上传原图、缩略图不因本水印设置而变更。

---

## Constraint: 单主体水印编排

```python
def gen_personal_record_card(
    year: int,
    day_checkin_count: list[int],
    user_id: int,
    stats: PersonalRecordStats,
    *,
    user_display_name: str | None = None,
    avatar=None,
    watermark_text: str | None = None,
) -> str:
    # 构建卡片 → 非 None 时 apply_watermark → 保存 PNG
```

- 绘图层 MUST NOT 读取用户设置。`watermark_text=None` 保持旧调用输出；两个插件入口读取 `watermark_enabled(uid)`（缺省 True），开启传主体展示名，关闭传 None。
- `watermark.py::apply_watermark(image, text)` 返回新图，不改变原图；复用字体，固定 45°、白色 alpha=64/255、相邻行横向错半周期交错平铺，不增加配置或依赖。
- 超长名称先限 128 字符，再按半幅图宽省略；限制字体测量与旋转画布资源。卡头和水印都来源于同一展示名，可按各自布局省略。
- 多人排行榜不接受水印参数、不调用水印函数；上传照片不变。底部署名与用户平铺水印相互独立，关闭平铺水印不删除底部署名。
- 真实背景是 `(245,245,245)`。实际样图中白字在绿色热力格上可见、浅灰空白处很淡；MUST NOT 以像素差代替视觉验收，不改底色、不加暗描边。
- 回归：`test/test_gen_image.py` 验证水印样式/确定性/长中文名资源与旧签名；`test/test_generated_image_privacy.py` 实际执行四入口，验证公开默认、匿名头像、两档案水印设置和真实发送目标、多人图无水印与原文字回退。

---

## Constraint: 输出路径

```
server_data/
  personal_records/
    {user_id}_calendar_heatmap_monthly.png   ← 档案卡保存位置
```

每次请求重新生成（不缓存），文件被覆盖。
