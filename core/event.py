class Event:
    def __init__(self, raw: dict):
        self.raw = raw

    @property
    #发送者 QQ号
    def user_id(self) -> int:
        return self.raw.get("user_id", 0)

    @property
    def group_id(self):
        return self.raw.get("group_id")

    @property
    def message(self):
        return self.raw.get("message", [])

    @property
    def is_group(self):
        return self.raw.get("message_type") == "group"

    @property
    def is_private(self):
        return self.raw.get("message_type") == "private"

    @property
    def message_id(self):
        return self.raw.get("message_id")

    @property
    def post_type(self):
        return self.raw.get("post_type")

    @property
    def time(self):
        return self.raw.get("time")

    @property
    def sender(self):
        return self.raw.get("sender")

    @property
    def request_type(self):
        return self.raw.get("request_type")

    @property
    def notice_type(self):
        return self.raw.get("notice_type")

class Message:
    def __init__(self, raw: dict):
        self.raw = raw

    @property
    def type(self):
        return self.raw.get("type")

    @property
    def data(self):
        return self.raw.get("data")
