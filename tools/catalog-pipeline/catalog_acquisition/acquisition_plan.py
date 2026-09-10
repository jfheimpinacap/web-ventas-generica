"""Offline-only authorization and URL gates for asset acquisition."""
from __future__ import annotations
import ipaddress, re
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit
from .discovery import SourceDefinition
from .paths import safe_join
from .schema_validation import validate as validate_schema
from .serialization import canonical_bytes

AUTH_VERSION="acquisition-authorization-v1"
POLICY_VERSION="asset-acquisition-v1"
SECRET_QUERY=re.compile(r"(?:token|signature|sig|credential|api[_-]?key|bearer|session|password|passwd|jwt|auth)",re.I)
AMBIGUOUS_ESCAPE=re.compile(r"%(?:2e|2f|5c|25)",re.I)

class AcquisitionBlocked(ValueError):
    def __init__(self,reason): super().__init__(reason); self.reason=reason

def fingerprint(value):
    semantic=dict(value); semantic.pop("authorization_fingerprint",None); semantic.pop("operational_timestamps",None)
    return sha256(canonical_bytes(semantic)).hexdigest()

def candidate_set_fingerprint(candidates):
    return sha256(canonical_bytes(sorted(candidates,key=lambda x:str(x.get("candidate_id") or x.get("media_candidate_id") or x.get("document_candidate_id"))))).hexdigest()

def _relative_evidence(root:Path,reference:str,digest:str):
    if not isinstance(reference,str) or PurePosixPath(reference).is_absolute(): raise AcquisitionBlocked("evidence_reference_invalid")
    path=safe_join(root,reference)
    try: data=path.read_bytes()
    except OSError as exc: raise AcquisitionBlocked("evidence_missing") from exc
    if sha256(data).hexdigest()!=digest: raise AcquisitionBlocked("evidence_hash_mismatch")

def validate_authorization(auth,root:Path,*,source:SourceDefinition,source_definition_fingerprint:str,
                           extraction_fingerprint:str,asset_fingerprint:str,candidates):
    validate_schema(auth,Path(__file__).parents[1]/"schemas/v1/acquisition-authorization.schema.json")
    if auth["schema_version"]!=AUTH_VERSION or auth["policy_version"]!=POLICY_VERSION: raise AcquisitionBlocked("authorization_version_mismatch")
    if auth["state"]!="approved": raise AcquisitionBlocked("authorization_not_approved")
    bindings={"source_namespace":source.source,"source_definition_version":"discovery-config-v1",
      "source_definition_fingerprint":source_definition_fingerprint,"adapter_version":source.adapter_version,
      "extraction_manifest_fingerprint":extraction_fingerprint,"asset_manifest_fingerprint":asset_fingerprint,
      "candidate_set_fingerprint":candidate_set_fingerprint(candidates)}
    for key,value in bindings.items():
        if auth.get(key)!=value: raise AcquisitionBlocked(f"{key}_mismatch")
    if auth["authorized_methods"]!=["GET"] or auth["authorized_schemes"]!=["https"]: raise AcquisitionBlocked("unsafe_transport_authorization")
    _relative_evidence(root,auth["structure_evidence_reference"],auth["structure_evidence_sha256"])
    _relative_evidence(root,auth["rights_evidence_reference"],auth["rights_evidence_sha256"])
    if not source.structure_verified: raise AcquisitionBlocked("source_structure_unverified")
    if source.structure_evidence_sha256!=auth["structure_evidence_sha256"]: raise AcquisitionBlocked("structure_evidence_binding_mismatch")
    calculated=fingerprint(auth)
    if auth["authorization_fingerprint"]!=calculated: raise AcquisitionBlocked("authorization_fingerprint_mismatch")
    return calculated

def validate_url(url:str,auth:dict)->str:
    try: parsed=urlsplit(url)
    except ValueError as exc: raise AcquisitionBlocked("url_invalid") from exc
    if parsed.scheme!="https" or not parsed.netloc: raise AcquisitionBlocked("url_https_required")
    if parsed.username is not None or parsed.password is not None: raise AcquisitionBlocked("url_userinfo_forbidden")
    if parsed.fragment: raise AcquisitionBlocked("url_fragment_forbidden")
    host=(parsed.hostname or "").rstrip(".").lower()
    if not host: raise AcquisitionBlocked("url_host_missing")
    try: ipaddress.ip_address(host)
    except ValueError: pass
    else: raise AcquisitionBlocked("url_ip_literal_forbidden")
    if host=="localhost" or host.endswith((".localhost",".local",".internal",".invalid")): raise AcquisitionBlocked("url_local_host_forbidden")
    scopes={x["host"].rstrip(".").lower():x for x in auth["host_scopes"]}
    if host not in scopes: raise AcquisitionBlocked("url_host_not_authorized")
    try: port=parsed.port
    except ValueError as exc: raise AcquisitionBlocked("url_port_invalid") from exc
    allowed=scopes[host]["port"]
    if (port or 443)!=allowed: raise AcquisitionBlocked("url_port_not_authorized")
    raw_path=parsed.path or "/"
    if "\\" in raw_path or AMBIGUOUS_ESCAPE.search(raw_path): raise AcquisitionBlocked("url_path_ambiguous")
    try: decoded=bytes(raw_path,"ascii").decode("ascii")
    except UnicodeError as exc: raise AcquisitionBlocked("url_path_non_ascii") from exc
    segments=decoded.split("/")
    if any(x in (".","..") for x in segments): raise AcquisitionBlocked("url_path_traversal")
    allowed_path=raw_path in scopes[host]["exact_paths"] or any(raw_path==p.rstrip("/") or raw_path.startswith(p.rstrip("/")+"/") for p in scopes[host]["path_prefixes"])
    if raw_path!="/robots.txt" and not allowed_path: raise AcquisitionBlocked("url_path_not_authorized")
    try: query=parse_qsl(parsed.query,keep_blank_values=True,strict_parsing=True)
    except ValueError as exc: raise AcquisitionBlocked("url_query_invalid") from exc
    permitted=set(auth["query_policy"]["allowed_names"])
    for name,_ in query:
        if SECRET_QUERY.search(name): raise AcquisitionBlocked("url_sensitive_query_forbidden")
        if name not in permitted: raise AcquisitionBlocked("url_query_not_authorized")
    normalized_query="&".join(f"{quote(k,safe='')}={quote(v,safe='')}" for k,v in query)
    netloc=host if allowed==443 else f"{host}:{allowed}"
    return urlunsplit(("https",netloc,raw_path,normalized_query,""))

@dataclass(frozen=True)
class PlanItem:
    candidate_id:str; state:str; reason:str; url:str|None

def build_plan(*,authorization,authorization_root,source,source_definition_fingerprint,
               extraction_fingerprint,asset_fingerprint,candidates):
    """Run every local gate. Callers construct transport only after ``transport_allowed``."""
    items=[]
    try:
        auth_fp=validate_authorization(authorization,authorization_root,source=source,
          source_definition_fingerprint=source_definition_fingerprint,extraction_fingerprint=extraction_fingerprint,
          asset_fingerprint=asset_fingerprint,candidates=candidates)
    except Exception as exc:
        reason=exc.reason if isinstance(exc,AcquisitionBlocked) else "authorization_invalid"
        return {"schema_version":"acquisition-plan-v1","transport_allowed":False,"authorization_fingerprint":None,
          "items":[asdict(PlanItem(_candidate_id(x),"blocked",reason,None)) for x in candidates],"network_requests":0}
    for candidate in sorted(candidates,key=_candidate_id):
        cid=_candidate_id(candidate); url=candidate.get("resolved_url") or candidate.get("candidate_url")
        if candidate.get("host_review_status")=="pending_host_review": items.append(PlanItem(cid,"pending","pending_host_review",None)); continue
        if candidate.get("resource_type") not in authorization["resource_types"]: items.append(PlanItem(cid,"blocked","resource_type_not_authorized",None)); continue
        try: safe=validate_url(url,authorization) if isinstance(url,str) else (_ for _ in ()).throw(AcquisitionBlocked("candidate_url_missing"))
        except AcquisitionBlocked as exc: items.append(PlanItem(cid,"blocked",exc.reason,None))
        else: items.append(PlanItem(cid,"allowed","authorized",safe))
    return {"schema_version":"acquisition-plan-v1","transport_allowed":bool(items) and all(x.state=="allowed" for x in items),
      "authorization_fingerprint":auth_fp,"items":[asdict(x) for x in items],"network_requests":0}

def _candidate_id(row): return str(row.get("candidate_id") or row.get("media_candidate_id") or row.get("document_candidate_id") or "")
