import random

from core.base import Plugin
from core.cq import text


from core.utils import register_plugin
@register_plugin
class DivinationPlugin(Plugin):
    name = 'divination'
    description = '进行一次塔罗占卜。'

    def match(self, message_type):
        return self.on_full_match("/占卜")

    def handle(self):
        cards = [
            "愚者",
            "魔术师",
            "女祭司",
            "皇后",
            "皇帝",
            "教皇",
            "恋人",
            "战车",
            "力量",
            "隐者",
            "命运之轮",
            "正义",
            "倒吊人",
            "死神",
            "节制",
            "恶魔",
            "高塔",
            "星星",
            "月亮",
            "太阳",
            "审判",
            "世界",
        ]
        card_name = random.choice(cards)
        direction = random.choice(["正位", "逆位"])

        self.api.send_msg(
            text(
                "*洗牌中...*\n"
                f"你抽到了：{card_name}（{direction}）"
            )
        )
