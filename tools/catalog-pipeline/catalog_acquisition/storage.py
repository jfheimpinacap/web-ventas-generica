"""Local-only atomic and write-once storage."""
from __future__ import annotations
import hashlib, os, tempfile
from pathlib import Path
from .errors import HashMismatchError, ImmutableEvidenceError

def sha256_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def verify_hash(data: bytes, expected: str) -> None:
    actual = sha256_bytes(data)
    if actual != expected: raise HashMismatchError("SHA-256 verification failed", expected=expected, actual=actual)

def atomic_write(target: Path, data: bytes, expected_sha256: str | None = None) -> None:
    if expected_sha256: verify_hash(data, expected_sha256)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def write_once(target: Path, data: bytes, expected_sha256: str | None = None) -> bool:
    if expected_sha256: verify_hash(data, expected_sha256)
    if target.exists():
        if target.read_bytes() == data: return False
        raise ImmutableEvidenceError("Raw evidence identity already contains different bytes", target=target.name)
    atomic_write(target, data, expected_sha256)
    return True
