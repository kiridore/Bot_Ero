from datetime import datetime, timedelta
import sqlite3


def _migrate_forum_polls(conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
    """旧版「选项直挂帖子、整帖单选」结构 → 新版「帖子含多个子投票（单选/多选）」。

    幂等：`forum_poll_options` 已含 `poll_id` 列即视为已迁移。
    原子：整个迁移包在单个 `BEGIN IMMEDIATE ... COMMIT` 事务内，任一失败整体回滚
    （SQLite 支持事务化 DDL），进程被杀也能靠 WAL 恢复自动回滚。
    并发安全：bot 与 webapp 共享同一 SQLite、启动时都会跑 `init_schema`，故先拿写锁
    （`BEGIN IMMEDIATE`）串行化，拿到锁后二次确认是否已被另一进程迁移。
    迁移期间临时关闭外键以安全重建被 `forum_poll_votes` 引用的表，结束后恢复。
    """
    def _has_new_schema():
        cols = [r[1] for r in cur.execute("PRAGMA table_info(forum_poll_options)").fetchall()]
        return "poll_id" in cols

    if _has_new_schema():
        return
    # 结束此前可能由早期 DML 打开的隐式事务，否则 `PRAGMA foreign_keys` 会被静默忽略，
    # 导致重建被引用表时触发 ON DELETE CASCADE 误删投票。
    conn.commit()
    cur.execute("PRAGMA foreign_keys=OFF")
    try:
        # 立即拿写锁串行化并发迁移（另一进程正在迁移时会在此阻塞，busy_timeout=5000 兜底）
        cur.execute("BEGIN IMMEDIATE")
        # 拿锁后二次确认：另一进程可能已完成迁移
        if _has_new_schema():
            conn.rollback()
            return
        # 1. 为每个含选项的旧投票帖建一个默认子投票（问题为空，多选标志取自旧帖级字段）
        cur.execute("""
            INSERT INTO forum_polls (post_id, title, allow_multi, ord)
            SELECT o.post_id, '', p.poll_allow_multi, 0
            FROM (SELECT DISTINCT post_id FROM forum_poll_options) o
            JOIN forum_posts p ON p.id = o.post_id
        """)
        # 2. 选项表：post_id → poll_id
        cur.execute("ALTER TABLE forum_poll_options RENAME TO forum_poll_options_old")
        cur.execute("""
            CREATE TABLE forum_poll_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                ord INTEGER NOT NULL,
                FOREIGN KEY (poll_id) REFERENCES forum_polls(id) ON DELETE CASCADE
            );
        """)
        cur.execute("""
            INSERT INTO forum_poll_options (id, poll_id, text, ord)
            SELECT oo.id, fp.id, oo.text, oo.ord
            FROM forum_poll_options_old oo
            JOIN forum_polls fp ON fp.post_id = oo.post_id
        """)
        cur.execute("DROP TABLE forum_poll_options_old")
        # 3. 投票表：poll_id 由「帖子 id」重映射为「子投票 id」，唯一约束改为多选兼容
        cur.execute("ALTER TABLE forum_poll_votes RENAME TO forum_poll_votes_old")
        cur.execute("""
            CREATE TABLE forum_poll_votes (
                poll_id INTEGER NOT NULL,
                option_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(poll_id, option_id, user_id),
                FOREIGN KEY (option_id) REFERENCES forum_poll_options(id) ON DELETE CASCADE
            );
        """)
        cur.execute("""
            INSERT INTO forum_poll_votes (poll_id, option_id, user_id, created_at)
            SELECT oo.poll_id, vo.option_id, vo.user_id, vo.created_at
            FROM forum_poll_votes_old vo
            JOIN forum_poll_options oo ON oo.id = vo.option_id
        """)
        cur.execute("DROP TABLE forum_poll_votes_old")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.execute("PRAGMA foreign_keys=ON")


def init_schema(conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkin_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        checkin_date TEXT NOT NULL,
        content TEXT NOT NULL
    );
    """)

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_assets (
            user_id TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0
        );
    ''')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_titles (
            user_id TEXT NOT NULL,
            title_id INTEGER NOT NULL,
            unlocked_at TEXT NOT NULL,
            PRIMARY KEY (user_id, title_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_title_state (
            user_id TEXT PRIMARY KEY,
            equipped_title INTEGER
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_equipped_titles (
            user_id TEXT NOT NULL,
            slot INTEGER NOT NULL,
            title_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, slot),
            UNIQUE (user_id, title_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_lottery_daily_stats (
            stat_date TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            draw_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (stat_date, user_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_remedy_usage (
            year INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (year, user_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_lottery_stats (
            user_id INTEGER PRIMARY KEY,
            total_spent INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_weekly_streak_reward_claims (
            user_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, week_start)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_attendance_reward_claims (
            user_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL,
            period_key TEXT NOT NULL,
            points INTEGER NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, reward_type, period_key)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_lottery_profile (
            user_id INTEGER PRIMARY KEY,
            draw_count INTEGER NOT NULL DEFAULT 0,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            zero_streak INTEGER NOT NULL DEFAULT 0,
            max_zero_streak INTEGER NOT NULL DEFAULT 0,
            has_hit_ten INTEGER NOT NULL DEFAULT 0,
            total_zeros INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("PRAGMA table_info(user_lottery_profile)")
    _lp_cols = [row[1] for row in cur.fetchall()]
    if "total_zeros" not in _lp_cols:
        cur.execute("ALTER TABLE user_lottery_profile ADD COLUMN total_zeros INTEGER NOT NULL DEFAULT 0")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shop_stock (
            product_id TEXT PRIMARY KEY,
            stock INTEGER NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shop_user_buffs (
            user_id INTEGER PRIMARY KEY,
            extra_draw_pack_until TEXT,
            checkin_luck_remaining INTEGER NOT NULL DEFAULT 0,
            lottery_waiver_remaining INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("PRAGMA table_info(checkin_records)")
    _cols = [row[1] for row in cur.fetchall()]
    if "message_id" not in _cols:
        cur.execute("ALTER TABLE checkin_records ADD COLUMN message_id INTEGER")
    cur.execute("""
        INSERT OR IGNORE INTO user_equipped_titles (user_id, slot, title_id)
        SELECT user_id, 1, equipped_title
        FROM user_title_state
        WHERE equipped_title IS NOT NULL
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            creator_user_id INTEGER NOT NULL,
            fire_at TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            fired INTEGER NOT NULL DEFAULT 0,
            is_private INTEGER NOT NULL DEFAULT 0,
            is_recurring INTEGER NOT NULL DEFAULT 0,
            repeat_y INTEGER NOT NULL DEFAULT 0,
            repeat_m INTEGER NOT NULL DEFAULT 0,
            repeat_d INTEGER NOT NULL DEFAULT 0,
            recur_kind INTEGER NOT NULL DEFAULT 0,
            recur_a INTEGER NOT NULL DEFAULT 0,
            recur_b INTEGER NOT NULL DEFAULT 0,
            recur_c INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_group_alarms_due ON group_alarms (fired, fire_at)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS guestbook_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS guestbook_likes (
            entry_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (entry_id, user_id),
            FOREIGN KEY (entry_id) REFERENCES guestbook_entries(id)
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_guestbook_entries_created "
        "ON guestbook_entries (created_at DESC)"
    )
    cur.execute("PRAGMA table_info(group_alarms)")
    _alarm_cols = [row[1] for row in cur.fetchall()]
    if _alarm_cols and "is_private" not in _alarm_cols:
        cur.execute(
            "ALTER TABLE group_alarms ADD COLUMN is_private INTEGER NOT NULL DEFAULT 0"
        )
    cur.execute("PRAGMA table_info(group_alarms)")
    _alarm_cols2 = [row[1] for row in cur.fetchall()]
    for col, ddl in (
        ("is_recurring", "ALTER TABLE group_alarms ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0"),
        ("repeat_y", "ALTER TABLE group_alarms ADD COLUMN repeat_y INTEGER NOT NULL DEFAULT 0"),
        ("repeat_m", "ALTER TABLE group_alarms ADD COLUMN repeat_m INTEGER NOT NULL DEFAULT 0"),
        ("repeat_d", "ALTER TABLE group_alarms ADD COLUMN repeat_d INTEGER NOT NULL DEFAULT 0"),
        ("recur_kind", "ALTER TABLE group_alarms ADD COLUMN recur_kind INTEGER NOT NULL DEFAULT 0"),
        ("recur_a", "ALTER TABLE group_alarms ADD COLUMN recur_a INTEGER NOT NULL DEFAULT 0"),
        ("recur_b", "ALTER TABLE group_alarms ADD COLUMN recur_b INTEGER NOT NULL DEFAULT 0"),
        ("recur_c", "ALTER TABLE group_alarms ADD COLUMN recur_c INTEGER NOT NULL DEFAULT 0"),
    ):
        if _alarm_cols2 and col not in _alarm_cols2:
            cur.execute(ddl)
            cur.execute("PRAGMA table_info(group_alarms)")
            _alarm_cols2 = [row[1] for row in cur.fetchall()]
    cur.execute(
        """
        UPDATE group_alarms
        SET recur_kind = 1, recur_a = repeat_d, recur_b = 0, recur_c = 0
        WHERE is_recurring = 1 AND recur_kind = 0
          AND repeat_y = 0 AND repeat_m = 0 AND repeat_d > 0
        """
    )
    cur.execute(
        """
        UPDATE group_alarms
        SET is_recurring = 0, recur_kind = 0, recur_a = 0, recur_b = 0, recur_c = 0
        WHERE is_recurring = 1 AND recur_kind = 0
          AND NOT (repeat_y = 0 AND repeat_m = 0 AND repeat_d > 0)
        """
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS immortal_lottery_carry (
            group_id INTEGER NOT NULL PRIMARY KEY,
            carry_4a INTEGER NOT NULL DEFAULT 0,
            carry_3a INTEGER NOT NULL DEFAULT 0,
            carry_2a INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS immortal_lottery_results (
            group_id INTEGER NOT NULL,
            period_key TEXT NOT NULL,
            winning_digits TEXT NOT NULL,
            bet_total INTEGER NOT NULL DEFAULT 0,
            drawn_at TEXT NOT NULL,
            PRIMARY KEY (group_id, period_key)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS immortal_lottery_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            period_key TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            digits TEXT NOT NULL,
            bet_bj_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (group_id, user_id, bet_bj_date)
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_immortal_bets_period ON immortal_lottery_bets (group_id, period_key)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS immortal_lottery_issue (
            group_id INTEGER NOT NULL,
            period_key TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            PRIMARY KEY (group_id, period_key),
            UNIQUE (issue_code)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quest_progress (
            user_id TEXT NOT NULL,
            quest_id INTEGER NOT NULL,
            week_key TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            claimed_at TEXT,
            PRIMARY KEY (user_id, quest_id, week_key)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quest_completion_stats (
            user_id TEXT PRIMARY KEY,
            total_completions INTEGER DEFAULT 0
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quest_weekly_clears (
            user_id TEXT NOT NULL,
            week_key TEXT NOT NULL,
            cleared_at TEXT NOT NULL,
            PRIMARY KEY (user_id, week_key)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_plugin_config (
            group_id INTEGER NOT NULL,
            plugin_name TEXT NOT NULL,
            PRIMARY KEY (group_id, plugin_name)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_game_stats (
            user_id TEXT PRIMARY KEY,
            total_games INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            civilian_wins INTEGER DEFAULT 0,
            spy_wins INTEGER DEFAULT 0
        );
    """)
    cur.execute("DROP TABLE IF EXISTS group_chat_topic_messages")
    cur.execute("DROP TABLE IF EXISTS group_chat_topics")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            type TEXT NOT NULL,                -- 'relay' | 'match'
            title TEXT NOT NULL,
            description TEXT,                  -- 活动描述（可选）
            status TEXT NOT NULL DEFAULT 'open',  -- open | running | finished | cancelled
            created_by TEXT NOT NULL,
            signup_deadline TEXT,                -- 报名截止时间（到点自动开始）
            deadline TEXT,                       -- 活动截止时间（到点强制结束归档）
            hours_per_user REAL,               -- relay: 每人时限小时
            created_at TEXT NOT NULL,
            finished_at TEXT,
            pre_deadline_notified INTEGER NOT NULL DEFAULT 0  -- 截止前24h进度提醒已发
        );
    """)
    cur.execute("PRAGMA table_info(activities)")
    _act_cols = [row[1] for row in cur.fetchall()]
    if "theme" in _act_cols and "description" not in _act_cols:
        cur.execute("ALTER TABLE activities RENAME COLUMN theme TO description")
    if _act_cols and "signup_deadline" not in _act_cols:
        cur.execute("ALTER TABLE activities ADD COLUMN signup_deadline TEXT")
        cur.execute("PRAGMA table_info(activities)")
        _act_cols = [row[1] for row in cur.fetchall()]
    if _act_cols and "pre_deadline_notified" not in _act_cols:
        cur.execute(
            "ALTER TABLE activities ADD COLUMN pre_deadline_notified"
            " INTEGER NOT NULL DEFAULT 0"
        )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_members (
            activity_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            nickname TEXT NOT NULL,
            seq INTEGER NOT NULL DEFAULT 0,    -- relay 链序 / match 环序
            next_user_id TEXT,                 -- match: 下家
            status TEXT NOT NULL DEFAULT 'pending', -- pending|done|skipped|missed|left
            received_at TEXT,                  -- relay: 作品转交时刻（第一棒=开始通知时刻）
            submitted_at TEXT,
            content TEXT,
            images TEXT,                       -- JSON 数组
            PRIMARY KEY (activity_id, user_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS redeem_code_usage (
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            used_at TEXT NOT NULL,
            PRIMARY KEY (user_id, code)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            received_at TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_qq TEXT,
            target_type TEXT,
            target_url TEXT,
            title TEXT NOT NULL,
            description TEXT,
            data TEXT,
            dedup_key TEXT,
            UNIQUE(source, id),
            UNIQUE(source, dedup_key)
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_timeline_feed "
        "ON timeline_events (received_at DESC, id DESC)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timeline_user_watermarks (
            user_id TEXT PRIMARY KEY,
            position INTEGER NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timeline_read_events (
            user_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            PRIMARY KEY (user_id, event_id),
            FOREIGN KEY (event_id) REFERENCES timeline_events(id) ON DELETE CASCADE
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_timeline_read_events_event "
        "ON timeline_read_events (event_id)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body_json TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            pinned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            notified_at TEXT,
            poll_anonymous INTEGER NOT NULL DEFAULT 0,
            poll_deadline TEXT
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_forum_posts_created "
        "ON forum_posts (pinned DESC, id DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_forum_posts_notified "
        "ON forum_posts (notified_at) WHERE notified_at IS NULL"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            allow_multi INTEGER NOT NULL DEFAULT 0,
            ord INTEGER NOT NULL,
            FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_forum_polls_post "
        "ON forum_polls (post_id, ord)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_poll_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            ord INTEGER NOT NULL,
            FOREIGN KEY (poll_id) REFERENCES forum_polls(id) ON DELETE CASCADE
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_poll_votes (
            poll_id INTEGER NOT NULL,
            option_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(poll_id, option_id, user_id),
            FOREIGN KEY (option_id) REFERENCES forum_poll_options(id) ON DELETE CASCADE
        );
    """)
    _migrate_forum_polls(conn, cur)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            author_user_id TEXT NOT NULL,
            body_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_forum_comments_post "
        "ON forum_comments (post_id, id DESC)"
    )
    # 评论两级嵌套：parent_id=直接回复目标，root_id=所属顶层评论（分组键），edited_at=编辑时间
    cur.execute("PRAGMA table_info(forum_comments)")
    _fc_cols = [row[1] for row in cur.fetchall()]
    for _col, _ddl in (
        ("parent_id", "ALTER TABLE forum_comments ADD COLUMN parent_id INTEGER"),
        ("root_id", "ALTER TABLE forum_comments ADD COLUMN root_id INTEGER"),
        ("edited_at", "ALTER TABLE forum_comments ADD COLUMN edited_at TEXT"),
    ):
        if _col not in _fc_cols:
            cur.execute(_ddl)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_forum_comments_root "
        "ON forum_comments (root_id, id)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forum_post_tags (
            post_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (post_id, tag_id),
            FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES forum_tags(id) ON DELETE CASCADE
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_forum_post_tags_tag "
        "ON forum_post_tags (tag_id)"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tools_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            click_count INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("PRAGMA table_info(tools_links)")
    _tl_cols = [row[1] for row in cur.fetchall()]
    if "click_count" not in _tl_cols:
        cur.execute(
            "ALTER TABLE tools_links ADD COLUMN click_count INTEGER NOT NULL DEFAULT 0"
        )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tools_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tools_link_tags (
            link_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (link_id, tag_id),
            FOREIGN KEY (link_id) REFERENCES tools_links(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tools_tags(id) ON DELETE CASCADE
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tools_icon_cache (
            domain TEXT PRIMARY KEY,
            bytes BLOB,
            content_type TEXT,
            fetched_at TEXT NOT NULL,
            not_found INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_reports (
            week_key TEXT NOT NULL,
            group_id INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (week_key, group_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lottery_draw_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            drawn_at TEXT NOT NULL,
            result_type TEXT NOT NULL,
            value INTEGER,
            rarity TEXT,
            zero_streak_after INTEGER NOT NULL DEFAULT 0
        );
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_lottery_draw_log_time "
        "ON lottery_draw_log (drawn_at)"
    )
    conn.commit()
