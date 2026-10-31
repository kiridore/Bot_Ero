"""浏览器运输层测试：不安装或启动真实Chromium，不访问网络。"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, Mock

import pytest

from plugins.news import weibo_browser as browser_mod

FEED_URL = "https://m.weibo.cn/api/container/getIndex?containerid=1076036279793937"


@pytest.fixture
def browser_api(monkeypatch):
    package = ModuleType("playwright")
    package.__path__ = []
    api = ModuleType("playwright.sync_api")
    manager = MagicMock()
    api.sync_playwright = Mock(return_value=manager)
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    playwright = manager.__enter__.return_value
    browser = playwright.chromium.launch.return_value
    context = browser.new_context.return_value
    page = context.new_page.return_value
    page.url = browser_mod.HOMEPAGE
    response = page.expect_event.return_value.__enter__.return_value.value.response.return_value
    response.status = 200
    response.json.return_value = {"ok": 1, "data": {"cards": []}}
    return manager, playwright, browser, context, page, response


def test_only_opens_homepage_and_closes_resources(browser_api):
    manager, playwright, browser, context, page, response = browser_api
    assert browser_mod.fetch_homepage() == response.json.return_value
    playwright.chromium.launch.assert_called_once_with(headless=True, timeout=30000)
    browser.new_context.assert_called_once_with()
    page.expect_event.assert_called_once_with("requestfinished", predicate=browser_mod._is_feed_request, timeout=45000)
    page.goto.assert_called_once_with(browser_mod.HOMEPAGE, wait_until="domcontentloaded", timeout=45000)
    assert {call[0] for call in page.method_calls} == {"expect_event", "goto"}
    assert {call[0] for call in context.method_calls} == {"new_page"}
    browser.close.assert_called_once_with()
    manager.__exit__.assert_called_once()


@pytest.mark.parametrize("url,expected", [
    (FEED_URL, True), (FEED_URL + "&page=1", True),
    (FEED_URL + "&page=2", False), (FEED_URL + "&since_id=1", False),
    (FEED_URL.replace("6279793937", "123"), False),
    (FEED_URL.replace("https:", "http:"), False),
    (FEED_URL.replace("m.weibo.cn", "m.weibo.cn.evil.test"), False),
    ("https://m.weibo.cn/api/container/getIndex?type=uid&value=6279793937", False),
])
def test_matches_only_homepage_feed(url, expected):
    assert browser_mod._is_feed_request(Mock(url=url)) is expected


@pytest.mark.parametrize("phase", ["new_context", "goto", "wait", "json", "login", "http", "payload"])
def test_failure_releases_browser(browser_api, phase):
    manager, _, browser, _, page, response = browser_api
    if phase == "new_context":
        browser.new_context.side_effect = RuntimeError("context failed")
    elif phase == "goto":
        page.goto.side_effect = TimeoutError("navigation timeout")
    elif phase == "wait":
        page.expect_event.return_value.__exit__.side_effect = TimeoutError("body completion timeout")
    elif phase == "json":
        response.json.side_effect = ValueError("not JSON")
    elif phase == "login":
        page.url = "https://passport.weibo.com/sso/signin"
    elif phase == "http":
        response.status = 432
    else:
        response.json.return_value = {"ok": 0}
    with pytest.raises((RuntimeError, TimeoutError, ValueError)):
        browser_mod.fetch_homepage()
    browser.close.assert_called_once_with()
    manager.__exit__.assert_called_once()


@pytest.mark.parametrize("payload", [[], {}, {"ok": 1}, {"ok": 1, "data": {}}, {"ok": 1, "data": {"cards": {}}}])
def test_invalid_response(browser_api, payload):
    _, _, browser, _, _, response = browser_api
    response.json.return_value = payload
    with pytest.raises(ValueError):
        browser_mod.fetch_homepage()
    browser.close.assert_called_once_with()


def test_headers_without_finished_body_never_read_json(browser_api):
    _, _, browser, _, page, response = browser_api
    response.status = 200
    page.expect_event.return_value.__exit__.side_effect = TimeoutError("body never finished")
    with pytest.raises(TimeoutError):
        browser_mod.fetch_homepage()
    response.json.assert_not_called()
    browser.close.assert_called_once_with()


def test_missing_response_is_failure(browser_api):
    _, _, browser, _, page, _ = browser_api
    page.expect_event.return_value.__enter__.return_value.value.response.return_value = None
    with pytest.raises(ValueError, match="响应缺失"):
        browser_mod.fetch_homepage()
    browser.close.assert_called_once_with()


def test_launch_failure_stops_playwright(browser_api):
    manager, playwright, browser, _, _, _ = browser_api
    playwright.chromium.launch.side_effect = RuntimeError("browser missing")
    with pytest.raises(RuntimeError, match="browser missing"):
        browser_mod.fetch_homepage()
    browser.close.assert_not_called()
    manager.__exit__.assert_called_once()


def test_missing_dependency_has_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(RuntimeError, match="weibo-browser-deployment.md"):
        browser_mod.fetch_homepage()


def test_cli_only_prints_public_summary(monkeypatch, capsys):
    post = {"id": "123", "created_at": "today", "user": {"id": 6279793937, "user_token": "DO_NOT_PRINT"}}
    monkeypatch.setattr(browser_mod, "fetch_homepage", lambda: {"data": {"cards": [{"card_type": 9, "mblog": post}]}})
    assert browser_mod.main() == 0
    output = capsys.readouterr().out
    assert "6279793937" in output and "id=123" in output
    assert "DO_NOT_PRINT" not in output


def test_cli_failure_is_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(browser_mod, "fetch_homepage", Mock(side_effect=TimeoutError("timed out")))
    assert browser_mod.main() == 1
    assert "检查失败" in capsys.readouterr().err
