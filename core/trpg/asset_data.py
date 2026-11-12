"""COC 7th 资产参考表：抄录自 docs/COC7空白卡CY26.3.xlsx「资产及物价参考」工作表。

每个币种/时代有六档生活水平，信用评级区间固定为：
  身无分文 0 ｜ 拮据 1-9 ｜ 标准 10-49 ｜ 小康 50-89 ｜ 富裕 90-98 ｜ 富豪 99

每档给出三项（现金 / 其他资产 / 消费水平），写法三种：
  ("flat", 数值)   固定值
  ("x", 数值)      信用评级 × 数值
  ("text", "…")    无法直接参与计算的写法（如维多利亚时代的「5先令」）

重新生成方式：读该工作表第 6–13 行与 15–22 行，按币种分块取
（生活水平 / 信用评级 / 现金 / 其他资产 / 消费水平）五列。
"""

LEVELS = [
    {"name": "身无分文", "min": 0, "max": 0},
    {"name": "拮据", "min": 1, "max": 9},
    {"name": "标准", "min": 10, "max": 49},
    {"name": "小康", "min": 50, "max": 89},
    {"name": "富裕", "min": 90, "max": 98},
    {"name": "富豪", "min": 99, "max": 99},
]

CURRENCIES = [
    {
        "code": "JPY", "label": "日元（JPY）", "era": "2010s 日本",
        "rows": {
            "身无分文": {"cash": ("flat", 1000), "other": ("flat", 0), "spending": ("flat", 500)},
            "拮据": {"cash": ("x", 2000), "other": ("x", 20000), "spending": ("flat", 2000)},
            "标准": {"cash": ("x", 4000), "other": ("x", 150000), "spending": ("flat", 25000)},
            "小康": {"cash": ("x", 12000), "other": ("x", 1000000), "spending": ("flat", 100000)},
            "富裕": {"cash": ("x", 75000), "other": ("x", 6000000), "spending": ("flat", 500000)},
            "富豪": {"cash": ("flat", 30000000), "other": ("flat", 30000000000), "spending": ("flat", 2000000)},
        },
    },
    {
        "code": "CNY", "label": "人民币（CNY）", "era": "2010s 中国",
        "rows": {
            "身无分文": {"cash": ("flat", 100), "other": ("flat", 0), "spending": ("flat", 50)},
            "拮据": {"cash": ("x", 100), "other": ("x", 1000), "spending": ("flat", 100)},
            "标准": {"cash": ("x", 200), "other": ("x", 5000), "spending": ("flat", 1000)},
            "小康": {"cash": ("x", 500), "other": ("x", 40000), "spending": ("flat", 5000)},
            "富裕": {"cash": ("x", 3000), "other": ("x", 250000), "spending": ("flat", 20000)},
            "富豪": {"cash": ("flat", 1000000), "other": ("flat", 1000000000), "spending": ("flat", 100000)},
        },
    },
    {
        "code": "USD", "label": "美元（USD，现代）", "era": "现代 美国",
        "rows": {
            "身无分文": {"cash": ("flat", 10), "other": ("flat", 0), "spending": ("flat", 10)},
            "拮据": {"cash": ("x", 20), "other": ("x", 200), "spending": ("flat", 40)},
            "标准": {"cash": ("x", 40), "other": ("x", 1000), "spending": ("flat", 200)},
            "小康": {"cash": ("x", 100), "other": ("x", 10000), "spending": ("flat", 1000)},
            "富裕": {"cash": ("x", 400), "other": ("x", 40000), "spending": ("flat", 5000)},
            "富豪": {"cash": ("flat", 1000000), "other": ("flat", 100000000), "spending": ("flat", 100000)},
        },
    },
    {
        "code": "USD1920", "label": "美元（USD，1920s）", "era": "1920s 美国",
        "rows": {
            "身无分文": {"cash": ("flat", 0.5), "other": ("flat", 0), "spending": ("flat", 0.5)},
            "拮据": {"cash": ("x", 1), "other": ("x", 10), "spending": ("flat", 2)},
            "标准": {"cash": ("x", 2), "other": ("x", 50), "spending": ("flat", 10)},
            "小康": {"cash": ("x", 5), "other": ("x", 500), "spending": ("flat", 50)},
            "富裕": {"cash": ("x", 20), "other": ("x", 2000), "spending": ("flat", 250)},
            "富豪": {"cash": ("flat", 50000), "other": ("flat", 5000000), "spending": ("flat", 5000)},
        },
    },
    {
        "code": "GBP", "label": "英镑（GBP，维多利亚）", "era": "维多利亚时代 英国",
        "rows": {
            "身无分文": {"cash": ("text", "5先令"), "other": ("flat", 0), "spending": ("text", "5便士")},
            "拮据": {"cash": ("x", 1), "other": ("x", 10), "spending": ("text", "20先令")},
            "标准": {"cash": ("x", 10), "other": ("x", 20), "spending": ("text", "2镑10先令")},
            "小康": {"cash": ("x", 12), "other": ("x", 200), "spending": ("flat", 15)},
            "富裕": {"cash": ("x", 50), "other": ("x", 500), "spending": ("flat", 50)},
            "富豪": {"cash": ("flat", 150000), "other": ("flat", 300000), "spending": ("flat", 250)},
        },
    },
    {
        "code": "AUD", "label": "澳元（AUD）", "era": "2010s 澳大利亚",
        "rows": {
            "身无分文": {"cash": ("flat", 10), "other": ("flat", 0), "spending": ("flat", 10)},
            "拮据": {"cash": ("x", 15), "other": ("x", 110), "spending": ("flat", 35)},
            "标准": {"cash": ("x", 30), "other": ("x", 500), "spending": ("flat", 140)},
            "小康": {"cash": ("x", 75), "other": ("x", 900), "spending": ("flat", 700)},
            "富裕": {"cash": ("x", 350), "other": ("x", 30000), "spending": ("flat", 4000)},
            "富豪": {"cash": ("flat", 1000000), "other": ("flat", 9000000), "spending": ("flat", 80000)},
        },
    },
]

# 其他资产表的五个分类（人物卡 69 行）
ASSET_ITEM_FIELDS = [
    ("vehicle", "交通工具"),
    ("residence", "住所"),
    ("luxury", "奢侈品"),
    ("securities", "股票/证券等"),
    ("other", "其他"),
]
