"""新卧底历史存储；写操作必须在transaction中，允许结束记录与战绩共用事务。"""
from contextlib import contextmanager
import json


SUMMARY = """SELECT g.record_id, g.room_code, g.group_id, g.created_at,
                    g.started_at, g.ended_at, g.status, g.winner, g.revision"""


def _decode(cursor, row):
    if row is None:
        return None
    data = dict(zip((column[0] for column in cursor.description), row))
    if 'snapshot_json' in data:
        data['snapshot'] = json.loads(data.pop('snapshot_json'))
    return data


class WhoIsSpyManager:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def transaction(self):
        if self.conn.in_transaction:
            raise RuntimeError('已有事务，不能嵌套开启游戏事务')
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            yield self
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def _require_transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError('游戏写入必须位于显式事务中')

    def create(self, *, request_key, room_code, group_id, created_at, snapshot):
        self._require_transaction()
        cursor = self.conn.execute('SELECT * FROM spy_game_records WHERE request_key = ?', (request_key,))
        existing = _decode(cursor, cursor.fetchone())
        if existing is not None:
            if existing['group_id'] != group_id:
                raise ValueError('创建请求已用于其他群')
            return existing
        cursor = self.conn.execute("""
            INSERT INTO spy_game_records
                (request_key, room_code, group_id, created_at, status, snapshot_json)
            VALUES (?, ?, ?, ?, 'waiting', ?)
        """, (request_key, room_code, group_id, created_at,
              json.dumps(snapshot, ensure_ascii=False, allow_nan=False)))
        return self.get_internal(cursor.lastrowid)

    def get_internal(self, record_id):
        """仅供游戏状态处理；命令查询必须使用带范围校验的detail/list_records。"""
        cursor = self.conn.execute('SELECT * FROM spy_game_records WHERE record_id = ?', (record_id,))
        return _decode(cursor, cursor.fetchone())

    def save(self, record_id, revision, *, status, snapshot, participants,
             started_at=None, ended_at=None, winner=None):
        self._require_transaction()
        cursor = self.conn.execute("""
            UPDATE spy_game_records
            SET status = ?, started_at = ?, ended_at = ?, winner = ?, snapshot_json = ?, revision = revision + 1
            WHERE record_id = ? AND revision = ? AND status IN ('waiting', 'playing')
              AND NOT (status = 'playing' AND ? = 'waiting')
        """, (status, started_at, ended_at, winner,
              json.dumps(snapshot, ensure_ascii=False, allow_nan=False), record_id, revision, status))
        if cursor.rowcount != 1:
            raise ValueError('游戏记录已变更或已结束，不能覆盖')
        for player in participants:
            self.conn.execute("""
                INSERT INTO spy_game_participants
                    (record_id, user_id, nickname, joined_at, left_at, participated, state)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id, user_id) DO UPDATE SET
                    nickname = excluded.nickname,
                    left_at = excluded.left_at,
                    participated = MAX(spy_game_participants.participated, excluded.participated),
                    state = excluded.state
            """, (record_id, str(player['user_id']), player.get('nickname', ''),
                  player['joined_at'], player.get('left_at'), player['participated'], player['state']))
        return revision + 1

    @staticmethod
    def _check_scope(group_id, user_id):
        if (group_id is None) == (user_id is None):
            raise ValueError('必须且只能指定当前群或当前账号')

    def list_records(self, *, group_id=None, user_id=None, page=1):
        self._check_scope(group_id, user_id)
        if type(page) is not int or page < 1 or (page - 1) * 10 > 2**63 - 1:
            raise ValueError('页码必须是有效正整数')
        offset = (page - 1) * 10
        if group_id is not None:
            cursor = self.conn.execute(SUMMARY + """
                FROM spy_game_records AS g WHERE g.group_id = ?
                ORDER BY g.created_at DESC, g.record_id DESC LIMIT 11 OFFSET ?
            """, (group_id, offset))
        else:
            cursor = self.conn.execute(SUMMARY + """,
                p.state AS participation_state, p.participated, p.joined_at, p.left_at
                FROM spy_game_records AS g
                JOIN spy_game_participants AS p ON p.record_id = g.record_id
                WHERE p.user_id = ?
                ORDER BY g.created_at DESC, g.record_id DESC LIMIT 11 OFFSET ?
            """, (str(user_id), offset))
        rows = cursor.fetchall()
        return [_decode(cursor, row) for row in rows[:10]], len(rows) > 10

    def detail(self, record_id, *, group_id=None, user_id=None):
        """校验记录归属；返回含私密字段的内部数据，显示层仍须按结束状态筛选。"""
        self._check_scope(group_id, user_id)
        if group_id is not None:
            cursor = self.conn.execute(
                'SELECT * FROM spy_game_records WHERE record_id = ? AND group_id = ?',
                (record_id, group_id))
        else:
            cursor = self.conn.execute("""
                SELECT g.* FROM spy_game_records AS g
                JOIN spy_game_participants AS p ON p.record_id = g.record_id
                WHERE g.record_id = ? AND p.user_id = ?
            """, (record_id, str(user_id)))
        return _decode(cursor, cursor.fetchone())

    def active_room(self, room_code):
        cursor = self.conn.execute("SELECT * FROM spy_game_records WHERE room_code = ? AND status IN ('waiting', 'playing')", (room_code,))
        return _decode(cursor, cursor.fetchone())

    def active_for_user(self, user_id):
        cursor = self.conn.execute("""
            SELECT g.* FROM spy_game_records g JOIN spy_game_participants p ON p.record_id = g.record_id
            WHERE p.user_id = ? AND p.state != 'left' AND g.status IN ('waiting', 'playing')
        """, (str(user_id),))
        return _decode(cursor, cursor.fetchone())

    def active_in_group(self, group_id):
        cursor = self.conn.execute("SELECT * FROM spy_game_records WHERE group_id = ? AND status IN ('waiting', 'playing') ORDER BY record_id", (group_id,))
        return [_decode(cursor, row) for row in cursor.fetchall()]

    def can_receive(self, record_id, user_id):
        return self.conn.execute('SELECT 1 FROM spy_game_participants WHERE record_id = ? AND user_id = ? AND state != ?',
                                 (record_id, str(user_id), 'left')).fetchone() is not None

    def by_request(self, request_key):
        cursor = self.conn.execute('SELECT * FROM spy_game_records WHERE request_key = ?', (request_key,))
        return _decode(cursor, cursor.fetchone())

    def interrupt_open(self, ended_at):
        """仅由bot启动恢复调用；保留最后快照，关系字段的status/winner为权威。"""
        self._require_transaction()
        cursor = self.conn.execute("""
            UPDATE spy_game_records
            SET status = 'interrupted', winner = NULL, ended_at = ?, revision = revision + 1
            WHERE status IN ('waiting', 'playing')
        """, (ended_at,))
        return cursor.rowcount
