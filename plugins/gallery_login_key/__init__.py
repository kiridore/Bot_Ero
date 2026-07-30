from core.base import NICKNAME, CommandPlugin
from core.cq import at, text

from checkin_gallery.auth import make_login_key
from core.utils import register_plugin


@register_plugin
class GalleryLoginKeyPlugin(CommandPlugin):
    name = "gallery_login_key"
    description = "私聊发放打卡图库网页登录密钥。"
    COMMANDS = ("/图库密钥", "/圖庫密鑰", "/网页密钥", "/網頁密鑰")

    def handle(self):
        if self.bot_event.user_id is None:
            return
        if not self.bot_event.is_private:
            self.api.send_msg(
                at(self.bot_event.user_id),
                text(
                    f"「/图库密钥」仅限私聊使用喵~\n"
                    f"请先添加{NICKNAME}为好友，再在私聊中发送该指令获取网页登录密钥。"
                ),
            )
            return
        key = make_login_key(self.bot_event.user_id)
        self.api.send_msg(
            at(self.bot_event.user_id),
            text(
                "打卡图库登录密钥（请勿泄露）：\n"
                f"{key}\n\n"
                "在图库页面点击「登录」粘贴即可；登录后可进入个人主页。"
            ),
        )
