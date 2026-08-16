"""小埃周报生成器：周一 08:00 聚合 message_log.db + data.db，写 weekly_reports 并通知。"""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta

from core.base import TimedHeartbeatPlugin
from core.config import GROUP_ID, WEB_BASE_URL, WEEKLY_NOTIFY_ENABLED
from core.cq import text
from core.db.message_log import MessageLogManager
from core.onebot_client import resolve_display_name
from core.utils import get_monday_to_monday, register_plugin

try:
    import jieba.posseg as pseg

    _JIEBA_OK = True
except ImportError:  # pragma: no cover - 模拟依赖缺失时验证
    pseg = None
    _JIEBA_OK = False

_boot_checked = False

_LINK_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_REDEEM_RE = re.compile(r"^[A-Za-z]{4}-[A-Za-z]{4}-[A-Za-z]{4}$")
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]"
)
_CHINESE_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_PURE_DIGIT_RE = re.compile(r"^\d+$")

_STOPWORDS = {
    "的", "了", "吗", "啊", "嗯", "呢", "吧", "呀", "在", "和", "很", "也", "都", "就",
    "是", "不", "有", "这", "那", "我", "你", "他", "她", "它", "们", "与", "及",
    "或", "等", "被", "把", "让", "向", "从", "对", "为", "着", "过", "之", "其",
    "又", "才", "还", "而", "且", "并", "再", "可", "能", "会", "要", "去", "来",
    "说", "看", "想", "到", "得", "地", "没", "太", "挺", "最", "更", "只", "个",
    "位", "次", "年", "月", "日", "时", "分", "秒", "今天", "昨天", "明天", "现在",
    "什么", "怎么", "为什么", "因为", "所以", "但是", "如果", "然后", "就是", "可以",
    "没有", "一个", "一下", "知道", "觉得", "还是", "这个", "那个", "这样", "那样",
    "不过", "已经", "正在", "比较", "非常", "特别", "有点", "一点", "一直", "一起",
    "还有", "或者", "以及", "却", "仍", "则", "哦", "哈", "嘿", "唉", "嘛",
}


def _name(user_id) -> str:
    try:
        return resolve_display_name(str(user_id))
    except Exception:
        return str(user_id)


def _safe_int(value, default=0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _last_week_bounds() -> tuple[str, str]:
    """返回最近一个完整周界：周一 08:00 → 次周一 08:00。

    定时任务在周一 08:00 运行，此时 get_monday_to_monday() 返回新一周；
    因此周报周界 = get_monday_to_monday() 的 start 再往前退 7 天。
    """
    start, _end = get_monday_to_monday()
    start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    report_end = start
    report_start = (start_dt - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    return report_start, report_end


@register_plugin
class WeeklyReportPlugin(TimedHeartbeatPlugin):
    name = "weekly_report"
    description = "每周一 08:00 聚合生成群周报，并写入 weekly_reports 归档"

    RUN_AT = "08:00"
    RUN_WEEKDAYS = [1]

    def match(self, event_type: str = "message") -> bool:
        global _boot_checked
        if event_type != "meta":
            return False
        if not _boot_checked:
            return True  # 启动补偿：首个 meta 触发一次补漏
        return self.should_run_on_heartbeat(event_type)

    def handle(self):
        try:
            self._handle()
        except Exception:
            from core.logger import logger

            logger.exception("周报生成失败")

    # ------------------------------------------------------------------
    def _handle(self):
        global _boot_checked
        scheduled = self.should_run_on_heartbeat("meta")

        if not _boot_checked:
            try:
                start, end = _last_week_bounds()
                self._generate_week(start, end)
            finally:
                _boot_checked = True

        if scheduled:
            start, end = _last_week_bounds()
            self._generate_week(start, end)

    def _generate_week(self, start: str, end: str):
        week_key = start.split(" ")[0]
        group_id = int(GROUP_ID)
        db = self.dbmanager
        if db.weekly.get(week_key, group_id) is not None:
            return

        data = self._aggregate(db, group_id, week_key, start, end)
        db.weekly.upsert(week_key, group_id, data)

        if WEEKLY_NOTIFY_ENABLED:
            issue = data["period"]["issue"]
            url = f"{WEB_BASE_URL}/weekly/{week_key}"
            self.api.send_msg(text(f"📰 第 {issue} 期《小埃周报》已出版\n{url}"))

    # ------------------------------------------------------------------
    def _aggregate(self, db, group_id: int, week_key: str, start: str, end: str) -> dict:
        messages = self._load_messages(group_id, start, end)
        period = self._build_period(db, group_id, week_key, start, end, messages)
        headline = self._build_headline(db, group_id, start, end, period)
        checkin = self._build_checkin(db, start, end)
        lottery = self._build_lottery(db, start, end)
        voices = self._build_voices(messages)
        activity = self._build_activity(db, group_id, start, end, messages)
        trivia = self._build_trivia(db, group_id, week_key, messages, activity)
        return {
            "period": period,
            "headline": headline,
            "checkin": checkin,
            "lottery": lottery,
            "voices": voices,
            "activity": activity,
            "trivia": trivia,
        }

    def _load_messages(self, group_id: int, start: str, end: str) -> list[dict]:
        mlog = MessageLogManager()
        try:
            return mlog.get_week(group_id, start, end)
        finally:
            mlog.close()

    # ------------------------------------------------------------------
    def _build_period(self, db, group_id, week_key, start, end, messages) -> dict:
        total_messages = len(messages)
        total_chars = sum(len(m.get("text", "")) for m in messages)
        issue = db.weekly.issue(group_id, week_key) + 1
        return {
            "issue": issue,
            "start": start.split(" ")[0],
            "end": end.split(" ")[0],
            "total_messages": total_messages,
            "total_chars": total_chars,
        }

    def _build_headline(self, db, group_id, start, end, period) -> dict:
        # 1. 仙人彩大奖 / 奖池滚存
        db.cur.execute(
            "SELECT period_key, winning_digits, bet_total FROM immortal_lottery_results"
            " WHERE group_id = ? AND drawn_at >= ? AND drawn_at < ?"
            " ORDER BY drawn_at DESC LIMIT 1",
            (int(group_id), start, end),
        )
        imm = db.cur.fetchone()
        if imm:
            period_key, digits, pool = imm[0], str(imm[1]), int(imm[2] or 0)
            jackpot_hit = False
            db.cur.execute(
                "SELECT user_id, digits FROM immortal_lottery_bets WHERE group_id = ? AND period_key = ?",
                (int(group_id), str(period_key)),
            )
            for _uid, bet in db.cur.fetchall():
                if sum(1 for i in range(4) if digits[i] == str(bet)[i]) >= 3:
                    jackpot_hit = True
                    break
            return {
                "kind": "immortal_jackpot",
                "title": "仙人彩大奖落定" if jackpot_hit else "仙人彩奖池滚存",
                "body": f"本期开奖号码 {digits}，奖池 {pool} 积分。",
                "stats": [{"label": "开奖号码", "value": digits}, {"label": "奖池", "value": pool}],
            }

        # 2. 群活动本周结束
        db.cur.execute(
            "SELECT a.id, a.title FROM activities a"
            " LEFT JOIN activity_members m ON m.activity_id = a.id"
            " WHERE a.group_id = ? AND a.status = 'finished'"
            " AND a.finished_at >= ? AND a.finished_at < ?"
            " GROUP BY a.id HAVING COUNT(m.user_id) > 0"
            " ORDER BY a.finished_at DESC LIMIT 1",
            (int(group_id), start, end),
        )
        act = db.cur.fetchone()
        if act:
            return {
                "kind": "activity",
                "title": f"群活动「{act[1]}」本周收官",
                "body": "本周有群活动结束并完成归档。",
                "stats": [],
            }

        # 3. 新传说称号解锁
        db.cur.execute(
            "SELECT COUNT(*) FROM user_titles WHERE unlocked_at >= ? AND unlocked_at < ?",
            (start, end),
        )
        new_titles = db.cur.fetchone()[0]
        if new_titles > 0:
            return {
                "kind": "legendary_title",
                "title": "本周有人解锁了新称号",
                "body": f"本周共解锁 {new_titles} 个新称号。",
                "stats": [{"label": "新称号", "value": new_titles}],
            }

        # 4. 总消息数破历史纪录
        db.cur.execute(
            "SELECT MAX(CAST(json_extract(data_json, '$.period.total_messages') AS INTEGER))"
            " FROM weekly_reports WHERE group_id = ?",
            (int(group_id),),
        )
        row = db.cur.fetchone()
        prev_max = _safe_int(row[0] if row else None)
        if period["total_messages"] > prev_max and prev_max > 0:
            return {
                "kind": "message_record",
                "title": "群消息数破历史纪录",
                "body": f"本周共 {period['total_messages']} 条消息，刷新历史纪录。",
                "stats": [{"label": "本周消息", "value": period["total_messages"]}],
            }

        # 5. 卧底局数（v1 简化：有卧底局即作为花絮头条候选，不在头条阶段重复扫描）
        return {
            "kind": "plain",
            "title": "平淡的一周",
            "body": "本周群内风平浪静，大家都在好好生活。",
            "stats": [],
        }

    def _build_checkin(self, db, start, end) -> dict:
        from core.config import REMEDY_MARKER

        db.cur.execute(
            "SELECT user_id, checkin_date, content FROM checkin_records"
            " WHERE checkin_date >= ? AND checkin_date < ?"
            " ORDER BY id ASC",
            (start, end),
        )
        rows = db.cur.fetchall()
        normal = []
        remedy = 0
        for user_id, checkin_date, content in rows:
            if content == REMEDY_MARKER:
                remedy += 1
            else:
                normal.append((user_id, checkin_date, content))

        total = len(normal)
        users = len({r[0] for r in normal})
        daily_avg = round(total / 7, 1)

        day_set: dict[int, set] = {}
        first: dict[int, tuple] = {}
        for user_id, checkin_date, content in normal:
            try:
                day = (datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=8)).strftime("%Y-%m-%d")
            except ValueError:
                day = checkin_date[:10]
            day_set.setdefault(int(user_id), set()).add(day)
            if int(user_id) not in first:
                first[int(user_id)] = (checkin_date, content)

        full_week = [
            {"user_id": uid, "name": _name(uid)}
            for uid, days in day_set.items()
            if len(days) >= 7
        ]
        full_week.sort(key=lambda x: x["user_id"])

        images = []
        for user_id, (checkin_date, content) in first.items():
            slug = str(content).replace("{", "").replace("}", "").replace("-", "")
            images.append({
                "user_id": user_id,
                "name": _name(user_id),
                "url": f"/thumb/{user_id}/{slug}",
            })
        images.sort(key=lambda x: x["user_id"])

        return {
            "total": total,
            "users": users,
            "daily_avg": daily_avg,
            "full_week": full_week,
            "remedy": remedy,
            "images": images,
        }

    def _build_lottery(self, db, start, end) -> dict:
        start_date = start.split(" ")[0]
        end_date = end.split(" ")[0]
        total_draws, users = db.lottery.weekly_draw_totals(start_date, end_date)
        top = db.lottery.weekly_top_drawer(start_date, end_date)
        lucky_rows = db.lottery.weekly_lucky_from_log(start, end)
        unlucky = db.lottery.weekly_unlucky_from_log(start, end)

        db.cur.execute(
            "SELECT winning_digits, bet_total FROM immortal_lottery_results"
            " WHERE group_id = ? AND drawn_at >= ? AND drawn_at < ?"
            " ORDER BY drawn_at DESC LIMIT 1",
            (int(GROUP_ID), start, end),
        )
        imm = db.cur.fetchone()
        immortal = None
        if imm:
            digits = str(imm[0])
            pool = int(imm[1] or 0)
            winners = 0
            db.cur.execute(
                "SELECT period_key FROM immortal_lottery_results"
                " WHERE group_id = ? AND drawn_at >= ? AND drawn_at < ?"
                " ORDER BY drawn_at DESC LIMIT 1",
                (int(GROUP_ID), start, end),
            )
            pk_row = db.cur.fetchone()
            if pk_row:
                period_key = str(pk_row[0])
                db.cur.execute(
                    "SELECT digits FROM immortal_lottery_bets WHERE group_id = ? AND period_key = ?",
                    (int(GROUP_ID), period_key),
                )
                for (bet,) in db.cur.fetchall():
                    if sum(1 for i in range(4) if digits[i] == str(bet)[i]) >= 2:
                        winners += 1
            immortal = {"digits": digits, "pool": pool, "winners": winners}

        lucky = [
            {"user_id": r["user_id"], "name": _name(r["user_id"]), "hit": r["hit"]}
            for r in lucky_rows
        ]
        unlucky_out = None
        if unlucky:
            unlucky_out = {
                "user_id": unlucky["user_id"],
                "name": _name(unlucky["user_id"]),
                "zero_streak": unlucky["zero_streak"],
            }

        return {
            "total_draws": total_draws,
            "per_user": round(total_draws / users, 1) if users else 0.0,
            "top": {
                "user_id": top["user_id"],
                "name": _name(top["user_id"]),
                "count": top["count"],
            } if top else None,
            "lucky": lucky,
            "unlucky": unlucky_out,
            "immortal": immortal,
        }

    def _build_voices(self, messages) -> dict:
        quotes = self._pick_quotes(messages)
        memes, meme_king = self._detect_memes(messages)
        words = self._hot_words(messages)
        return {
            "quotes": quotes,
            "memes": memes,
            "meme_king": meme_king,
            "words": words,
        }

    def _is_command(self, text: str) -> bool:
        return text.lstrip().startswith("/")

    def _is_redeem_code(self, text: str) -> bool:
        return bool(_REDEEM_RE.match(text.strip())) or text.strip().upper() in {
            "TEST-CODE-TEST",
            "ONLY-YEAR-ONCE",
        }

    def _pick_quotes(self, messages) -> list[dict]:
        candidates = []
        for m in messages:
            text = (m.get("text") or "").strip()
            if not text:
                continue
            if self._is_command(text):
                continue
            if "@" in text or _LINK_RE.search(text) or self._is_redeem_code(text):
                continue
            if len(text) < 8 or len(text) > 80:
                continue
            reply_count = sum(
                1 for other in messages if other.get("reply_to_msg_id") == m.get("msg_id")
            )
            score = 0.0
            if reply_count > 0:
                score += 1
            if m.get("has_image"):
                score += 0.5
            if _EMOJI_RE.search(text):
                score += 0.5
            candidates.append({
                "user_id": int(m["user_id"]),
                "text": text,
                "at": m.get("sent_at", "")[:16],
                "score": score,
                "reply_count": reply_count,
            })

        # 每用户限 1 条（保留最高分）
        best_by_user: dict[int, dict] = {}
        for c in candidates:
            uid = c["user_id"]
            if uid not in best_by_user or c["score"] > best_by_user[uid]["score"]:
                best_by_user[uid] = c
        uniq = sorted(best_by_user.values(), key=lambda x: (-x["score"], x["at"]))
        if not uniq:
            return []

        top = uniq[:2]
        rest = uniq[2:]
        random.shuffle(rest)
        picked = top + rest[:3]
        picked.sort(key=lambda x: (-x["score"], x["at"]))
        return [
            {"user_id": q["user_id"], "name": _name(q["user_id"]), "text": q["text"], "at": q["at"]}
            for q in picked
        ]

    def _detect_memes(self, messages) -> tuple[list[dict], dict | None]:
        groups: dict[str, list[dict]] = {}
        for m in messages:
            text = (m.get("text") or "").strip()
            if self._is_command(text) or len(text) <= 2:
                continue
            groups.setdefault(text, []).append({
                "user_id": int(m["user_id"]),
                "sent_at": m.get("sent_at", ""),
            })

        events: list[dict] = []
        for text, entries in groups.items():
            entries.sort(key=lambda x: x["sent_at"])
            i = 0
            while i < len(entries):
                j = i
                window_users: set[int] = set()
                while j < len(entries):
                    try:
                        t0 = datetime.strptime(entries[i]["sent_at"], "%Y-%m-%d %H:%M:%S")
                        t1 = datetime.strptime(entries[j]["sent_at"], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        j += 1
                        continue
                    if (t1 - t0).total_seconds() > 1800:
                        break
                    window_users.add(entries[j]["user_id"])
                    j += 1
                if len(window_users) >= 3:
                    events.append({
                        "text": text,
                        "users": set(window_users),
                        "count": j - i,
                    })
                    i = j
                else:
                    i += 1

        meme_counter: dict[str, dict] = {}
        user_counter: dict[int, int] = {}
        for ev in events:
            item = meme_counter.setdefault(ev["text"], {"text": ev["text"], "count": 0, "users": set()})
            item["count"] += ev["count"]
            item["users"] |= ev["users"]
            for uid in ev["users"]:
                user_counter[uid] = user_counter.get(uid, 0) + 1

        memes = []
        for item in meme_counter.values():
            memes.append({
                "text": item["text"],
                "count": item["count"],
                "users": len(item["users"]),
            })
        memes.sort(key=lambda x: (-x["count"], -x["users"]))

        meme_king = None
        if user_counter:
            best_uid = max(user_counter, key=lambda uid: (user_counter[uid], -uid))
            meme_king = {
                "user_id": best_uid,
                "name": _name(best_uid),
                "count": user_counter[best_uid],
            }
        return memes[:3], meme_king

    def _hot_words(self, messages) -> list[dict]:
        if _JIEBA_OK:
            return self._hot_words_jieba(messages)
        return self._hot_words_fallback(messages)

    def _tokenize(self, text: str) -> list[str]:
        if _JIEBA_OK:
            words = []
            for word, flag in pseg.lcut(text):
                if flag and flag[0] in ("n", "v", "a"):
                    words.append(word)
            return words
        return _CHINESE_WORD_RE.findall(text)

    def _hot_words_jieba(self, messages) -> list[dict]:
        per_user_day: set[tuple[int, str, str]] = set()
        freq: dict[str, int] = {}
        for m in messages:
            text = (m.get("text") or "").strip()
            if not text or self._is_command(text):
                continue
            day = m.get("sent_at", "")[:10]
            uid = int(m["user_id"])
            for word in self._tokenize(text):
                word = word.strip()
                if len(word) < 2 or word in _STOPWORDS or _PURE_DIGIT_RE.match(word):
                    continue
                key = (uid, day, word)
                if key in per_user_day:
                    continue
                per_user_day.add(key)
                freq[word] = freq.get(word, 0) + 1
        words = [{"w": w, "c": c} for w, c in freq.items()]
        words.sort(key=lambda x: (-x["c"], x["w"]))
        return words[:30]

    def _hot_words_fallback(self, messages) -> list[dict]:
        per_user_day: set[tuple[int, str, str]] = set()
        freq: dict[str, int] = {}
        for m in messages:
            text = (m.get("text") or "").strip()
            if not text or self._is_command(text):
                continue
            day = m.get("sent_at", "")[:10]
            uid = int(m["user_id"])
            for word in _CHINESE_WORD_RE.findall(text):
                if word in _STOPWORDS or _PURE_DIGIT_RE.match(word):
                    continue
                key = (uid, day, word)
                if key in per_user_day:
                    continue
                per_user_day.add(key)
                freq[word] = freq.get(word, 0) + 1
        words = [{"w": w, "c": c} for w, c in freq.items()]
        words.sort(key=lambda x: (-x["c"], x["w"]))
        return words[:30]

    # ------------------------------------------------------------------
    def _build_activity(self, db, group_id, start, end, messages) -> dict:
        daily = [0] * 7
        hour_count: dict[tuple[int, int], int] = {}
        talkers: dict[int, dict] = {}
        night_owl: dict[int, int] = {}
        early_bird: dict[int, int] = {}
        for m in messages:
            try:
                dt = datetime.strptime(m.get("sent_at", ""), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            daily[dt.weekday()] += 1
            key = (dt.weekday(), dt.hour)
            hour_count[key] = hour_count.get(key, 0) + 1
            uid = int(m["user_id"])
            item = talkers.setdefault(uid, {"count": 0, "chars": 0})
            item["count"] += 1
            item["chars"] += len(m.get("text", ""))
            if 1 <= dt.hour <= 5:
                night_owl[uid] = night_owl.get(uid, 0) + 1
            elif 8 <= dt.hour <= 12:
                early_bird[uid] = early_bird.get(uid, 0) + 1

        total_messages = len(messages)
        talker_list = [
            {
                "user_id": uid,
                "name": _name(uid),
                "count": v["count"],
                "ratio": round(v["count"] / total_messages, 4) if total_messages else 0.0,
            }
            for uid, v in talkers.items()
        ]
        talker_list.sort(key=lambda x: (-x["count"], x["user_id"]))
        talkers_top5 = talker_list[:5]

        peak = None
        if hour_count:
            best_key = max(hour_count, key=lambda k: (hour_count[k], -k[0], -k[1]))
            peak = {
                "day": best_key[0],
                "hour": best_key[1],
                "count": hour_count[best_key],
            }

        night_owl_out = None
        if night_owl:
            uid = max(night_owl, key=lambda k: (night_owl[k], -k))
            night_owl_out = {"user_id": uid, "name": _name(uid), "count": night_owl[uid]}
        early_bird_out = None
        if early_bird:
            uid = max(early_bird, key=lambda k: (early_bird[k], -k))
            early_bird_out = {"user_id": uid, "name": _name(uid), "count": early_bird[uid]}

        # 周常全清
        db.cur.execute(
            "SELECT COUNT(*) FROM quest_weekly_clears WHERE week_key = ?",
            (_last_week_bounds()[0].split(" ")[0],),
        )
        quest_clears = _safe_int(db.cur.fetchone()[0])

        # 新解锁称号
        db.cur.execute(
            "SELECT user_id, title_id FROM user_titles WHERE unlocked_at >= ? AND unlocked_at < ?",
            (start, end),
        )
        new_titles = [
            {"user_id": int(r[0]), "name": _name(int(r[0])), "title_id": int(r[1])}
            for r in db.cur.fetchall()
        ]

        # 本周结束的活动
        db.cur.execute(
            "SELECT id, title, type FROM activities WHERE group_id = ?"
            " AND status = 'finished' AND finished_at >= ? AND finished_at < ?"
            " ORDER BY finished_at ASC",
            (int(group_id), start, end),
        )
        activities = [
            {"id": int(r[0]), "title": str(r[1]), "type": str(r[2])}
            for r in db.cur.fetchall()
        ]

        # 卧底局数：读 game_records JSON
        spy_games = self._count_spy_games(group_id, start, end)

        return {
            "daily": daily,
            "peak": peak,
            "talkers": talkers_top5,
            "night_owl": night_owl_out,
            "early_bird": early_bird_out,
            "quest_clears": quest_clears,
            "new_titles": new_titles,
            "activities": activities,
            "spy_games": spy_games,
        }

    def _count_spy_games(self, group_id: int, start: str, end: str) -> int:
        import os

        base = f"server_data/game_records/{int(group_id)}"
        if not os.path.isdir(base):
            return 0
        start_ts = datetime.strptime(start, "%Y-%m-%d %H:%M:%S").timestamp()
        end_ts = datetime.strptime(end, "%Y-%m-%d %H:%M:%S").timestamp()
        count = 0
        for fname in os.listdir(base):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(base, fname), encoding="utf-8") as f:
                    data = json.load(f)
                ended = float(data.get("ended_at", 0))
                if start_ts <= ended < end_ts:
                    count += 1
            except Exception:
                continue
        return count

    def _build_trivia(self, db, group_id, week_key, messages, activity) -> dict:
        # 蝉联榜：话痨王连庄
        streaks = []
        prev = self._prev_top_talker(db, group_id, week_key)
        if prev and activity["talkers"]:
            cur_top = activity["talkers"][0]
            if str(prev["user_id"]) == str(cur_top["user_id"]):
                weeks = int(prev.get("weeks", 1)) + 1
                streaks.append({
                    "user_id": cur_top["user_id"],
                    "name": cur_top["name"],
                    "weeks": weeks,
                    "title": "话痨王",
                })

        # 涨幅榜：比上周发言增长最多者
        prev_counts = self._prev_talker_counts(db, group_id, week_key)
        gains = []
        for t in activity["talkers"]:
            uid = t["user_id"]
            prev_c = prev_counts.get(uid, 0)
            delta = t["count"] - prev_c
            if delta > 0:
                gains.append({"user_id": uid, "name": t["name"], "delta": delta})
        gains.sort(key=lambda x: -x["delta"])
        gains = gains[:3]

        records = self._cold_facts(messages)

        return {"streaks": streaks, "gains": gains, "records": records}

    def _prev_week_key(self, week_key: str) -> str:
        dt = datetime.strptime(week_key, "%Y-%m-%d") - timedelta(days=7)
        return dt.strftime("%Y-%m-%d")

    def _prev_report(self, db, group_id, week_key):
        prev_key = self._prev_week_key(week_key)
        return db.weekly.get(prev_key, group_id)

    def _prev_top_talker(self, db, group_id, week_key) -> dict | None:
        prev = self._prev_report(db, group_id, week_key)
        if not prev:
            return None
        talkers = prev["data_json"].get("activity", {}).get("talkers", [])
        if not talkers:
            return None
        return talkers[0]

    def _prev_talker_counts(self, db, group_id, week_key) -> dict[int, int]:
        prev = self._prev_report(db, group_id, week_key)
        if not prev:
            return {}
        return {
            int(t["user_id"]): int(t["count"])
            for t in prev["data_json"].get("activity", {}).get("talkers", [])
        }

    def _cold_facts(self, messages) -> list[dict]:
        facts = []
        if messages:
            longest = max(messages, key=lambda m: len(m.get("text", "")))
            facts.append({
                "label": "最长单条消息",
                "detail": f"{len(longest.get('text', ''))} 字",
                "user_id": int(longest["user_id"]),
                "name": _name(int(longest["user_id"])),
            })

        per_day: dict[str, int] = {}
        per_day_images: dict[str, int] = {}
        per_minute: dict[str, int] = {}
        for m in messages:
            try:
                dt = datetime.strptime(m.get("sent_at", ""), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            day = dt.strftime("%Y-%m-%d")
            per_day[day] = per_day.get(day, 0) + 1
            if m.get("has_image"):
                per_day_images[day] = per_day_images.get(day, 0) + 1
            minute = dt.strftime("%Y-%m-%d %H:%M")
            per_minute[minute] = per_minute.get(minute, 0) + 1

        if per_day:
            best_day = max(per_day, key=lambda k: (per_day[k], k))
            facts.append({"label": "单日最多消息", "detail": f"{best_day} · {per_day[best_day]} 条"})
        if per_day_images:
            best_img_day = max(per_day_images, key=lambda k: (per_day_images[k], k))
            facts.append({"label": "最多图片的一天", "detail": f"{best_img_day} · {per_day_images[best_img_day]} 张"})
        if per_minute:
            best_minute = max(per_minute, key=lambda k: (per_minute[k], k))
            facts.append({"label": "1 分钟内连发最多", "detail": f"{best_minute} · {per_minute[best_minute]} 条"})

        random.shuffle(facts)
        return facts[:3]
