from __future__ import annotations
import base64
from cryptography.fernet import Fernet
from .config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        # dev fallback: derive a deterministic key from JWT_SECRET (NOT for prod)
        raw = (settings.JWT_SECRET + "-h3c-fernet").encode()[:32].ljust(32, b"0")
        key = base64.urlsafe_b64encode(raw).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_str(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_str(token: str) -> str:
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode()).decode()
