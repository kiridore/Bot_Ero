from datetime import datetime

from core.timeline_client import emit_event

from .defs import TITLE_DEFS


def get_title_def(title_id):
    return TITLE_DEFS.get(title_id)


def get_lottery_title_ids():
    return [tid for tid, data in TITLE_DEFS.items() if data.get("unlock_type") == "lottery"]


def _title_collection_progress(unlocked: int, total: int, width: int = 16) -> str:
    if total <= 0:
        return f"[{'░' * width}] 0/0 (0.0%)"
    pct = max(0.0, min(100.0, 100.0 * unlocked / total))
    filled = min(int(width * unlocked / total), width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {unlocked}/{total} ({pct:.1f}%)"


def evaluate_and_unlock_titles(dbmanager, user_id, checkin_dt: datetime | None = None):
    user_id = int(user_id)
    newly_unlocked = []

    def unlock(tid):
        if tid in TITLE_DEFS and not dbmanager.titles.has(user_id, tid):
            dbmanager.titles.unlock(user_id, tid)
            newly_unlocked.append(tid)
            # 社区时间线事件（best-effort；dedup 按 用户+称号，天然幂等，解锁无回滚）
            tdef = TITLE_DEFS[tid]
            emit_event(
                source="title",
                actor_id=str(user_id),
                actor_qq=str(user_id),
                title="{id:%s} 解锁称号「%s」" % (user_id, tdef["name"]),
                description="稀有度：%s" % tdef.get("rarity", "unknown"),
                target_url="/profile",
                dedup_key="title:%s:%s" % (user_id, tid),
            )

    if checkin_dt is not None:
        h, m = checkin_dt.hour, checkin_dt.minute
        # 时段
        if (h > 8 or (h == 8 and m >= 0)) and h < 12:
            unlock(201)
        if (h > 14 or (h == 14 and m >= 0)) and h < 16:
            unlock(202)
        if (h > 17 or (h == 17 and m >= 30)) and (h < 18 or (h == 18 and m <= 30)):
            unlock(203)
        if (h > 1 or (h == 1 and m >= 0)) and h < 5:
            unlock(204)
        weekday = checkin_dt.weekday()  # mon=0
        if (weekday == 6 and (h > 23 or (h == 23 and m >= 30))) or (weekday == 0 and h < 8):
            unlock(205)

        # 日期
        mmdd = (checkin_dt.month, checkin_dt.day)
        mapping = {
            (5, 1): 212,
            (4, 1): 213,
            (6, 1): 214,
            (10, 24): 215,
            (2, 22): 216,
            (2, 14): 217,
            (8, 11): 218,
            (3, 14): 219,
            (1, 1): 221,
        }
        if mmdd in mapping:
            unlock(mapping[mmdd])
        if checkin_dt.month == checkin_dt.day:
            unlock(220)
        if (h == 23 and m == 59) or (h == 0 and m in (0, 1)):
            unlock(210)
        if h == 0 and m == 0:
            unlock(211)

    # 累计打卡天数
    total_days = dbmanager.checkin.count_all_days(user_id)
    if total_days >= 30:
        unlock(209)
    if total_days >= 100:
        unlock(208)
    if total_days >= 200:
        unlock(207)
    if total_days >= 365:
        unlock(206)

    # 抽奖画像（兼容旧数据：draw_count 至少为 total_spent）
    profile = dbmanager.lottery.profile(user_id)
    spent = dbmanager.lottery.spent(user_id)
    draw_count = max(profile["draw_count"], spent)
    if draw_count >= 1:
        unlock(230)
    if draw_count >= 10:
        unlock(231)
    if draw_count >= 25:
        unlock(232)
    if draw_count >= 50:
        unlock(233)
    if draw_count >= 100:
        unlock(234)
    if draw_count >= 200:
        unlock(242)
    if draw_count >= 500:
        unlock(243)
    if draw_count >= 1000:
        unlock(244)
    if draw_count >= 3:
        unlock(247)
    if draw_count >= 75:
        unlock(248)
    if draw_count >= 150:
        unlock(249)
    if draw_count >= 300:
        unlock(250)
    if draw_count >= 2000:
        unlock(251)
    if profile["duplicate_count"] >= 1:
        unlock(227)
    if profile["duplicate_count"] >= 10:
        unlock(228)
    if profile["duplicate_count"] >= 100:
        unlock(229)
    if profile["has_hit_ten"] >= 1:
        unlock(235)
    if profile["max_zero_streak"] >= 3:
        unlock(236)
    if profile["max_zero_streak"] >= 10:
        unlock(237)
    if profile["max_zero_streak"] >= 1:
        unlock(252)
    if profile["max_zero_streak"] >= 5:
        unlock(253)
    if profile["max_zero_streak"] >= 15:
        unlock(254)
    if profile["max_zero_streak"] >= 30:
        unlock(255)
    if profile["total_zeros"] >= 1:
        unlock(256)
    if profile["total_zeros"] >= 10:
        unlock(257)
    if profile["total_zeros"] >= 50:
        unlock(258)
    if profile["total_zeros"] >= 100:
        unlock(259)
    if profile["total_zeros"] >= 300:
        unlock(260)

    # 累计周常任务完成次数
    quest_total = dbmanager.quest.completion(user_id)
    if quest_total >= 5:
        unlock(238)
    if quest_total >= 15:
        unlock(239)
    if quest_total >= 30:
        unlock(240)
    if quest_total >= 50:
        unlock(241)

    # 累计全清周数
    clear_count = dbmanager.quest.clear_count(user_id)
    if clear_count >= 1:
        unlock(261)
    if clear_count >= 3:
        unlock(262)
    if clear_count >= 5:
        unlock(263)
    if clear_count >= 10:
        unlock(264)
    if clear_count >= 20:
        unlock(265)

    # 依赖称号状态的进度称号
    titles = dbmanager.titles.list(user_id)
    cnt = len(titles)
    if cnt >= 10:
        unlock(222)
    if cnt >= 20:
        unlock(223)
    if cnt >= 30:
        unlock(224)
    if cnt >= 50:
        unlock(245)
    if cnt >= 100:
        unlock(246)

    titles = dbmanager.titles.list(user_id)
    if any((TITLE_DEFS.get(t, {}).get("rarity") == "legendary") for t in titles):
        unlock(225)

    equipped = dbmanager.titles.equipped_all(user_id)
    if len(equipped) == 3 and all((TITLE_DEFS.get(t, {}).get("rarity") == "legendary") for t in equipped):
        unlock(226)

    return newly_unlocked