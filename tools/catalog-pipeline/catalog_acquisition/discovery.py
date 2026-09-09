"""Safe, deterministic discovery contracts (no product canonicalisation)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Literal

URL_RULE_VERSION = "technical-url-v1"
REQUEST_POLICY_VERSION = "discovery-http-v1"
MANIFEST_VERSION = "discovery-manifest-v1"
SourceRole = Literal["authoritative_existence", "supplemental"]

@dataclass(frozen=True)
class SourceDefinition:
    source: str
    display_name: str
    role: SourceRole
    start_url: str
    hosts: tuple[str, ...]
    path_prefix: str
    adapter_version: str
    structure_verified: bool = False
    structure_evidence_reference: str | None = None
    structure_evidence_rule_version: str | None = None
    structure_evidence_sha256: str | None = None

SOURCES = {
    "ep": SourceDefinition("ep", "EP Equipment", "authoritative_existence",
        "https://ep-equipment.com/es/productos/", ("ep-equipment.com", "www.ep-equipment.com"),
        "/es/productos/", "ep-discovery-v1", False, None, None, None),
    "gam": SourceDefinition("gam", "GAM Rentals Chile", "supplemental",
        "https://online.gamrentals.com/cl/826-ep", ("online.gamrentals.com",),
        "/cl/826-ep", "gam-discovery-v1", False, None, None, None),
}

@dataclass(frozen=True)
class LinkEvidence:
    origin_url: str
    locator: str
    raw_href: str
    snapshot_reference: str
    rule_id: str
    rule_version: str

@dataclass(frozen=True)
class DiscoveryLink:
    original_url: str
    canonical_url: str | None
    kind: str
    label_raw: str
    label_hint: str
    model_hint: str | None
    evidence: LinkEvidence
    reason: str = ""

@dataclass
class ParseResult:
    page_type: str
    links: list[DiscoveryLink] = field(default_factory=list)
    categories: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    json_ld: list[object] = field(default_factory=list)
    embedded_json: list[object] = field(default_factory=list)

def source_key(source: str, canonical_url: str) -> str:
    """URL-derived source key; labels/models never participate."""
    return f"url-v1:sha256:{sha256((source+'\0'+canonical_url).encode()).hexdigest()}"

def candidate_record(source: SourceDefinition, link: DiscoveryLink) -> dict[str, object]:
    if link.canonical_url is None:
        raise ValueError("candidate requires a canonical URL")
    key = source_key(source.source, link.canonical_url)
    return {"source": source.source, "source_role": source.role,
        "source_identity": f"{source.source}:{key}", "source_key": key,
        "source_url": link.original_url, "canonical_url": link.canonical_url,
        "label_raw": link.label_raw, "label_hint": link.label_hint,
        "model_hint": link.model_hint, "source_categories": [],
        "discovery_page": link.evidence.origin_url,
        "evidence_reference": link.evidence.snapshot_reference,
        "locator": link.evidence.locator, "rule_version": link.evidence.rule_version,
        "warnings": [], "review_status": "pending"}

def stable_dict(value: object) -> dict[str, object]:
    return asdict(value)  # type: ignore[arg-type]
