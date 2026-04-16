import requests

from core.base import Plugin
from core.cq import at, image, text


class RandomReferencePlugin(Plugin):
    name = 'random_reference'
    description = '发送一张随机参考图片。'

    PICSUM_URL = "https://picsum.photos/512"

    def match(self, message_type):
        return self.on_full_match("/随机参考")

    def _resolve_image_url(self) -> str:
        # picsum.photos returns a redirect to the actual image.
        proxies = {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890",
        }
        try:
            resp = requests.get(self.PICSUM_URL, proxies=proxies, timeout=30, allow_redirects=False)
        except Exception:
            resp = requests.get(self.PICSUM_URL, timeout=30, allow_redirects=False)

        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location", "")
            if loc:
                return loc
        return self.PICSUM_URL

    def handle(self):
        user_id = self.context.get("user_id")
        url = self._resolve_image_url()

        if user_id:
            self.api.send_msg(at(user_id), text("随机参考："), image(url))
        else:
            self.api.send_msg(text("随机参考："), image(url))

