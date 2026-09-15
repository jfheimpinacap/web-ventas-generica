from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

@dataclass(frozen=True)
class BinaryInfo:
    kind: str
    extension: str
    mime: str

def detect_binary(data: bytes) -> BinaryInfo:
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return BinaryInfo("image", ".jpg", "image/jpeg")
    if data.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in data[-24:]:
        return BinaryInfo("image", ".png", "image/png")
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return BinaryInfo("image", ".webp", "image/webp")
    if data.startswith(b"%PDF-") and b"%%EOF" in data[-1024:]:
        return BinaryInfo("technical_sheet", ".pdf", "application/pdf")
    raise ValueError("INVALID_BINARY")

def validate_public_url(url: str, resolver=socket.getaddrinfo) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL pública HTTP/HTTPS inválida")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost":
        raise ValueError("destino local prohibido")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = [ipaddress.ip_address(item[4][0]) for item in resolver(host, parsed.port or 443, type=socket.SOCK_STREAM)]
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("destino privado o no público prohibido")
