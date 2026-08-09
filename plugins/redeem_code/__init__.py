from core.base import CommandPlugin
from core.cq import at, text
from core.logger import logger
from core.utils import register_plugin

from .codes import CODE_PATTERN, REDEEM_CODES


@register_plugin
class RedeemCodePlugin(CommandPlugin):
    name = "redeem_code"
    description = "使用兑换码兑换奖励。"
    COMMANDS = ("/兑换码", "/兌換碼")

    def handle(self):
        try:
            if self.bot_event.user_id is None:
                return
            user_id = self.bot_event.user_id
            if not self.args:
                self.api.send_msg(text("请使用 /兑换码 <兑换码>，格式：XXXX-XXXX-XXXX（大写字母）"))
                return
            code = self.args[0].strip().upper()  # 输入大小写不敏感，存储统一大写
            if not CODE_PATTERN.match(code):
                self.api.send_msg(text("兑换码格式不正确，应为 XXXX-XXXX-XXXX（大写字母）"))
                return
            entry = REDEEM_CODES.get(code)
            if entry is None:
                self.api.send_msg(text("兑换码不存在或已失效"))
                return
            if not self.dbmanager.redeem.claim(user_id, code):
                self.api.send_msg(text("你已使用过该兑换码，无法重复兑换"))
                return
            try:
                reward_msg = entry["callback"](self.dbmanager, user_id, self.api)
            except Exception:
                self.dbmanager.redeem.release(user_id, code)  # 回滚占位，允许重试
                logger.exception("兑换码回调执行失败: %s", code)
                self.api.send_msg(text("兑换处理失败，请稍后再试喵"))
                return
            suffix = f"，{reward_msg}" if reward_msg else ""
            self.api.send_msg(at(user_id), text(f"兑换成功{suffix}"))
        except Exception:
            logger.exception("RedeemCode 处理异常")
            self.api.send_msg(text("兑换处理失败，请稍后再试喵"))
