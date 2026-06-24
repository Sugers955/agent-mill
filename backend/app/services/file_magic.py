"""File magic bytes validation — verifies actual file type regardless of client Content-Type."""
from __future__ import annotations

# Magic bytes signatures (prefix, expected MIME type)
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"\x1f\x8b", "application/gzip"),
    (b"RIFF", "audio/wav"),
    (b"\xca\xfe\xba\xbe", "application/java"),  # Java class
    (b"\xef\xbb\xbf", "text/plain"),  # UTF-8 BOM text
    (b"{\rtf", "text/rtf"),  # RTF
]

ALLOWED_UPLOAD_MIMES: set[str] = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/pdf", "application/zip", "application/gzip",
    "text/plain", "text/markdown", "text/csv", "text/rtf",
    "application/json", "application/xml", "text/html",
    "text/yaml", "text/x-python", "text/x-javascript",
    "application/java",
}


def detect_mime(data: bytes) -> str | None:
    """Detect MIME type from file header bytes. Returns None if unknown."""
    for prefix, mime in _MAGIC_SIGNATURES:
        if data.startswith(prefix):
            # Special case: RIFF could be WebP
            if mime == "audio/wav" and len(data) >= 12 and data[8:12] == b"WEBP":
                return "image/webp"
            return mime
    # Check for plain text (first 512 bytes are all printable)
    try:
        sample = data[:512]
        if sample.decode("utf-8").isprintable():
            return "text/plain"
    except (UnicodeDecodeError, ValueError):
        pass
    return None


def is_allowed_upload(mime: str | None) -> bool:
    """Check if detected MIME is in the allowed upload set."""
    if mime is None:
        return False
    return mime in ALLOWED_UPLOAD_MIMES
