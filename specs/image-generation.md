# Spec: 图片生成

> 关联规范: [plugins.md](plugins.md) | [web-gallery.md](web-gallery.md)
> 父文档: [CLAUDE.md](../CLAUDE.md)
> 最后更新: 2026-06-29

---

## Constraint: 模块结构

`core/gen_image/` 是基于 Pillow 的图片生成子系统，完全本地渲染，无外部服务依赖。

```
core/gen_image/
  __init__.py          ← 便捷导出和编排函数
  models.py            ← 数据模型 (PersonalRecordStats)
  year_heatmap.py      ← 年度热度图渲染
  profile_card.py      ← 完整档案卡生成
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
    day_checkin_count: dict[int, int],  # {day_of_year: count}
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
    day_checkin_count: dict[int, int],
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
| `FOOTER_TEXT` | `"Power by 小埃同学"` | 底部水印 |

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

`plugins/personal_records.py` 的 `PersonalRecords` 插件：
- 响应 `/档案 [年份]` 命令
- 调用 `gen_personal_record_card()` 生成档案卡
- 通过 `self.api.send_msg(image(path))` 发送

### Web 端

`checkin_gallery/profile_service.py` 的 `build_profile()`：
- 调用相同的 `gen_image` 模块
- 返回图片路径供前端展示

---

## Constraint: 输出路径

```
server_data/
  personal_records/
    {user_id}_calendar_heatmap_monthly.png   ← 档案卡保存位置
```

每次请求重新生成（不缓存），文件被覆盖。
