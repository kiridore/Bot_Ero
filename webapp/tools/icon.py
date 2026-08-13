"""工具箱卡片图标服务端解析。

浏览器直连 `https://<domain>/favicon.ico` 常因站点未在默认路径放图标而失败——
现代站点图标声明在首页 HTML `<link rel="icon">`。本模块先试默认路径，失败则
抓首页解析 link 标签取真实图标地址，结果由调用方入库缓存（含负缓存）。

安全：
- 只允许已收录链接的域名（路由层校验），避免开放代理滥用；
- 域名解析到内网/回环/链路本地地址一律拒绝（防 SSRF）；
- 上游请求均有超时上限与体积上限，跟随重定向 ≤3 跳。
"""

import os
import re
import socket
from urllib.parse import urljoin

import requests

MAX_BYTES = 512 * 1024  # 图标体积上限
TIMEOUT_FAVICON = 4.0   # 直接路径探测
TIMEOUT_HTML = 5.0      # 首页抓取
TIMEOUT_ICON = 4.0      # 解析出的候选图标
UA = "Mozilla/5.0 (compatible; BotEroWebapp/1.0; +https://littlero.tech)"
PROXY = os.environ.get("BOTERO_ICON_PROXY")  # 可选：如 "http://127.0.0.1:7890"

_TAG_RE = re.compile(r"<link\b[^>]*>", re.I)
_ATTR_RE = re.compile(r'([\w-]+)\s*=\s*(["\'])(.*?)\2', re.I)

_IMAGE_EXT = (".ico", ".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp", ".avif")


def _session() -> requests.Session:
    s = requests.Session()
    s.max_redirects = 3
    if PROXY:
        s.proxies = {"http": PROXY, "https": PROXY}
    return s


def _is_private_host(domain: str) -> bool:
    """域名解析到内网/回环/链路本地地址 → 拒绝（防 SSRF）。
    解析失败视为不可判定 → 不拦截（连接本身会自然失败）。"""
    try:
        infos = socket.getaddrinfo(domain, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        ip = str(info[4][0])
        if (
            ip.startswith("127.") or ip == "::1"
            or ip.startswith("10.") or ip.startswith("192.168.")
            or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", ip)
            or ip.startswith("169.254.") or ip.startswith("0.")
            or ip == "::" or ip.lower().startswith("fe80")
        ):
            return True
    return False


def _link_icon_candidates(html: str):
    """解析首页 HTML 中的 <link rel="*icon*"> href 列表（保持文档顺序）。"""
    for tag in _TAG_RE.findall(html):
        attrs = {k.lower(): v for k, _, v in _ATTR_RE.findall(tag)}
        rel = attrs.get("rel", "")
        if "icon" not in rel.lower():
            continue
        href = attrs.get("href")
        if href and not href.strip().lower().startswith("data:"):
            yield href.strip()


def _looks_like_image(url: str, content_type: str, lenient: bool = False) -> bool:
    """默认路径 favicon.ico 放宽（浏览器能显示的 octet-stream/未知类型也算），
    HTML 声明候选保持严格（image/* 或图片扩展名）。体积上限是真正的兜底。"""
    ct = content_type.lower()
    if ct.startswith("image/") or ct in ("application/octet-stream", "application/x-icon"):
        return True
    if lenient:
        return True
    return url.split("?", 1)[0].lower().endswith(_IMAGE_EXT)


def _get(url: str, timeout: float):
    try:
        resp = _session().get(
            url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True
        )
        return resp
    except requests.RequestException:
        return None


def fetch_icon(domain: str) -> tuple[bytes, str] | None:
    """解析域名图标。返回 (bytes, content_type)；无图标返回 None。"""
    if _is_private_host(domain):
        return None

    # 1) 默认路径（放宽内容判断：浏览器能显示的这里都算）
    resp = _get(f"https://{domain}/favicon.ico", TIMEOUT_FAVICON)
    if (
        resp is not None and resp.status_code == 200
        and resp.content and len(resp.content) <= MAX_BYTES
        and _looks_like_image(resp.url, resp.headers.get("Content-Type", ""), lenient=True)
    ):
        ct = resp.headers.get("Content-Type") or "image/x-icon"
        return resp.content, ct

    # 2) 首页解析 <link rel="icon">
    page = _get(f"https://{domain}/", TIMEOUT_HTML)
    if page is not None and page.status_code == 200:
        for href in _link_icon_candidates(page.text):
            icon_url = urljoin(f"https://{domain}/", href)
            icon_resp = _get(icon_url, TIMEOUT_ICON)
            if (
                icon_resp is not None and icon_resp.status_code == 200
                and icon_resp.content and len(icon_resp.content) <= MAX_BYTES
                and _looks_like_image(icon_resp.url, icon_resp.headers.get("Content-Type", ""))
            ):
                ct = icon_resp.headers.get("Content-Type") or "image/x-icon"
                return icon_resp.content, ct
    return None
