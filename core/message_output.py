"""同步收集已确认的发送请求；一个实例只服务一次外部操作。"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass

from core.logger import logger


@dataclass(frozen=True)
class SendRequest:
    target: tuple
    content: object
    kind: str = "text"
    merge: str | None = None
    order: int = 0


def send_request(request):
    """唯一真实发送入口，目的地不从别的事件或可变全局推断。"""
    from core.api import ApiWrapper
    from core.cq import text
    kind, target_id = request.target
    api = ApiWrapper({"group_id" if kind == "group" else "user_id": target_id})
    try:
        if request.kind == "text":
            return api.send_msg(text(request.content))
        if request.kind == "segments":
            return api.send_msg(*request.content)
        if request.kind == "forward":
            return api.send_forward_msg(request.content)
        return api.send_forward_nodes(request.content)
    finally:
        api.dbmanager.conn.close()


class MessageOutput:
    def __init__(self, send, default_target=None, *, max_text_chars=2000):
        if max_text_chars <= 0:
            raise ValueError("文本分段长度必须为正数")
        self.send = send
        self.operation_id = None  # Operation 绑定；不得供多个事件共用
        self.default_target = default_target
        self.max_text_chars = max_text_chars
        self._requests = []
        self._staged = None
        self._flushed = False

    def submit(self, content, *, target=None, kind="text", merge=None, order=0):
        if self._flushed:
            raise RuntimeError("本次操作已经发送完毕")
        target = self.default_target if target is None else target
        if not (isinstance(target, tuple) and len(target) == 2
                and target[0] in ("group", "private")
                and isinstance(target[1], int) and not isinstance(target[1], bool)
                and target[1] > 0):
            raise ValueError("发送位置必须明确为群号或私聊账号")
        if kind not in ("text", "segments", "forward", "nodes"):
            raise ValueError("不支持的发送类型")
        if kind == "text" and not isinstance(content, str):
            raise TypeError("普通文本请求必须是字符串")
        if merge is not None and not isinstance(merge, str):
            raise TypeError("合并标记必须是字符串")
        request = SendRequest(target, deepcopy(content), kind, merge, order)
        (self._requests if self._staged is None else self._staged).append(request)

    @contextmanager
    def capture(self):
        if self._staged is not None:
            raise RuntimeError("不能嵌套收集输出")
        self._staged = []
        try:
            yield
        except BaseException:
            raise
        else:
            self._requests.extend(self._staged)
        finally:
            self._staged = None

    def failure(self, plugin):
        if self.default_target is not None:
            self.submit(f"{plugin} 处理失败，其他已完成的操作不受影响。", order=1000)

    def flush(self):
        if self._staged is not None:
            raise RuntimeError("不能发送尚未确认的输出")
        if self._flushed:
            return
        self._flushed = True  # 失败或超时也不再次发送结果不明的请求
        groups = {}
        for sequence, request in enumerate(self._requests):
            key = ((request.target, request.merge) if request.kind == "text" and request.merge
                   else ("single", sequence))
            groups.setdefault(key, []).append((sequence, request))
        batches = sorted(groups.values(), key=lambda items: min(
            (r.order, seq) for seq, r in items
        ))
        for batch_number, items in enumerate(batches, 1):
            items.sort(key=lambda item: (item[1].order, item[0]))
            request = items[0][1]
            if request.kind == "text":
                body = "\n".join(r.content for _, r in items)
                contents = [body[i:i + self.max_text_chars]
                            for i in range(0, len(body), self.max_text_chars)] or [""]
            else:
                contents = [request.content]
            for part_number, content in enumerate(contents, 1):
                try:
                    result = self.send(SendRequest(request.target, content, request.kind))
                    if not result:
                        logger.warning(
                            "消息发送失败，操作=%s 批次=%s 分段=%s 类型=%s 目标=%s，不自动重试",
                            self.operation_id, batch_number, part_number, request.kind, request.target,
                        )
                except Exception:
                    logger.exception(
                        "消息发送异常，操作=%s 批次=%s 分段=%s 类型=%s 目标=%s，不自动重试",
                        self.operation_id, batch_number, part_number, request.kind, request.target,
                    )
