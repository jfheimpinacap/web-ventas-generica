"""The single canonical JSON/fingerprint policy for the pipeline."""
from __future__ import annotations
import hashlib, json, unicodedata
from pathlib import PurePath

VOLATILE_FIELDS = frozenset({"created_at", "updated_at", "captured_at", "observed_at", "run_started_at", "absolute_path"})
UNORDERED_COLLECTION_FIELDS = frozenset({"aliases", "blocking_issue_codes", "additional_source_categories"})

def _normalize(value: object, *, fingerprint: bool = False, field: str = "") -> object:
    if isinstance(value, str): return unicodedata.normalize("NFC", value).replace("\\", "/") if field.endswith("path") else unicodedata.normalize("NFC", value)
    if isinstance(value, PurePath): return value.as_posix()
    if isinstance(value, dict):
        return {str(k): _normalize(v, fingerprint=fingerprint, field=str(k)) for k, v in sorted(value.items()) if not (fingerprint and str(k) in VOLATILE_FIELDS)}
    if isinstance(value, (list, tuple)):
        items = [_normalize(v, fingerprint=fingerprint, field=field) for v in value]
        return sorted(items, key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True)) if field in UNORDERED_COLLECTION_FIELDS else items
    if value is None or isinstance(value, (bool, int, float)): return value
    raise TypeError(f"Unsupported canonical JSON value: {type(value).__name__}")

def canonical_bytes(value: object) -> bytes:
    return (json.dumps(_normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def content_fingerprint(value: dict[str, object]) -> str:
    if "schema_version" not in value or "rules_version" not in value:
        raise ValueError("Fingerprints require schema_version and rules_version")
    return hashlib.sha256((json.dumps(_normalize(value, fingerprint=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
