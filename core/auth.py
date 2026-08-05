import base64
import hmac
import hashlib

from core.config import AUTH_SALT


def make_login_key(user_id: int | str) -> str:
    uid = str(int(user_id))
    sig = hmac.new(
        AUTH_SALT.encode("utf-8"),
        uid.encode("utf-8"),
        hashlib.sha256,
    ).digest()[:12]
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    payload = f"{uid}:{sig_b64}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def verify_login_key(key: str) -> str | None:
    if not key or not key.strip():
        return None
    try:
        padded = key.strip() + "=" * (-len(key.strip()) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        uid, sig_b64 = payload.split(":", 1)
        sig_padded = sig_b64 + "=" * (-len(sig_b64) % 4)
        sig = base64.urlsafe_b64decode(sig_padded.encode("ascii"))
        expected = hmac.new(
            AUTH_SALT.encode("utf-8"),
            uid.encode("utf-8"),
            hashlib.sha256,
        ).digest()[:12]
        if hmac.compare_digest(sig, expected):
            return uid
    except (ValueError, UnicodeDecodeError):
        return None
    return None
