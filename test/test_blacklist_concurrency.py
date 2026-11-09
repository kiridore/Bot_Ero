from concurrent.futures import ThreadPoolExecutor
from threading import Event

from core import plugin_dispatch
from test.test_blacklist_management import management


def test_message_and_internal_notification_keep_admitted_snapshot(management, monkeypatch):
    run, db, hits, cls = management
    started, finish = Event(), Event()
    events = []

    def business(self):
        events.append('started')
        started.set()
        assert finish.wait(5)
        assert not self.operation.blacklist_snapshot.blocks(user_id=42)
        self.operation.publish('blacklist.test', {'user_id': 42})
        events.append('completed')

    def consume(operation, payload):
        assert not operation.blacklist_snapshot.blocks(user_id=payload['user_id'])
        events.append('notification')

    monkeypatch.setattr(cls, 'handle', business)
    monkeypatch.setattr(plugin_dispatch, '_subscriptions', [
        plugin_dispatch.Subscription('blacklist.test', 'probe', consume)])
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(run, '/测试', 42)
        try:
            assert started.wait(5)
            assert '已加入' in run('/黑名单 添加 用户 42')
            assert db.community.is_banned('user', 42)
            assert run('/测试', uid=42) == ''  # 后续消息不能进入business
        finally:
            finish.set()
        old.result(timeout=10)
    assert events == ['started', 'completed', 'notification']
