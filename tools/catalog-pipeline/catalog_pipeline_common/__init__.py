"""Dependency-neutral primitives shared by catalog pipeline stages."""
from .serialization import canonical_bytes, content_fingerprint

__all__ = ["canonical_bytes", "content_fingerprint"]
