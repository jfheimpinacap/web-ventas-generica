"""Discovery entries preserve authoritative findings before canonical resolution."""
from __future__ import annotations
from dataclasses import dataclass
from .errors import PipelineError
from .identity import SourceIdentity

SOURCE_ROLES = frozenset({"authoritative_existence", "supplemental"})
DISCOVERY_IDENTITY_RULE_VERSION = "discovery-identity-v1"

class SupplementalDiscoveryError(PipelineError): code = "SUPPLEMENTAL_CANNOT_DISCOVER"

@dataclass(frozen=True)
class DiscoveredProductEntry:
    discovered_entry_id: str
    authoritative_source_identity_value: str
    source_role: str
    raw_observation_ids: tuple[str, ...]
    canonical_identity_value: str | None
    canonical_candidate_identity_values: tuple[str, ...]
    resolution_status: str
    blocking_issue_codes: tuple[str, ...]
    original_categories: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    supplemental_source_identity_values: tuple[str, ...]
    review_status: str

def discovered_entry_id(authoritative_source_identity: SourceIdentity) -> str:
    """Stable while the authoritative source identity is stable; never a physical key."""
    return f"{DISCOVERY_IDENTITY_RULE_VERSION}:{authoritative_source_identity.value}"

def discovered_product_entry(authoritative_source_identity: SourceIdentity, *, source_role: str,
                             raw_observation_ids: tuple[str, ...], canonical_identity_value: str | None = None,
                             canonical_candidate_identity_values: tuple[str, ...] = (),
                             resolution_status: str = "missing", blocking_issue_codes: tuple[str, ...] = (),
                             original_categories: tuple[str, ...] = (), evidence_ids: tuple[str, ...] = (),
                             supplemental_source_identity_values: tuple[str, ...] = (),
                             review_status: str = "pending") -> DiscoveredProductEntry:
    if source_role not in SOURCE_ROLES: raise ValueError("unknown source role")
    if source_role != "authoritative_existence":
        raise SupplementalDiscoveryError("A supplemental source cannot create an official discovered entry")
    return DiscoveredProductEntry(discovered_entry_id(authoritative_source_identity), authoritative_source_identity.value,
        source_role, raw_observation_ids, canonical_identity_value, canonical_candidate_identity_values,
        resolution_status, blocking_issue_codes, original_categories, evidence_ids,
        supplemental_source_identity_values, review_status)
