"""微博手机首页读取；直接运行本文件可只读检查，不加载机器人配置。"""
import sys
from urllib.parse import parse_qs, urlsplit

WEIBO_UID = "6279793937"
HOMEPAGE = f"https://m.weibo.cn/u/{WEIBO_UID}"


def _is_feed_request(request) -> bool:
    url = urlsplit(request.url)
    params = parse_qs(url.query)
    return (url.scheme == "https" and url.netloc == "m.weibo.cn"
            and url.path == "/api/container/getIndex"
            and params.get("containerid") == [f"107603{WEIBO_UID}"]
            and params.get("page", ["1"]) == ["1"]
            and "since_id" not in params)


def fetch_homepage() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("微博源需要安装Playwright与Chromium，见docs/weibo-browser-deployment.md") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, timeout=30000)
        try:
            context = browser.new_context()
            page = context.new_page()
            # 等正文完成而非仅等响应头，避免json()被未结束的响应阻塞。
            with page.expect_event("requestfinished", predicate=_is_feed_request, timeout=45000) as pending:
                page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=45000)
            response = pending.value.response()
            if response is None:
                raise ValueError("微博首页内容响应缺失")
            if response.status != 200:
                raise ValueError(f"微博首页内容请求失败：HTTP {response.status}")
            if urlsplit(page.url).netloc != "m.weibo.cn":
                raise ValueError("微博主页停留在登录或访客页面")
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("ok") != 1:
                raise ValueError("微博首页返回异常或需要登录")
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("cards"), list):
                raise ValueError("微博首页卡片列表无效")
            return payload
        finally:
            browser.close()


def main() -> int:
    try:
        payload = fetch_homepage()
        posts = [card["mblog"] for card in payload["data"]["cards"]
                 if card.get("card_type") == 9
                 and str(card.get("mblog", {}).get("user", {}).get("id")) == WEIBO_UID]
        if not posts:
            raise ValueError("没有取得目标账号的微博，请检查页面访问条件")
        print(f"微博首页读取成功：账号 {WEIBO_UID}，{len(posts)} 条（含置顶，仅首页）")
        for post in posts[:3]:
            print(f"id={post['id']} published_at={post['created_at']}")
        return 0
    except Exception as exc:
        print(f"微博首页检查失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
