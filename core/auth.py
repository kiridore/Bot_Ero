import base64
import hmac
import hashlib

from core.config import AUTH_SALT, AUTH_SALT_OLD


def _signature(uid: str, salt: str) -> bytes:
    return hmac.new(
        salt.encode("utf-8"),
        uid.encode("utf-8"),
        hashlib.sha256,
    ).digest()[:12]


def make_login_key(user_id: int | str) -> str:
    uid = str(int(user_id))
    sig_b64 = base64.urlsafe_b64encode(_signature(uid, AUTH_SALT)).decode("ascii").rstrip("=")
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
    except (ValueError, UnicodeDecodeError):
        return None
    for salt in [AUTH_SALT, *AUTH_SALT_OLD]:
        if hmac.compare_digest(sig, _signature(uid, salt)):
            return uid
    return None
