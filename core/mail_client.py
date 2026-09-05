"""cloud-mail（Skymail）发信客户端：登录换 token、发件账号自动发现、best-effort 发邮件。

API 文档：https://doc.skymail.ink/api/api-doc.html
配置：config.yaml mail 节（可选；url/email/password 任一为空 = 功能关闭）。
属性访问 config.*（不用导入期绑定，遵守 specs/conventions.md §测试隔离与文案同步）。
"""

import base64
from functools import lru_cache

import requests

from core import config

_TIMEOUT = 15
_MAX_ATTACHMENTS = 10  # 服务端上限

# ponytail: token 进程内缓存；服务端换密钥需重启进程才重登，可接受
_token: str | None = None


def _configured() -> bool:
    return bool(config.CLOUDMAIL_URL and config.CLOUDMAIL_EMAIL and config.CLOUDMAIL_PASSWORD)


def _call(method: str, path: str, *, token: str | None = None, json_body: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token  # 文档要求：不加 Bearer 前缀
    try:
        resp = requests.request(
            method, f"{config.CLOUDMAIL_URL.rstrip('/')}{path}",
            headers=headers, json=json_body, timeout=_TIMEOUT)
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return int(data.get("code") or 0), data


def _login(force: bool = False) -> str | None:
    global _token
    if _token and not force:
        return _token
    result = _call("POST", "/api/login", json_body={
        "email": config.CLOUDMAIL_EMAIL, "password": config.CLOUDMAIL_PASSWORD})
    if not result or result[0] != 200:
        return None
    token = (result[1].get("data") or {}).get("token")
    if not token:
        return None
    _token = str(token)
    return _token


@lru_cache(maxsize=1)
def _account_id() -> int | None:
    token = _login()
    if not token:
        return None
    result = _call("GET", "/api/account/list?size=1", token=token)
    if not result or result[0] != 200:
        return None
    items = result[1].get("data") or []
    if not items:
        return None
    return int(items[0]["accountId"])


def send_email(
    to: list[str],
    subject: str,
    html: str,
    text: str | None = None,
    sender_name: str | None = None,
    attachments: list[tuple[str, bytes, str | None]] | None = None,
) -> tuple[bool, str]:
    """发邮件（best-effort，绝不抛出）。attachments: [(文件名, 内容, MIME|None)]。

    返回 (成功?, 说明)。未配置时返回 (False, "邮箱服务未配置")，功能可安全闲置。
    """
    if not _configured():
        return False, "邮箱服务未配置"
    if not subject or not html:
        return False, "主题与正文不能为空"
    to = [str(x).strip() for x in (to or []) if str(x).strip()]
    if not to:
        return False, "收件人不能为空"
    if attachments and len(attachments) > _MAX_ATTACHMENTS:
        return False, f"附件最多 {_MAX_ATTACHMENTS} 个"

    global _token
    account_id = _account_id()
    if account_id is None:
        # accountId/token 可能过期：清缓存强制重登重试一次
        _token = None
        _account_id.cache_clear()
        account_id = _account_id()
    if account_id is None:
        return False, "无法获取发件账号（登录失败或无邮箱账号）"
    token = _login()
    if not token:
        return False, "登录失败"

    payload: dict = {
        "accountId": account_id,
        "receiveEmail": to,
        "subject": subject,
        "content": html,
    }
    if text:
        payload["text"] = text
    name = sender_name or config.CLOUDMAIL_SENDER_NAME
    if name:
        payload["name"] = name
    if attachments:
        payload["attachments"] = [
            {
                "filename": fname,
                "content": base64.b64encode(data).decode("ascii"),
                **({"contentType": mime} if mime else {}),
            }
            for fname, data, mime in attachments
        ]

    result = _call("POST", "/api/email/send", token=token, json_body=payload)
    if result is None:
        return False, "网络错误或超时"
    code, body = result
    if code == 200:
        return True, "ok"
    # token 失效：强制重登再试一次（非 token 类失败重试无害，仍失败即返回服务端消息）
    fresh = _login(force=True)
    if fresh:
        result = _call("POST", "/api/email/send", token=fresh, json_body=payload)
        if result and result[0] == 200:
            return True, "ok"
    return False, str(body.get("message") or f"发送失败（code={code}）")
