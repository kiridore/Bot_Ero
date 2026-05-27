from core.base import Plugin
from core.cq import at, text

from checkin_gallery.auth import make_login_key
from core.utils import register_plugin


@register_plugin
class GalleryLoginKeyPlugin(Plugin):
    name = "gallery_login_key"
    description = "私聊发放打卡图库网页登录密钥。"

    def match(self, message_type):
        return self.bot_event.is_private and self.on_full_match_any(
            "/图库密钥",
            "/圖庫密鑰",
            "/网页密钥",
            "/網頁密鑰",
        )

    def handle(self):
        if self.bot_event.user_id is None:
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
