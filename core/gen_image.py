from genericpath import exists
import os
from PIL import Image, ImageDraw, ImageFont
import datetime
import math

# =====================
# 配置
# =====================
cell_size = 18      # 每个格子大小
padding = 4         # 格子间距
month_padding_x = 40  # 月份之间的水平间距
month_padding_y = 40  # 月份之间的垂直间距
bg_color = (245, 245, 245)  # 背景颜色


# =====================
# 颜色函数 (GitHub 风格)
# =====================
def get_github_green(max_value, val):
    if val == 0:
        return (235, 237, 240)  # 浅灰
    colors = [
        (198, 228, 139),
        (123, 201, 111),
        (35, 154, 59),
        (25, 97, 39)
    ]
    if val-1 > 3:
        return colors[3]
    else:
        return colors[val-1]

def gen_year_heatmap(year, data, user_id):
# 生成示例数据（每天一个值）
    start_date = datetime.date(year, 1, 1)
    days_in_year = 366 if ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)) else 365
# =====================
# 计算每个月的布局
# =====================
    months_data = {}
    current_day_idx = 0
    for month in range(1, 13):
        month_start = datetime.date(year, month, 1)
        month_days = (datetime.date(year, month + 1, 1) - month_start).days if month != 12 else (datetime.date(year + 1, 1, 1) - month_start).days
        month_vals = data[current_day_idx:current_day_idx + month_days]
        months_data[month] = (month_start, month_vals)
        current_day_idx += month_days

# 每个月的宽度：周数 * (cell_size + padding)
    month_widths = {}
    month_heights = {}
    for month, (month_start, month_vals) in months_data.items():
        first_weekday = month_start.weekday()  # 周一=0
        total_cells = len(month_vals) + first_weekday
        weeks = math.ceil(total_cells / 7)
        month_widths[month] = weeks * (cell_size + padding) - padding
        month_heights[month] = 7 * (cell_size + padding) - padding

# =====================
# 计算画布大小 (按3列 × 4行的月历)
# =====================
    cols = 3
    rows = 4
    width = sum([max(month_widths[m] for m in range(c + 1, 13, cols)) for c in range(cols)]) + (cols - 1) * month_padding_x
    height = sum([max(month_heights[m] for m in range(r * cols + 1, min(r * cols + cols + 1, 13))) for r in range(rows)]) + (rows - 1) * month_padding_y
    width += 80  # 左边留空
    height += 60  # 顶部留空

# =====================
# 绘图
# =====================
    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    try:
        font_month = ImageFont.truetype("arial.ttf", 16)
        font_title = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font_month = ImageFont.load_default()
        font_title = ImageFont.load_default()

# 标题
    title_text = f"{year} Contributions"
    title_w = draw.textlength(title_text, font=font_title)
    draw.text(((width - title_w) // 2, 10), title_text, font=font_title, fill=(50, 50, 50))

# 绘制每个月
    for month in range(1, 13):
        grid_col = (month - 1) % cols
        grid_row = (month - 1) // cols

        # 计算左上角位置
        x_offset = sum([max(month_widths[m] for m in range(c + 1, 13, cols)) for c in range(grid_col)]) + grid_col * month_padding_x + 40
        y_offset = sum([max(month_heights[m] for m in range(r * cols + 1, min(r * cols + cols + 1, 13))) for r in range(grid_row)]) + grid_row * month_padding_y + 50

        month_start, month_vals = months_data[month]
        first_weekday = month_start.weekday()  # 周一=0

        # 月份文字
        month_name = month_start.strftime("%B")
        draw.text((x_offset, y_offset - 20), month_name, font=font_month, fill=(80, 80, 80))

        # 绘制方格
        day_idx = 0
        max_value = max(data) if max(data) > 0 else 1
        for week in range(math.ceil((len(month_vals) + first_weekday) / 7)):
            for day_in_week in range(7):
                if week == 0 and day_in_week < first_weekday:
                    continue
                if day_idx >= len(month_vals):
                    break

                val = month_vals[day_idx]
                color = get_github_green(max_value, val)

                x0 = x_offset + week * (cell_size + padding)
                y0 = y_offset + day_in_week * (cell_size + padding)
                x1 = x0 + cell_size
                y1 = y0 + cell_size

                draw.rounded_rectangle(
                    [x0, y0, x1, y1],
                    radius=4,
                    fill=color,
                    outline=(220, 220, 220)
                )
                day_idx += 1

# 保存
    os.makedirs("./tmp", exist_ok = True)
    image.save("./tmp/{}_calendar_heatmap_monthly.png".format(user_id))
    print("已生成 calendar_heatmap_monthly.png")
