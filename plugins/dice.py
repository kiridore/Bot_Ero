import random
import re

from core.base import Plugin
from core.cq import text


from core.utils import register_plugin
@register_plugin
class DicePlugin(Plugin):
    name = 'roll_dice'
    description = '按 .rXdY 格式掷骰子并返回结果。'

    PATTERN = re.compile(r"^\.r(\d+)d(\d+)$", re.IGNORECASE)

    def match(self, message_type):
        if message_type != "message":
            return False
        message = self.bot_event.message
        if len(message) != 1:
            return False
        seg = message[0]
        if seg.get("type") != "text":
            return False
        msg = seg.get("data", {}).get("text", "").strip()
        return self.PATTERN.match(msg) is not None

    def handle(self):
        msg = self.bot_event.message[0].get("data", {}).get("text", "").strip()
        m = self.PATTERN.match(msg)
        a = int(m.group(1))
        b = int(m.group(2))
        if a <= 0 or b <= 0:
            self.api.send_msg(text("骰子数量和面数都必须大于0"))
            return
        if a > 100 or b > 1000:
            self.api.send_msg(text("为了防止刷屏，限制为最多100个骰子、1000面"))
            return

        values = [random.randint(1, b) for _ in range(a)]
        total = sum(values)
        self.api.send_msg(text(".r{}d{}\n结果：{}\n总和：{}".format(a, b, " + ".join(map(str, values)), total)))
