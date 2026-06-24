from __future__ import annotations
import base64
import re
from cryptography.fernet import Fernet
from .config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        # dev fallback: derive a deterministic key from JWT_SECRET (NOT for prod)
        raw = (settings.JWT_SECRET + "-agent-mill-fernet").encode()[:32].ljust(32, b"0")
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


def mask_str(value: str | None, visible_chars: int = 4) -> str | None:
    """脱敏字符串，只保留最后 visible_chars 位。"""
    if not value:
        return value
    if len(value) <= visible_chars:
        return "****"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def mask_email(email: str) -> str:
    """邮箱脱敏。"""
    if not email or "@" not in email:
        return mask_str(email)
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """手机号脱敏。"""
    if not phone:
        return phone
    phone = str(phone)
    if len(phone) < 7:
        return mask_str(phone)
    return phone[:3] + "****" + phone[-4:]


def mask_id_card(id_card: str) -> str:
    """身份证号脱敏。"""
    if not id_card:
        return id_card
    id_card = str(id_card)
    if len(id_card) < 10:
        return mask_str(id_card)
    return id_card[:4] + "**********" + id_card[-4:]


def mask_dict(data: dict, rules: dict | None = None) -> dict:
    """按规则脱敏字典中的字段。默认脱敏 email/phone/id_card。"""
    if rules is None:
        rules = {
            "email": mask_email,
            "phone": mask_phone,
            "mobile": mask_phone,
            "id_card": mask_id_card,
        }

    masked = {}
    for key, value in data.items():
        if key in rules and isinstance(value, str):
            masked[key] = rules[key](value)
        else:
            masked[key] = value
    return masked


def mask_text(text: str) -> str:
    """脱敏文本中的敏感信息。"""
    if not text:
        return text
    # 脱敏邮箱
    text = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', lambda m: mask_email(m.group()), text)
    # 脱敏手机号
    text = re.sub(r'1[3-9]\d{9}', lambda m: mask_phone(m.group()), text)
    return text
