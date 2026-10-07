"""每次外部事件独立的同步通知处理；不创建线程，不共享待处理队列。"""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from uuid import uuid4

from core.logger import logger


@dataclass(frozen=True)
class Subscription:
    topic: str
    plugin: str
    handler: object
    order: int = 0
    cleanup: bool = False


_subscriptions = []


def subscribe(topic, plugin, *, order=0, cleanup=False):
    """注册本身不代表开启；cleanup 仅供根据历史记录撤销旧奖励。"""
    def decorate(handler):
        entry = Subscription(topic, plugin, handler, order, cleanup)
        identity = (topic, plugin, handler.__module__, handler.__qualname__)
        for index, old in enumerate(_subscriptions):
            if (old.topic, old.plugin, old.handler.__module__, old.handler.__qualname__) == identity:
                _subscriptions[index] = entry
                break
        else:
            _subscriptions.append(entry)
        return handler
    return decorate


def _deployment_allowed(plugin: str) -> bool:
    """部署硬边界；延迟导入避免模块期循环。手动构造的 Operation 也受同一限制。"""
    from core import context
    return context.plugin_allowed(plugin)


class Operation:
    MAX_NOTIFICATIONS = 1000

    def __init__(self, enabled, output, *, subscriptions=None, operation_id=None):
        if output.operation_id is not None:
            raise ValueError("不同操作不能共用消息输出列表")
        self.id = operation_id or uuid4().hex
        output.operation_id = self.id
        self.enabled = MappingProxyType(dict(enabled))
        self.output = output
        self.subscriptions = tuple(sorted(
            _subscriptions if subscriptions is None else subscriptions,
            key=lambda s: s.order,
        ))
        self._pending = deque()
        self._published = 0
        self._staged = None
        self._ancestry = ()
        self._draining = False
        self.failures = []

    def is_enabled(self, plugin):
        return bool(self.enabled.get(plugin, False))

    def publish(self, topic, payload):
        # 同一业务记录允许不同类型通知，但不允许从子通知重新通知其祖先。
        # 不同抽取序号可重复同一通知类型；总数上限阻止不断换来源的错误循环。
        if self._published >= self.MAX_NOTIFICATIONS:
            raise ValueError("单次操作内部通知超出安全上限")
        self._published += 1
        identity = (topic, payload.get("source_operation"))
        if identity in self._ancestry:
            raise ValueError("内部通知发生循环")
        item = (topic, deepcopy(payload), self._ancestry + (identity,))
        if self._staged is None:
            self._pending.append(item)
        else:
            self._staged.append(item)

    def execute(self, plugin, callback):
        """成功后才接受提示和子通知；数据库事务由业务处理函数负责。"""
        if self._staged is not None:
            raise RuntimeError("不能嵌套执行通知处理函数")
        self._staged = []
        try:
            with self.output.capture():
                callback()
        except Exception:
            self.failures.append(plugin)
            logger.exception("操作 %s 的插件 %s 处理失败", self.id, plugin)
            self.output.failure(plugin)
            return False
        else:
            self._pending.extend(self._staged)
            return True
        finally:
            self._staged = None

    def drain(self):
        if self._draining:
            raise RuntimeError("不能递归处理内部通知")
        self._draining = True
        try:
            while self._pending:
                topic, payload, ancestry = self._pending.popleft()
                self._ancestry = ancestry
                for sub in self.subscriptions:
                    if sub.topic != topic:
                        continue
                    # cleanup 只绕过局部新奖励开关，绕不过部署禁止（config-unification）
                    if sub.cleanup:
                        if not _deployment_allowed(sub.plugin):
                            continue
                    elif not self.is_enabled(sub.plugin):
                        continue
                    # 每个消费者各拿一份数据，不能篡改其他消费者所见内容。
                    self.execute(sub.plugin, lambda s=sub: s.handler(self, deepcopy(payload)))
        finally:
            self._ancestry = ()
            self._draining = False

    def finish(self):
        self.drain()
        self.output.flush()
