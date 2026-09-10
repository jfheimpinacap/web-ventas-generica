"""Closed, deterministic offline audit and canonical catalog packaging.

The module consumes an explicit allow-list.  It has deliberately no transport or
import behavior: an audited package is evidence for a later local dry-run, not an
authorization to mutate JEM Nexus.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath

from .paths import UnsafePathError, safe_join, windows_collision_key
from .serialization import canonical_bytes

SCHEMA_VERSION = "1.0.0"
RULE_VERSION = "catalog-audit-v1"
PRODUCER = "catalog-package"
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o100644 << 16
MANIFEST_PATH = "package-manifest.json"
HASH = frozenset({"fingerprint", "content_fingerprint", "plan_fingerprint", "manifest_fingerprint"})
SEVERITIES = frozenset({"error", "blocking_review", "warning", "info"})
RESOLUTIONS = frozenset({"open", "resolved_by_exact_approval", "not_applicable", "superseded_by_input_change"})


class PackageError(ValueError):
    """Stable fail-closed error returned by the offline CLI."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(value):
    if not isinstance(value, dict):
        return digest(canonical_bytes(value))
    return digest(canonical_bytes({k: v for k, v in value.items() if k not in HASH and not k.endswith("_at")}))


def _path(value):
    """Validate one portable path without touching the filesystem."""
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise PackageError("UNSAFE_PATH", "path must be non-empty portable text")
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if posix.is_absolute() or windows.drive or windows.root or windows.anchor:
        raise PackageError("UNSAFE_PATH", "absolute, drive and UNC paths are forbidden")
    parts = value.split("/")
    if any(x in {"", ".", ".."} or x.endswith((" ", ".")) for x in parts):
        raise PackageError("UNSAFE_PATH", "empty, traversal and ambiguous segments are forbidden")
    try:
        safe_join(Path.cwd(), value)
    except UnsafePathError as error:
        raise PackageError("UNSAFE_PATH", str(error)) from error
    return value


def _unique_paths(values):
    exact, folded = set(), set()
    for value in values:
        _path(value)
        key = "/".join(windows_collision_key(x) for x in value.split("/"))
        if value in exact:
            raise PackageError("DUPLICATE_PATH", value)
        if key in folded:
            raise PackageError("PATH_COLLISION", value)
        exact.add(value); folded.add(key)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8", errors="strict"))


def validate_references(manifest, root):
    """Validate every allowlisted artifact and its declared ancestry transitively."""
    required = {"artifact_type", "schema_version", "path", "sha256", "size", "producer", "producer_fingerprint", "policy_version", "scope", "identity"}
    references = manifest.get("artifact_references", [])
    if not references:
        raise PackageError("INPUT_INCOMPATIBLE", "the closed input manifest has no references")
    _unique_paths([x.get("path") for x in references])
    known = {x.get("producer_fingerprint") for x in references} | set(manifest.get("trusted_root_fingerprints", []))
    result = {}
    for reference in references:
        if set(reference) != required:
            raise PackageError("INPUT_INCOMPATIBLE", "artifact reference fields are not closed")
        if reference["schema_version"] != SCHEMA_VERSION:
            raise PackageError("SCHEMA_INCOMPATIBLE", reference["path"])
        path = safe_join(Path(root), reference["path"])
        if path.is_symlink() or any(x.is_symlink() for x in path.parents if x != Path(root).parent):
            raise PackageError("UNEXPECTED_SYMLINK", reference["path"])
        if not path.is_file():
            raise PackageError("ARTIFACT_MISSING", reference["path"])
        data = path.read_bytes()
        if len(data) != reference["size"]:
            raise PackageError("SIZE_MISMATCH", reference["path"])
        if digest(data) != reference["sha256"]:
            raise PackageError("HASH_MISMATCH", reference["path"])
        document = json.loads(data.decode("utf-8", errors="strict")) if reference["path"].endswith((".json", ".jsonl")) and not reference["path"].endswith(".jsonl") else None
        if isinstance(document, dict):
            ancestry = document.get("upstream_fingerprints", document.get("input_fingerprints", {}))
            for upstream in ancestry.values() if isinstance(ancestry, dict) else ancestry:
                if upstream not in known:
                    raise PackageError("UPSTREAM_FINGERPRINT_MISMATCH", reference["path"])
        result[reference["artifact_type"]] = {"reference": reference, "path": path, "document": document, "bytes": data}
    required_types = set(manifest.get("required_artifact_types", []))
    if required_types - set(result):
        raise PackageError("ORPHAN_REFERENCE", ",".join(sorted(required_types - set(result))))
    return result


def finding(rule, identity=None, *, severity="error", blocking=True, subject=None,
            code=None, parameters=None, evidence=(), upstream=(), approval=None,
            resolution="open", policy_fingerprint=""):
    if severity not in SEVERITIES or resolution not in RESOLUTIONS:
        raise PackageError("FINDING_INCOMPATIBLE", "unknown severity or resolution")
    body = {"audit_rule_id": rule, "audit_rule_version": "1", "scope": "product" if identity else "catalog",
            "product_identity": identity, "subject": subject, "severity": severity, "blocking": bool(blocking),
            "message_code": code or rule.upper().replace(".", "_"), "parameters": parameters or {},
            "evidence_references": sorted(set(evidence)), "upstream_fingerprints": sorted(set(upstream)),
            "approval_reference": approval, "resolution_state": resolution, "policy_fingerprint": policy_fingerprint}
    body["finding_id"] = "finding-" + fingerprint(body)[:24]
    body["schema_version"] = SCHEMA_VERSION
    return body


def _exact_approval(item, approval, policy_fp, input_fp, fixture_only):
    if not approval or approval.get("synthetic", False) and not fixture_only:
        return False
    expected = {"decision": item.get("expected_decision"), "scope": item.get("scope", "product"),
                "product_identity": item.get("product_identity"), "subject": item.get("subject"),
                "evidence_references": sorted(item.get("evidence_references", [])), "value": item.get("value"),
                "policy_fingerprint": policy_fp, "input_fingerprint": input_fp}
    return all(approval.get(key) == value for key, value in expected.items())


def _explicit_exclusion(identity, bundle, policy_fp, input_fp):
    """Return only a complete, versioned exclusion; uncertainty is never exclusion."""
    candidate = next((x for x in bundle.get("exclusion_decisions", []) if x.get("product_identity") == identity), None)
    if not candidate:
        return None
    required = {"decision_id", "product_identity", "decision", "rule_id", "rule_version",
                "reason_code", "evidence_references", "policy_fingerprint", "input_fingerprint"}
    if (set(candidate) != required or candidate["decision"] != "exclude"
            or not candidate["rule_id"] or not candidate["reason_code"]
            or not candidate["evidence_references"] or candidate["policy_fingerprint"] != policy_fp
            or candidate["input_fingerprint"] != input_fp):
        return None
    return candidate


def validate_inclusion_decision(decision):
    """Enforce cross-field invariants not expressible by the local schema subset."""
    value = decision.get("decision")
    blockers = decision.get("blocking_findings", [])
    exclusion = decision.get("exclusion_reason")
    if value == "include" and (blockers or decision.get("readiness") != "package_eligible"):
        raise PackageError("DECISION_INCOHERENT", "include cannot carry blockers or blocked readiness")
    if value == "blocked" and (not blockers or exclusion is not None):
        raise PackageError("DECISION_INCOHERENT", "blocked requires structured blocking findings")
    if value == "exclude" and (blockers or not isinstance(exclusion, dict) or not exclusion.get("reason_code")):
        raise PackageError("DECISION_INCOHERENT", "exclude requires an explicit reason and no blockers")
    if value not in {"include", "exclude", "blocked"}:
        raise PackageError("DECISION_INCOHERENT", "unknown inclusion decision")


def _audit_product(product, bundle, policy, input_fp):
    identity = product.get("canonical_identity")
    policy_fp = policy["fingerprint"]
    findings, applied = [], []
    def add(rule, **kw): findings.append(finding(rule, identity, policy_fingerprint=policy_fp, upstream=bundle.get("upstream_fingerprints", {}).values(), **kw))
    if not identity or not product.get("brand_code") or not product.get("canonical_model"):
        add("identity.required", subject="identity")
    if product.get("run_fingerprint") not in (None, input_fp):
        add("identity.run_mismatch", subject="identity")
    mapping = product.get("category_mapping", {})
    targets = {x["category_key"] for x in bundle.get("category_catalog", {}).get("categories", [])}
    if mapping.get("mapping_status") != "approved": add("category.approval_required", subject="category", severity="blocking_review")
    if mapping.get("target_category_key") not in targets: add("category.target_missing", subject="category")
    if len(mapping.get("primary_categories", [mapping.get("target_category_key")] if mapping.get("target_category_key") else [])) != 1:
        add("category.primary_count", subject="category")
    if isinstance(mapping.get("target_category_key"), int): add("category.production_id", subject="category")
    specs = product.get("product_specs", [])
    spec_keys = set()
    for spec in specs:
        key = spec.get("canonical_key")
        if not key or key in spec_keys or spec.get("canonical_identity", identity) != identity or spec.get("resolution_status") == "conflict":
            add("product_spec.invalid", subject=key or "product_spec", evidence=spec.get("evidence_references", []))
        spec_keys.add(key)
        if len(str(spec.get("display_value", ""))) > policy.get("max_spec_length", 2000): add("product_spec.length", subject=key)
    contract = bundle.get("field_contract", {})
    for key, field in product.get("structured_fields", {}).items():
        rule = contract.get("fields", {}).get(key)
        value = field.get("value") if isinstance(field, dict) else field
        if rule is None: add("field.unknown", subject=key)
        elif "enum" in rule and value not in rule["enum"]: add("field.enum", subject=key, parameters={"value": value})
        elif isinstance(value, str) and len(value) > rule.get("max_length", len(value)): add("field.length", subject=key)
    if product.get("document_kind") != "normalized_for_audit_not_api_payload": add("producto.document_kind", subject="producto.json")
    commercial = product.get("commercial", {})
    safe = {"is_published": False, "price_visible": False, "is_featured": False, "price": None}
    if any(commercial.get(k) != v for k, v in safe.items()): add("commercial.unsafe_default", subject="commercial")
    for key in policy.get("required_commercial_fields", []):
        if commercial.get(key) is None: add("commercial.required", subject=key, severity="blocking_review")
    for review in bundle.get("reviews", []):
        if review.get("canonical_identity") == identity and review.get("blocking") and review.get("status") not in {"resolved", "not_applicable"}:
            add("review.open", subject=review.get("subject", "review"), severity="blocking_review", evidence=review.get("evidence_references", []))
    for conflict in bundle.get("conflicts", []):
        if conflict.get("canonical_identity") == identity and conflict.get("status") != "resolved": add("conflict.open", subject=conflict.get("source_field_key", "conflict"))
    for gap in bundle.get("schema_gaps", []):
        if identity in gap.get("affected_products", [identity]) and policy.get("schema_gap_rules", {}).get(gap.get("concept"), "blocking") == "blocking": add("schema_gap.blocking", subject=gap.get("concept"))
    media = product.get("media", [])
    primary = [x for x in media if isinstance(x, dict) and x.get("role") == "primary"]
    secondary = [x for x in media if isinstance(x, dict) and x.get("role") == "secondary"]
    if len(primary) > 1: add("asset.primary_count", subject="primary_image")
    if len(secondary) > policy.get("max_secondary_images", 4): add("asset.secondary_count", subject="secondary_images")
    if {x.get("sha256") for x in primary} & {x.get("sha256") for x in secondary}: add("asset.role_overlap", subject="media")
    if not primary and policy.get("missing_primary", "blocking") != "allowed":
        mode = policy.get("missing_primary", "blocking"); add("asset.primary_missing", subject="primary_image", severity="warning" if mode == "warning" else "error", blocking=mode == "blocking")
    assets = media + ([product["technical_sheet"]] if isinstance(product.get("technical_sheet"), dict) else []) + product.get("additional_documents", [])
    for asset in assets:
        if asset.get("canonical_identity") != identity or not asset.get("binary_validated") or not asset.get("selected") or not asset.get("materialized_path") or not asset.get("receipt_reference"):
            add("asset.integrity", subject=asset.get("role", "asset"), evidence=asset.get("evidence_references", []))
        if asset.get("source_adapter") == "gam" and not asset.get("gam_approval_reference"):
            add("asset.gam_approval", subject=asset.get("role", "asset"), severity="blocking_review")
    for candidate in list(findings):
        if not candidate["blocking"]: continue
        item = {"expected_decision": "resolve", "scope": candidate["scope"], "product_identity": identity,
                "subject": candidate["subject"], "evidence_references": candidate["evidence_references"], "value": candidate["parameters"].get("value")}
        approval = next((x for x in bundle.get("approvals", []) if _exact_approval(item, x, policy_fp, input_fp, bundle["fixture_only"])), None)
        if approval:
            candidate["resolution_state"] = "resolved_by_exact_approval"; candidate["blocking"] = False
            candidate["approval_reference"] = approval["approval_id"]; applied.append(approval["approval_id"])
    blocking = sorted(x["finding_id"] for x in findings if x["blocking"] and x["resolution_state"] == "open")
    if not identity: readiness = "audit_blocked"
    elif any("category" in x["audit_rule_id"] for x in findings if x["finding_id"] in blocking): readiness = "category_mapping_required"
    elif any("commercial" in x["audit_rule_id"] for x in findings if x["finding_id"] in blocking): readiness = "commercial_policy_required"
    elif any("schema_gap" in x["audit_rule_id"] for x in findings if x["finding_id"] in blocking): readiness = "schema_decision_required"
    elif any("asset" in x["audit_rule_id"] for x in findings if x["finding_id"] in blocking): readiness = "asset_review_required"
    elif blocking: readiness = "manual_review_required"
    else: readiness = "package_eligible"
    exclusion = _explicit_exclusion(identity, bundle, policy_fp, input_fp) if not blocking else None
    if blocking: decision_value = "blocked"
    elif exclusion: decision_value = "exclude"; readiness = "package_excluded"
    else: decision_value = "include"
    decision = {"schema_version": SCHEMA_VERSION, "product_identity": identity, "decision": decision_value,
                "rule_version": RULE_VERSION, "readiness": readiness, "blocking_findings": blocking, "applied_approvals": sorted(applied),
                "exclusion_reason": ({"decision_id": exclusion["decision_id"], "rule_id": exclusion["rule_id"], "rule_version": exclusion["rule_version"],
                                      "reason_code": exclusion["reason_code"], "evidence_references": exclusion["evidence_references"]} if exclusion else None),
                "normalized_product_fingerprint": fingerprint(product), "asset_set_fingerprint": fingerprint({"assets": assets}),
                "category_mapping_fingerprint": fingerprint(mapping), "policy_fingerprint": policy_fp}
    decision["decision_fingerprint"] = fingerprint(decision)
    validate_inclusion_decision(decision)
    master = {"schema_version": SCHEMA_VERSION, "product_identity": identity, "brand": product.get("brand_code"), "model": product.get("canonical_model"),
              "variant": product.get("variant"), "source_categories": product.get("source_categories", []), "jem_category": mapping,
              "structured_field_summary": product.get("structured_fields", {}), "product_spec_summary": specs,
              "primary_image": primary[0] if len(primary) == 1 else None, "secondary_images": secondary,
              "technical_sheet": product.get("technical_sheet"), "additional_documents": product.get("additional_documents", []),
              "schema_gaps": product.get("schema_gaps", []), "open_findings": blocking, "approval_references": sorted(applied),
              "readiness": readiness, "inclusion_decision": decision_value, "decision_fingerprint": decision["decision_fingerprint"], "producto_path": product.get("producto_path"),
              "fingerprints": {"normalized_product": decision["normalized_product_fingerprint"], "assets": decision["asset_set_fingerprint"], "category_mapping": decision["category_mapping_fingerprint"]}}
    return findings, decision, master


def audit(bundle):
    """Audit normalized facts without changing or approving them."""
    if bundle.get("schema_version") != SCHEMA_VERSION or "fixture_only" not in bundle:
        raise PackageError("INPUT_INCOMPATIBLE", "unsupported audit input")
    policy = bundle.get("audit_policy", {})
    if policy.get("fingerprint") != fingerprint(policy): raise PackageError("POLICY_FINGERPRINT_MISMATCH", "audit policy changed")
    package_policy = bundle.get("package_policy", {})
    if package_policy.get("fingerprint") != fingerprint(package_policy): raise PackageError("POLICY_FINGERPRINT_MISMATCH", "package policy changed")
    if not bundle["fixture_only"] and not bundle.get("structure_verified"):
        raise PackageError("LIVE_STRUCTURE_BLOCKED", "live structure is not legitimately verified")
    identities = [x.get("canonical_identity") for x in bundle.get("products", [])]
    comparable = [x.casefold() for x in identities if isinstance(x, str)]
    if len(comparable) != len(set(comparable)): raise PackageError("IDENTITY_DUPLICATE", "duplicate or case-colliding identity")
    input_fp = fingerprint({k:v for k,v in bundle.items() if k not in {"approvals", "exclusion_decisions"}})
    all_findings=[]; decisions=[]; masters=[]
    for product in sorted(bundle.get("products", []), key=lambda x: (str(x.get("canonical_identity", "")).casefold(), str(x.get("canonical_identity", "")))):
        findings, decision, master = _audit_product(product, bundle, policy, input_fp)
        all_findings += findings; decisions.append(decision); masters.append(master)
    eligible = [x["product_identity"] for x in decisions if x["decision"] == "include"]
    excluded = [{"product_identity": x["product_identity"], "reason": x["exclusion_reason"]} for x in decisions if x["decision"] == "exclude"]
    blocked = [{"product_identity": x["product_identity"], "reasons": x["blocking_findings"], "evidence_references": sorted({e for f in all_findings if f["finding_id"] in x["blocking_findings"] for e in f["evidence_references"]})} for x in decisions if x["decision"] == "blocked"]
    discovered = sorted(bundle.get("discovered_universe", identities), key=lambda x: str(x).casefold())
    counts = {"discovered": len(discovered), "audited": len(decisions), "eligible": len(eligible), "excluded": len(excluded), "blocked": len(blocked)}
    if counts["audited"] != counts["eligible"] + counts["excluded"] + counts["blocked"]: raise PackageError("UNIVERSE_PARTITION", "audited universe was not partitioned")
    readiness = "audit_complete_with_blockers" if blocked else ("ready_for_package_build" if eligible else "ready_for_package_plan")
    result = {"schema_version": SCHEMA_VERSION, "producer": PRODUCER, "rules_version": RULE_VERSION, "fixture_only": bundle["fixture_only"],
              "structure_verified": bundle.get("structure_verified", False), "input_fingerprint": input_fp, "policy_fingerprint": policy["fingerprint"],
              "package_policy": package_policy, "upstream_fingerprints": bundle.get("upstream_fingerprints", {}),
              "discovered_universe": discovered, "audited_universe": identities, "package_eligible_universe": sorted(eligible),
              "package_excluded_universe": excluded, "package_blocked_universe": blocked, "counts": counts, "findings": sorted(all_findings, key=lambda x:x["finding_id"]),
              "product_audits": masters, "inclusion_decisions": decisions, "open_reviews": bundle.get("reviews", []),
              "applied_approvals": sorted({a for x in decisions for a in x["applied_approvals"]}), "schema_gap_summary": bundle.get("schema_gaps", []),
              "asset_integrity_summary": {"referenced": sum(len(x.get("media", [])) + len(x.get("additional_documents", [])) + bool(x.get("technical_sheet")) for x in bundle.get("products", []))},
              "catalog_readiness": readiness, "offline": True, "network_requests": 0, "api_calls": 0, "imports": 0, "publications": 0}
    result["audit_fingerprint"] = fingerprint(result)
    return result


def audit_files(result):
    collections = {"audit-findings.jsonl": result["findings"], "product-audits.jsonl": result["product_audits"], "inclusion-decisions.jsonl": result["inclusion_decisions"],
                   "catalog-master.jsonl": result["product_audits"], "package-eligible-products.jsonl": [{"product_identity":x} for x in result["package_eligible_universe"]],
                   "package-excluded-products.jsonl": result["package_excluded_universe"], "package-blocked-products.jsonl": result["package_blocked_universe"]}
    files = {name: b"".join(canonical_bytes(x) for x in values) for name, values in collections.items()}
    report = ["catalog audit (informative only)", *(f"{k}: {v}" for k,v in sorted(result["counts"].items())),
              *(f"excluded: {x['product_identity']} reason={x['reason']['reason_code']}" for x in result["package_excluded_universe"]),
              *(f"blocked: {x['product_identity']} findings={','.join(x['reasons'])}" for x in result["package_blocked_universe"]),
              f"readiness: {result['catalog_readiness']}", "import/publication authorization: none"]
    files["audit-report.txt"] = ("\n".join(report)+"\n").encode("utf-8")
    manifest = {k:v for k,v in result.items() if k not in {"findings","product_audits","inclusion_decisions","open_reviews","applied_approvals","schema_gap_summary","asset_integrity_summary"}}
    manifest["files"] = [{"path":p,"sha256":digest(d),"size":len(d)} for p,d in sorted(files.items())]
    manifest["manifest_fingerprint"] = fingerprint(manifest)
    files["audit-manifest.json"] = canonical_bytes(manifest)
    return files


def write_audit(result, destination):
    destination=Path(destination); files=audit_files(result)
    if destination.exists(): raise PackageError("DESTINATION_CONFLICT", "audit destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=f".{destination.name}.auditing-", dir=destination.parent))
    try:
        for relative,data in files.items():
            target=safe_join(staging,relative); target.write_bytes(data)
        os.replace(staging,destination)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return files


def package_plan(audit_result, source_root, schema_paths=()):
    """Create an explicit plan; no directory traversal or glob participates."""
    policy=audit_result["package_policy"]; entries=[]
    def add(path, role, source, identity=None, mime=None, evidence=()):
        _path(path); source_path=safe_join(Path(source_root), source); data=source_path.read_bytes()
        entries.append({"path":path,"role":role,"source_reference":source,"source_sha256":digest(data),"source_size":len(data),
                        "destination_sha256":digest(data),"destination_size":len(data),"product_identity":identity,"mime":mime,
                        "policy_rule":RULE_VERSION,"evidence_references":sorted(evidence)})
    add("catalog/catalog-master.jsonl","catalog_master","catalog-master.jsonl")
    add("catalog/importable-products.jsonl","importable_products","package-eligible-products.jsonl")
    category_source=policy.get("category_mapping_source")
    if category_source: add("mappings/category-mapping.json","category_mapping",category_source)
    provenance_source=policy.get("provenance_source")
    if provenance_source: add("provenance/provenance-index.jsonl","provenance",provenance_source)
    masters={x["product_identity"]:x for x in audit_result["product_audits"]}
    for identity in audit_result["package_eligible_universe"]:
        master=masters[identity]; product_source=master.get("producto_path")
        if not product_source: raise PackageError("ORPHAN_REFERENCE", f"producto.json:{identity}")
        category=master["jem_category"]["target_category_key"]
        model=master["model"]
        add(f"catalogo/{category}/{model}/producto.json","producto",product_source,identity,"application/json")
        for asset in [x for x in [master.get("primary_image"),*master.get("secondary_images",[]),master.get("technical_sheet"),*master.get("additional_documents",[])] if x]:
            leaf={"primary":"imagenes","secondary":"imagenes","technical_sheet":"fichas-tecnicas"}.get(asset.get("role"),"documentos")
            filename=PurePosixPath(asset["materialized_path"]).name
            add(f"catalogo/{category}/{model}/{leaf}/{filename}",asset.get("role","document"),asset["materialized_path"],identity,asset.get("mime"),asset.get("evidence_references",[]))
    for schema in schema_paths: add(f"schemas/{PurePosixPath(schema).name}","schema",schema)
    entries.sort(key=lambda x:x["path"]); _unique_paths([x["path"] for x in entries])
    descriptors=[{"path":x["path"],"role":x["role"],"sha256":x["destination_sha256"],"size":x["destination_size"],"mime":x["mime"],"product_identity":x["product_identity"]} for x in entries]
    decision_fp=fingerprint({"decisions":[x["decision_fingerprint"] for x in audit_result["inclusion_decisions"]]})
    content_fp=fingerprint({"entries":descriptors,"policy_fingerprint":policy["fingerprint"],"audit_fingerprint":audit_result["audit_fingerprint"],"decision_fingerprint":decision_fp})
    blocked_count=len(audit_result["package_blocked_universe"])
    blocked=not audit_result["package_eligible_universe"] or blocked_count > 0 or audit_result["catalog_readiness"] != "ready_for_package_build"
    plan={"schema_version":SCHEMA_VERSION,"package_schema_version":SCHEMA_VERSION,"producer":PRODUCER,"package_policy":policy,
          "audit_manifest_fingerprint":audit_result["audit_fingerprint"],"included_products":audit_result["package_eligible_universe"],
          "excluded_product_count":len(audit_result["package_excluded_universe"]),"blocked_product_count":blocked_count,
          "decision_fingerprint":decision_fp,"entries":entries,"content_fingerprint":content_fp,
          "entry_count":len(entries)+1,"total_uncompressed_size":sum(x["destination_size"] for x in entries),"blocking":blocked,
          "fixture_only":audit_result["fixture_only"],"source_root":".","upstream_fingerprints":audit_result["upstream_fingerprints"]}
    plan["plan_fingerprint"]=fingerprint(plan)
    return plan


def _package_manifest(plan):
    payload=[{"path":x["path"],"role":x["role"],"sha256":x["destination_sha256"],"size":x["destination_size"],"mime":x["mime"],
              "product_identity":x["product_identity"],"source_relation":x["source_reference"]} for x in plan["entries"]]
    counts=Counter(x["role"] for x in plan["entries"])
    value={"package_kind":"canonical_catalog_audit_package","schema_version":SCHEMA_VERSION,"producer":PRODUCER,
           "policy_version":plan["package_policy"].get("policy_version"),"policy_fingerprint":plan["package_policy"]["fingerprint"],
           "audit_manifest_fingerprint":plan["audit_manifest_fingerprint"],"normalization_fingerprint":plan["upstream_fingerprints"].get("normalization"),
           "upstream_fingerprints":plan["upstream_fingerprints"],"brand_scope":plan["package_policy"].get("brand_scope",[]),
           "source_adapters":plan["package_policy"].get("source_adapters",[]),"product_count":len(plan["included_products"]),
           "entry_counts_by_role":dict(sorted(counts.items())),"total_entry_count":len(payload)+1,"total_payload_bytes":sum(x["size"] for x in payload),
           "entries":payload,"content_fingerprint":plan["content_fingerprint"],"decision_fingerprint":plan["decision_fingerprint"],"fixture_only":plan["fixture_only"],
           "guarantees":{"offline":True,"api_calls":0,"imports":0,"publications":0,"import_authorized":False},
           "excluded_product_count":plan["excluded_product_count"],"blocked_product_count":0,"readiness":"package_built"}
    value["manifest_fingerprint"]=fingerprint(value)
    return value


def _zip_info(path):
    info=zipfile.ZipInfo(path, ZIP_DATE); info.compress_type=zipfile.ZIP_STORED; info.create_system=3; info.external_attr=ZIP_MODE; info.flag_bits=0; info.extra=b""; info.comment=b""
    return info


def _write_zip(target, plan, root):
    manifest=canonical_bytes(_package_manifest(plan))
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        archive.comment=b""; archive.writestr(_zip_info(MANIFEST_PATH),manifest)
        for entry in plan["entries"]:
            data=safe_join(Path(root),entry["source_reference"]).read_bytes()
            if digest(data)!=entry["source_sha256"] or len(data)!=entry["source_size"]: raise PackageError("SOURCE_CHANGED",entry["source_reference"])
            archive.writestr(_zip_info(entry["path"]),data)


def verify_package(package, receipt=None, policy=None):
    """Stream-inspect a ZIP.  Nothing is extracted, repaired or overwritten."""
    package=Path(package); errors=[]; policy=policy or {}
    max_entries=policy.get("max_entries",10000); max_entry=policy.get("max_entry_size",100_000_000); max_total=policy.get("max_total_size",1_000_000_000); max_ratio=policy.get("max_compression_ratio",20)
    if not package.is_file(): return {"schema_version":SCHEMA_VERSION,"valid":False,"errors":["PACKAGE_MISSING"],"readiness":"input_blocked"}
    package_hash=digest(package.read_bytes())
    try:
        with zipfile.ZipFile(package,"r") as archive:
            infos=archive.infolist(); names=[x.filename for x in infos]
            try:_unique_paths(names)
            except PackageError as error: errors.append(error.code)
            if len(infos)>max_entries: errors.append("ENTRY_COUNT_LIMIT")
            if archive.comment: errors.append("ZIP_COMMENT")
            total=0; data_by_name={}
            for info in infos:
                if info.flag_bits & 1: errors.append("ENCRYPTED:"+info.filename)
                if info.compress_type != zipfile.ZIP_STORED: errors.append("COMPRESSION_METHOD:"+info.filename)
                if info.date_time != ZIP_DATE or info.create_system != 3 or info.external_attr != ZIP_MODE or info.extra or info.comment: errors.append("ZIP_METADATA:"+info.filename)
                if stat.S_IFMT(info.external_attr >> 16) != stat.S_IFREG: errors.append("SPECIAL_FILE:"+info.filename)
                if info.file_size>max_entry: errors.append("ENTRY_SIZE_LIMIT:"+info.filename)
                if info.compress_size and info.file_size/info.compress_size>max_ratio: errors.append("COMPRESSION_RATIO:"+info.filename)
                if policy.get("forbid_nested_zip",True) and info.filename.casefold().endswith((".zip",".jar")): errors.append("NESTED_ZIP:"+info.filename)
                total+=info.file_size
                hasher=hashlib.sha256(); chunks=[]
                with archive.open(info,"r") as stream:
                    while True:
                        chunk=stream.read(65536)
                        if not chunk: break
                        hasher.update(chunk); chunks.append(chunk)
                data_by_name[info.filename]=(hasher.hexdigest(),info.file_size,b"".join(chunks))
            if total>max_total: errors.append("TOTAL_SIZE_LIMIT")
            if not infos or infos[0].filename!=MANIFEST_PATH: errors.append("MANIFEST_ORDER")
            try: manifest=json.loads(data_by_name[MANIFEST_PATH][2].decode("utf-8",errors="strict"))
            except (KeyError,UnicodeDecodeError,json.JSONDecodeError): manifest=None; errors.append("MANIFEST_INVALID")
            if manifest:
                if manifest.get("manifest_fingerprint")!=fingerprint(manifest): errors.append("MANIFEST_FINGERPRINT")
                expected=[MANIFEST_PATH]+[x["path"] for x in manifest.get("entries",[])]
                if names!=expected: errors.append("ENTRY_LIST")
                for entry in manifest.get("entries",[]):
                    actual=data_by_name.get(entry["path"])
                    if not actual: errors.append("MISSING:"+entry["path"])
                    elif actual[:2]!=(entry["sha256"],entry["size"]): errors.append("ALTERED:"+entry["path"])
                descriptors=[{"path":x["path"],"role":x["role"],"sha256":x["sha256"],"size":x["size"],"mime":x.get("mime"),"product_identity":x.get("product_identity")} for x in manifest.get("entries",[])]
                if manifest.get("blocked_product_count") != 0: errors.append("BLOCKED_COUNT_INCOHERENT")
                calculated=fingerprint({"entries":descriptors,"policy_fingerprint":manifest.get("policy_fingerprint"),"audit_fingerprint":manifest.get("audit_manifest_fingerprint"),"decision_fingerprint":manifest.get("decision_fingerprint")})
                if calculated!=manifest.get("content_fingerprint"): errors.append("CONTENT_FINGERPRINT")
    except (OSError,zipfile.BadZipFile,RuntimeError) as error: errors.append("UNSAFE_OR_INVALID_ZIP:"+type(error).__name__)
    if receipt:
        value=read_json(receipt) if not isinstance(receipt,dict) else receipt
        if value.get("zip_sha256")!=package_hash or value.get("zip_size")!=package.stat().st_size: errors.append("RECEIPT_MISMATCH")
    return {"schema_version":SCHEMA_VERSION,"valid":not errors,"errors":sorted(errors),"zip_sha256":package_hash,"zip_size":package.stat().st_size,"readiness":"package_verified" if not errors else "input_blocked"}


def build_package(plan, expected_fingerprint, destination, source_root, receipt_path):
    if plan.get("plan_fingerprint")!=fingerprint(plan) or expected_fingerprint!=plan.get("plan_fingerprint"): raise PackageError("PLAN_FINGERPRINT_MISMATCH","plan or expected fingerprint changed")
    if plan.get("blocking") or plan.get("blocked_product_count", 0) != 0 or not plan.get("included_products"): raise PackageError("PLAN_BLOCKED","blocked or empty plan cannot be built")
    destination=Path(destination); receipt_path=Path(receipt_path); destination.parent.mkdir(parents=True,exist_ok=True); receipt_path.parent.mkdir(parents=True,exist_ok=True)
    staging_handle, staging_name=tempfile.mkstemp(prefix=f".{destination.name}.building-",suffix=".tmp",dir=destination.parent); os.close(staging_handle); staging=Path(staging_name)
    try:
        _write_zip(staging,plan,source_root); verification=verify_package(staging,policy=plan["package_policy"])
        if not verification["valid"]: raise PackageError("STAGING_VERIFY_FAILED",",".join(verification["errors"]))
        manifest=_package_manifest(plan)
        receipt={"schema_version":SCHEMA_VERSION,"package_path":destination.name,"zip_sha256":verification["zip_sha256"],"zip_size":verification["zip_size"],
                 "content_fingerprint":plan["content_fingerprint"],"manifest_fingerprint":manifest["manifest_fingerprint"],"plan_fingerprint":plan["plan_fingerprint"],
                 "audit_fingerprint":plan["audit_manifest_fingerprint"],"entry_count":plan["entry_count"],"product_count":len(plan["included_products"]),
                 "build_status":"completed","import_authorized":False}
        receipt["receipt_fingerprint"]=fingerprint(receipt)
        already_complete=False
        if destination.exists():
            existing=verify_package(destination,policy=plan["package_policy"])
            if existing["valid"] and existing["zip_sha256"]==verification["zip_sha256"]: receipt["build_status"]="already_complete"; already_complete=True
            else: raise PackageError("DESTINATION_CONFLICT","existing package differs or is invalid")
        else: os.replace(staging,destination)
        receipt_bytes=canonical_bytes(receipt)
        if receipt_path.exists() and not already_complete and receipt_path.read_bytes()!=receipt_bytes: raise PackageError("DESTINATION_CONFLICT","existing receipt differs")
        if receipt_path.exists() and already_complete:
            prior=read_json(receipt_path)
            if prior.get("zip_sha256")!=receipt["zip_sha256"] or prior.get("plan_fingerprint")!=receipt["plan_fingerprint"]: raise PackageError("DESTINATION_CONFLICT","existing receipt differs")
        if not receipt_path.exists():
            fd,name=tempfile.mkstemp(prefix=f".{receipt_path.name}.writing-",suffix=".tmp",dir=receipt_path.parent); os.close(fd); temporary=Path(name)
            try: temporary.write_bytes(receipt_bytes); os.replace(temporary,receipt_path)
            finally:
                if temporary.exists(): temporary.unlink()
        return receipt
    finally:
        if staging.exists(): staging.unlink()
