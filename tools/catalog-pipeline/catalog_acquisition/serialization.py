"""Compatibility exports for the pipeline's neutral serialization policy."""
from catalog_pipeline_common.serialization import (UNORDERED_COLLECTION_FIELDS,
 VOLATILE_FIELDS, canonical_bytes, content_fingerprint)

__all__ = ["UNORDERED_COLLECTION_FIELDS", "VOLATILE_FIELDS", "canonical_bytes", "content_fingerprint"]
