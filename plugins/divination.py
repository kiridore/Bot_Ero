import random

from core.base import Plugin
from core.cq import text


class DivinationPlugin(Plugin):
    def match(self, message_type):
        return self.on_full_match("/占卜")

    def handle(self):
        cards = [
            ("愚者", "新的开始，勇敢迈步"),
            ("魔术师", "资源到位，行动力增强"),
            ("女祭司", "先观察，答案在直觉里"),
            ("皇后", "滋养关系，照顾好自己"),
            ("皇帝", "建立秩序，稳住节奏"),
            ("教皇", "遵循原则，借力规则"),
            ("恋人", "重要选择，重视真心"),
            ("战车", "专注目标，推进到底"),
            ("力量", "柔韧胜过蛮力"),
            ("隐者", "短暂停步，整理方向"),
            ("命运之轮", "转机临近，顺势而为"),
            ("正义", "保持公平，承担结果"),
            ("倒吊人", "换个视角，等待时机"),
            ("死神", "旧阶段结束，新阶段开始"),
            ("节制", "平衡节奏，循序渐进"),
            ("恶魔", "警惕执念，避免内耗"),
            ("高塔", "突发变化，先稳后动"),
            ("星星", "保持希望，逐步恢复"),
            ("月亮", "信息未明，先别冲动"),
            ("太阳", "状态上扬，适合发力"),
            ("审判", "总结复盘，做出决定"),
            ("世界", "阶段圆满，开启新章"),
        ]
        card_name, meaning = random.choice(cards)
        direction = random.choice(["正位", "逆位"])

        if direction == "逆位":
            meaning = "当前阻力较大，建议放慢节奏并复盘"

        self.api.send_msg(
            text(
                "*洗牌中...*\n"
                f"你抽到了：{card_name}（{direction}）\n"
                f"解读：{meaning}"
            )
        )
