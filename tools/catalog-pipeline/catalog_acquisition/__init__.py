"""Offline acquisition foundation; deliberately independent of JEM import code."""

from .adapters import AdapterDiagnostic, SourceAdapter, SyntheticAdapter
from .discovered import DiscoveredProductEntry, discovered_entry_id, discovered_product_entry
from .identity import CanonicalIdentityRegistry, IdentityLink, SourceIdentityRegistry, canonical_identity, source_identity
from .paths import LayoutRegistry, category_slug, create_layout, image_filename, model_key, safe_join, technical_sheet_filename
from .serialization import canonical_bytes, content_fingerprint
from .storage import atomic_write, sha256_bytes, verify_hash, write_once
from .schema_validation import SchemaValidationError, validate, validate_schema_keywords

__all__ = [
    "AdapterDiagnostic", "SourceAdapter", "SyntheticAdapter", "SourceIdentityRegistry", "CanonicalIdentityRegistry", "IdentityLink",
    "DiscoveredProductEntry", "discovered_entry_id", "discovered_product_entry",
    "source_identity", "canonical_identity", "LayoutRegistry", "category_slug", "create_layout", "image_filename", "model_key", "safe_join", "technical_sheet_filename",
    "canonical_bytes", "content_fingerprint", "atomic_write", "sha256_bytes",
    "verify_hash", "write_once", "SchemaValidationError", "validate", "validate_schema_keywords",
]
