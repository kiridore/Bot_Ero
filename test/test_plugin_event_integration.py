"""通过真实打卡插件和周常消费者验证开关与关闭后的奖励撤销。"""
from unittest.mock import Mock

import pytest

from core import config, context
from core.database_manager import DbManager
from core.db.plugin_settings import set_user_plugins
from core.event import Event
from core.message_output import MessageOutput
from core.plugin_dispatch import Operation
from plugins.checkin import CheckinPlugin
from plugins.roll_back import RollbackCheckinPlugin
from plugins.checkin_recall import CheckinRecallPlugin
from plugins.weekly_quest import events  # 注册实际消费者


@pytest.fixture
def db(tmp_path, monkeypatch):
    import plugins.checkin as checkin
    import plugins.roll_back as rollback
    import plugins.checkin_recall as recall
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "integration.db")
    monkeypatch.setattr(checkin, "ensure_checkin_image", lambda *args: True)
    monkeypatch.setattr(checkin, "emit_event", lambda **kwargs: None)
    monkeypatch.setattr(rollback, "retract_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(recall, "retract_event", lambda *args, **kwargs: None)
    database = DbManager()
    yield database
    database.conn.close()


def run_plugin(cls, db, *, gid=10, uid=42, mid=100, message=None):
    raw = {"post_type": "message", "message_type": "private" if gid is None else "group",
           "user_id": uid, "message_id": mid, "message": message or [
               {"type": "text", "data": {"text": "/打卡"}},
               {"type": "image", "data": {"file": "test.png"}},
           ]}
    if gid is not None:
        raw["group_id"] = gid
    if cls is CheckinRecallPlugin:
        raw.update(post_type="notice", notice_type="group_recall")
    sent = []
    op = Operation(context.plugin_settings_snapshot(gid, uid), MessageOutput(
        lambda r: sent.append(r) or 1, ("group", gid) if gid is not None else ("private", uid)))
    plugin = cls.__new__(cls)
    plugin.bot_event = Event(raw)
    plugin.dbmanager = db
    plugin.api = Mock()
    plugin.api.get_image.return_value = ""
    plugin.operation = op
    assert op.execute(context.plugin_key(cls), plugin.handle)
    op.finish()
    assert not op.failures
    return op, sent


def enable_quest(db, gid=10):
    db.conn.execute("INSERT OR IGNORE INTO group_plugin_config VALUES (?, 'weekly_quest')", (gid,))
    db.conn.commit()


def points(db):
    row = db.conn.execute("SELECT points FROM user_assets WHERE user_id = '42'").fetchone()
    return row[0] if row else 0


def test_disable_quest_only_stops_new_quest_rewards(db):
    _, sent = run_plugin(CheckinPlugin, db)
    assert points(db) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM checkin_records").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM quest_progress").fetchone()[0] == 0
    assert len(sent) == 1 and sent[0].kind == "segments"  # 仍正常回复打卡结果
    enable_quest(db)
    assert points(db) == 0  # 开启本身不补发
    _, sent = run_plugin(CheckinPlugin, db, mid=101)
    assert points(db) == 1
    assert [r.content for r in sent if r.kind == "text"] == ["🎯 打个卡先 +1"]


def test_disable_private_override_does_not_affect_group(db):
    enable_quest(db, 0)
    enable_quest(db, 10)
    set_user_plugins(db.conn, 42, ["weekly_quest"], False)
    run_plugin(CheckinPlugin, db, gid=None)
    assert points(db) == 0
    run_plugin(CheckinPlugin, db, mid=102)
    assert points(db) == 1


def test_disable_title_and_shop_does_not_consume_buff_or_unlock(db, monkeypatch):
    from plugins.redeem_shop import events as shop_events
    db.shop.add_luck(42, 2)
    monkeypatch.setattr(shop_events.random, "random", lambda: 0)
    run_plugin(CheckinPlugin, db)
    assert db.shop.luck_remaining(42) == 2
    assert db.titles.list(42) == []
    db.conn.execute("INSERT INTO group_plugin_config VALUES (10, 'redeem_shop')")
    db.conn.commit()
    _, sent = run_plugin(CheckinPlugin, db, mid=101)
    assert db.shop.luck_remaining(42) == 1
    assert points(db) == 1
    assert any(r.content == "打卡增强：概率奖励 +1" for r in sent)
    run_plugin(CheckinPlugin, db, mid=101)  # 重复来源不能再次消耗道具或发奖
    assert db.shop.luck_remaining(42) == 1
    assert points(db) == 1


def test_title_evaluation_precedes_new_quest_completion(db):
    enable_quest(db)
    db.conn.execute("INSERT INTO group_plugin_config VALUES (10, 'title')")
    db.conn.commit()
    for _ in range(4):
        db.quest.increment_completion(42)
    run_plugin(CheckinPlugin, db)
    assert db.quest.completion(42) == 5
    assert not db.titles.has(42, 238)  # 保持先评估称号、再增加本次周常次数的旧顺序
    run_plugin(CheckinPlugin, db, mid=102)
    assert db.titles.has(42, 238)


def test_recalled_multi_image_message_revokes_once_while_quest_disabled(db):
    enable_quest(db)
    run_plugin(CheckinPlugin, db, message=[
        {"type": "text", "data": {"text": "/打卡"}},
        {"type": "image", "data": {"file": "one.png"}},
        {"type": "image", "data": {"file": "two.png"}},
    ])
    assert points(db) == 1
    db.conn.execute("DELETE FROM group_plugin_config WHERE plugin_name = 'weekly_quest'")
    db.conn.commit()
    _, sent = run_plugin(CheckinRecallPlugin, db)
    assert points(db) == 0
    assert db.conn.execute("SELECT COUNT(*) FROM checkin_records").fetchone()[0] == 0
    assert "含2张图" in sent[0].content[1]["data"]["text"]
    _, sent = run_plugin(CheckinRecallPlugin, db)
    assert not sent
    assert points(db) == 0


def test_disabled_quest_still_revokes_real_reward(db):
    enable_quest(db)
    run_plugin(CheckinPlugin, db)
    assert points(db) == 1
    db.conn.execute("DELETE FROM group_plugin_config WHERE plugin_name = 'weekly_quest'")
    db.conn.commit()
    run_plugin(RollbackCheckinPlugin, db, mid=200, message=[{"type": "text", "data": {"text": "/撤回打卡"}}])
    assert points(db) == 0
    assert db.conn.execute("SELECT revoked_at FROM plugin_reward_records").fetchone()[0] is not None
    run_plugin(RollbackCheckinPlugin, db, mid=201, message=[{"type": "text", "data": {"text": "/撤回打卡"}}])
    assert points(db) == 0
