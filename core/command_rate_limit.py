"""账号滚动指令窗口；一次事件只请求一次额度，网络与业务不在锁内。"""
from collections import deque
import math
from threading import Lock
import time


class CommandRateLimiter:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = Lock()
        self._windows = {}
        self._notices = {}
        self._next_cleanup = 0

    def acquire(self, user_id, limit):
        """返回(允许执行, 剩余秒数, 是否尝试提示)。"""
        if limit == 0:
            return True, 0, False
        with self._lock:
            now = self._clock()
            if now >= self._next_cleanup:
                for uid, window in list(self._windows.items()):
                    if (not window or window[-1] <= now - 60) and self._notices.get(uid, -math.inf) <= now - 10:
                        del self._windows[uid]
                        self._notices.pop(uid, None)
                self._next_cleanup = now + 60
            window = self._windows.setdefault(user_id, deque())
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) < limit:
                window.append(now)
                return True, 0, False
            notify = now - self._notices.get(user_id, -math.inf) >= 10
            if notify:
                self._notices[user_id] = now
            return False, math.ceil(window[0] + 60 - now), notify


limiter = CommandRateLimiter()


class CommandBudget:
    """每条消息共享一次决定；在首次匹配指令的handle前检查，保持原调度顺序。"""
    def __init__(self, raw, operation):
        from core import config
        self.limit = config.COMMAND_LIMIT_PER_MINUTE
        self.raw = raw
        self.operation = operation
        self.allowed = None

    def allows(self, plugin):
        uid = self.raw.get('user_id')
        if (not self.limit or self.raw.get('post_type') != 'message'
                or type(uid) is not int or uid <= 0 or not plugin.is_command()):
            return True
        if self.allowed is None:
            self.allowed, seconds, notify = limiter.acquire(uid, self.limit)
            if notify:
                from core.cq import at, text
                gid = self.raw.get('group_id')
                target = ('group', gid) if gid is not None else ('private', uid)
                content = [text(f'指令使用太频繁啦，每60秒最多{self.limit}次，请在约{seconds}秒后再试。')]
                if gid is not None:
                    content.insert(0, at(uid))
                self.operation.output.submit(content, target=target, kind='segments')
        return self.allowed
