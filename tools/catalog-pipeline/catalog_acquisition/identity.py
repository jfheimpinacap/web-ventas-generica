"""Separate, versioned source and canonical product identities."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import unicodedata
from .errors import IdentityCollisionError, PipelineError

SOURCE_IDENTITY_RULE_VERSION = "source-identity-v1"
CANONICAL_IDENTITY_RULE_VERSION = "canonical-identity-v1"

class SourceIdentityCollisionError(IdentityCollisionError): code = "SOURCE_IDENTITY_COLLISION"
class CanonicalIdentityCollisionError(IdentityCollisionError): code = "CANONICAL_IDENTITY_COLLISION"
class AmbiguousIdentityLinkError(PipelineError): code = "AMBIGUOUS_IDENTITY_LINK"

@dataclass(frozen=True)
class SourceIdentity:
    value: str
    rule_version: str
    source_namespace: str
    stable_source_key: str
    key_strategy: str

@dataclass(frozen=True)
class CanonicalIdentity:
    value: str
    rule_version: str
    brand: str
    model: str
    variant: str | None
    discriminator: str | None
    supersedes: str | None = None

@dataclass(frozen=True)
class IdentityLink:
    source_identity_value: str
    canonical_identity_value: str | None
    candidate_canonical_identity_values: tuple[str, ...]
    matching_rule: str
    matching_rule_version: str
    resolution_status: str
    human_decision_id: str | None
    blocking: bool

    def assert_importable(self, *, type_mapping_approved: bool, category_mapping_approved: bool,
                          blocking_issue_codes: tuple[str, ...] = ()) -> None:
        rule_approved = self.resolution_status == "derived_by_approved_rule" and bool(self.matching_rule and self.matching_rule_version)
        manual_approved = self.resolution_status == "manual_approved" and bool(self.human_decision_id)
        if (self.blocking or self.canonical_identity_value is None or not (rule_approved or manual_approved)
                or not type_mapping_approved or not category_mapping_approved or blocking_issue_codes):
            raise AmbiguousIdentityLinkError("Source-to-canonical link is not approved", source_identity_value=self.source_identity_value)

def _digest(version: str, components: tuple[str, ...]) -> str:
    payload = "\x1f".join((version, *(unicodedata.normalize("NFC", item) for item in components)))
    return f"{version}:sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

def source_identity(source_namespace: str, stable_source_key: str, *, key_strategy: str = "native-v1") -> SourceIdentity:
    """Identity of one source record; observed labels, URL and adapter version are excluded."""
    if not source_namespace or not stable_source_key or not key_strategy:
        raise ValueError("source namespace, stable key and versioned key strategy are required")
    value = _digest(SOURCE_IDENTITY_RULE_VERSION, (source_namespace, key_strategy, stable_source_key))
    return SourceIdentity(value, SOURCE_IDENTITY_RULE_VERSION, source_namespace, stable_source_key, key_strategy)

def canonical_identity(brand: str, model: str, variant: str | None = None, *, discriminator: str | None = None,
                       supersedes: str | None = None) -> CanonicalIdentity:
    """Calculate a candidate identity; this does not adopt or approve the product."""
    if not brand or not model: raise ValueError("canonical brand and exact model are required")
    components = (brand, model, variant or "", discriminator or "")
    value = _digest(CANONICAL_IDENTITY_RULE_VERSION, components)
    return CanonicalIdentity(value, CANONICAL_IDENTITY_RULE_VERSION, brand, model, variant, discriminator, supersedes)

class _Registry:
    error_type: type[IdentityCollisionError]
    def __init__(self) -> None: self._origins: dict[str, tuple[str, ...]] = {}
    def register(self, value: str, *components: str) -> None:
        current=tuple(components); previous=self._origins.get(value)
        if previous is not None and previous != current:
            raise self.error_type("Identity maps to different components", value=value, previous=previous, current=current)
        self._origins[value]=current

class SourceIdentityRegistry(_Registry): error_type = SourceIdentityCollisionError
class CanonicalIdentityRegistry(_Registry): error_type = CanonicalIdentityCollisionError
