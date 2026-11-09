from concurrent.futures import ThreadPoolExecutor

from core.command_rate_limit import CommandRateLimiter


def test_window_rolling_boundary_and_rejections_do_not_extend():
    now = [0.0]
    limiter = CommandRateLimiter(lambda: now[0])
    for _ in range(10):
        assert limiter.acquire(1, 20)[0]
    now[0] = 30
    for _ in range(10):
        assert limiter.acquire(1, 20)[0]
    assert limiter.acquire(1, 20) == (False, 30, True)
    now[0] = 59.1
    assert limiter.acquire(1, 20) == (False, 1, True)
    now[0] = 60
    for _ in range(10):
        assert limiter.acquire(1, 20)[0]
    assert limiter.acquire(1, 20) == (False, 30, False)
    assert limiter.acquire(2, 20)[0]


def test_concurrency_exact_capacity_and_restart_cleanup():
    now = [0]
    limiter = CommandRateLimiter(lambda: now[0])
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: limiter.acquire(1, 20), range(100)))
    assert sum(r[0] for r in results) == 20
    assert sum(r[2] for r in results) == 1
    assert CommandRateLimiter(lambda: now[0]).acquire(1, 20)[0]
    now[0] = 60
    assert limiter.acquire(2, 20)[0]
    assert 1 not in limiter._windows and 1 not in limiter._notices


def test_window_disabled_no_state():
    limiter = CommandRateLimiter()
    for _ in range(30):
        assert limiter.acquire(1, 0) == (True, 0, False)
    assert not limiter._windows
