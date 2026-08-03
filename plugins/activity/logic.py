import random
from datetime import datetime, timedelta


def build_ring(users: list[str], rng=random) -> list[tuple[str, str]]:
    """shuffle 后错位成单环，返回 [(uid, next_uid), ...]，无自匹配。"""
    if len(users) < 2:
        raise ValueError("匹配活动至少需要 2 人")
    shuffled = list(users)
    rng.shuffle(shuffled)
    return [(shuffled[i], shuffled[(i + 1) % len(shuffled)]) for i in range(len(shuffled))]


def relay_assignments(users: list[str], rng=random) -> list[tuple[str, str, int]]:
    """接龙链 [(uid, next_uid, seq), ...]，末位 next_uid=None。"""
    if not users:
        raise ValueError("接龙活动至少需要 1 人")
    shuffled = list(users)
    rng.shuffle(shuffled)
    out = []
    for i, uid in enumerate(shuffled):
        nxt = shuffled[i + 1] if i + 1 < len(shuffled) else None
        out.append((uid, nxt, i + 1))
    return out


def current_turn(members: list[dict]) -> dict | None:
    for m in sorted(members, key=lambda x: x["seq"]):
        if m["status"] == "pending":
            return m
    return None


def next_pending(members: list[dict], after_seq: int) -> dict | None:
    for m in sorted(members, key=lambda x: x["seq"]):
        if m["seq"] > after_seq and m["status"] == "pending":
            return m
    return None


def last_done(members: list[dict], before_seq: int) -> dict | None:
    done = [m for m in members if m["status"] == "done" and m["seq"] < before_seq]
    return max(done, key=lambda x: x["seq"], default=None)


def is_timeout(received_at: str | None, now: datetime, hours: float) -> bool:
    if not received_at:
        return False
    try:
        start = datetime.strptime(received_at, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return now - start > timedelta(hours=hours)


def relay_done(members: list[dict]) -> bool:
    return all(m["status"] != "pending" for m in members)
