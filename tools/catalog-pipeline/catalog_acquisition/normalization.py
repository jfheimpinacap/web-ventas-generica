"""Deterministic, fail-closed normalization of already extracted catalog facts.

This module deliberately has no transport dependency.  Values are represented as
strings backed by :class:`Decimal`; raw observations and every evidence reference
remain attached to the normalized conclusion.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from .errors import UnsafePathError
from .paths import safe_join
from .serialization import canonical_bytes

SCHEMA_VERSION = "1.0.0"
POLICY_VERSION = "normalization-ep-v1"
ABSENT = {"", "-", "—", "n/a", "no aplica", "opcional", "según configuración", "a consultar"}
NON_SCALAR_MARKERS = ("/", "hasta ", "≤", "≥")
STRUCTURED_FIELDS = {
    "working_height": "WorkingHeightM",
    "rated_load_capacity": "MaximumLoadCapacityKg",
    "maximum_load_capacity": "MaximumLoadCapacityKg",
    "operating_weight": "MachineWeightKg",
    "service_weight": "MachineWeightKg",
    "machine_weight": "MachineWeightKg",
    "power_source": "PowerSource",
    "terrain_type": "TerrainType",
    "year": "Year",
    "hours_meter": "HoursMeter",
}
PROHIBITED_ROUTES = {
    "lift_height", "lifting_height", "fork_height", "mast_height",
    "battery_capacity", "towing_capacity", "axle_load", "battery_weight",
    "attachment_weight", "mast_weight", "battery_voltage", "battery_chemistry",
}
GAP_FIELDS = {
    "lift_height": ("MaximumLiftHeightMm", "length", "mm"),
    "lifting_height": ("MaximumLiftHeightMm", "length", "mm"),
    "fork_height": ("MaximumLiftHeightMm", "length", "mm"),
    "battery_voltage": ("BatteryVoltageV", "electric_potential", "V"),
    "battery_capacity": ("BatteryCapacityAh", "electric_charge", "Ah"),
    "battery_chemistry": ("BatteryChemistry", "classification", None),
}
POWER = {"diesel": "diesel", "electric 24v": "electric_24v", "lithium electric": "electric_lithium"}
TERRAIN = {"indoor smooth": "indoor_smooth", "outdoor": "outdoor", "outdoor slopes and ramps": "outdoor_slopes_and_ramps"}


class NormalizationError(ValueError):
    """A stable, user-correctable contract or verification failure."""
    def __init__(self, code, message):
        super().__init__(message); self.code = code


def fingerprint(value):
    semantic = {k: v for k, v in value.items() if k not in {"created_at", "updated_at", "observed_at", "fingerprint"}}
    return hashlib.sha256(canonical_bytes(semantic)).hexdigest()


def _decimal_string(value, scale=None, rounding="ROUND_HALF_EVEN"):
    with localcontext() as context:
        context.prec = 40
        if scale is not None:
            value = value.quantize(Decimal(1).scaleb(-scale), rounding=rounding)
    rendered = format(value, "f")
    return rendered if scale is not None else (rendered.rstrip("0").rstrip(".") or "0")


def parse_measure(raw_value, raw_unit, rule):
    """Parse one declared-locale scalar, never guessing separators or units."""
    literal = str(raw_value).strip(); lowered = literal.casefold()
    if lowered in ABSENT:
        return {"normalized_value": None, "normalized_unit": None, "resolution_status": "not_applicable" if lowered == "no aplica" else "missing", "reason": "absence_literal"}
    if any(marker in lowered for marker in NON_SCALAR_MARKERS) or "-" in literal[1:]:
        return {"normalized_value": None, "normalized_unit": raw_unit, "resolution_status": "manual_approval_required", "reason": "non_scalar"}
    decimal_separator = rule.get("decimal_separator")
    thousands_separator = rule.get("thousands_separator")
    if ("," in literal or "." in literal) and not decimal_separator:
        return {"normalized_value": None, "normalized_unit": raw_unit, "resolution_status": "manual_approval_required", "reason": "locale_ambiguous"}
    number = literal.replace(" ", "" if thousands_separator == " " else " ")
    if thousands_separator:
        number = number.replace(thousands_separator, "")
    if decimal_separator and decimal_separator != ".": number = number.replace(decimal_separator, ".")
    try: value = Decimal(number)
    except InvalidOperation:
        return {"normalized_value": None, "normalized_unit": raw_unit, "resolution_status": "unsupported", "reason": "not_numeric"}
    source_unit = raw_unit
    target_unit = rule.get("target_unit")
    if not source_unit:
        return {"normalized_value": None, "normalized_unit": None, "resolution_status": "manual_approval_required", "reason": "unit_missing"}
    conversion = rule.get("conversions", {}).get(f"{source_unit}->{target_unit}")
    if source_unit != target_unit and conversion is None:
        return {"normalized_value": None, "normalized_unit": source_unit, "resolution_status": "unsupported", "reason": "unit_unknown"}
    if conversion is not None: value *= Decimal(str(conversion))
    return {"normalized_value": _decimal_string(value, rule.get("scale"), rule.get("rounding", "ROUND_HALF_EVEN")),
            "normalized_unit": target_unit, "resolution_status": "normalized" if conversion is not None or literal != _decimal_string(value) else "exact", "reason": None}


def _review(identity, kind, subject, evidence, blocking=True):
    seed = {"identity": identity, "kind": kind, "subject": subject, "evidence": sorted(evidence)}
    return {"schema_version": SCHEMA_VERSION, "review_id": "norm-review-" + fingerprint(seed)[:20], "review_type": kind,
            "canonical_identity": identity, "subject": subject, "status": "manual_review_required", "blocking": blocking,
            "evidence_references": sorted(evidence), "fixture_only": False, "policy_version": POLICY_VERSION}


def normalize_observation(observation, policy):
    key = observation["source_field_key"]
    rule = policy.get("field_rules", {}).get(key)
    evidence = sorted(set(observation.get("evidence_references", [])))
    base = {"schema_version": SCHEMA_VERSION, "canonical_identity": observation["canonical_identity"],
            "model": observation.get("model"), "variant": observation.get("variant"), "source_field_key": key,
            "source_label": observation.get("source_label"), "raw_value": observation.get("raw_value"),
            "raw_unit": observation.get("raw_unit"), "source": observation["source"], "source_url": observation.get("source_url"),
            "source_document": observation.get("source_document"), "source_page": observation.get("source_page"),
            "source_section": observation.get("source_section"), "extraction_rule": observation.get("extraction_rule"),
            "evidence_references": evidence, "relation_references": sorted(set(observation.get("relation_references", []))),
            "locale": observation.get("locale"), "qualifiers": observation.get("qualifiers", []), "policy_fingerprint": policy["fingerprint"],
            "rule_id": rule["rule_id"] if rule else "route.product-spec.v1", "rule_version": rule.get("rule_version", "1") if rule else "1",
            "target_field": None, "conflict_group": None, "review_references": []}
    if not rule:
        parsed = {"normalized_value": None, "normalized_unit": observation.get("raw_unit"), "resolution_status": "unsupported", "reason": "no_approved_rule"}
    elif rule["kind"] == "enum":
        aliases = POWER if rule["target_field"] == "PowerSource" else TERRAIN
        value = aliases.get(str(observation.get("raw_value", "")).strip().casefold())
        parsed = {"normalized_value": value, "normalized_unit": None, "resolution_status": "normalized" if value else "unsupported", "reason": None if value else "enum_unknown"}
    elif rule["kind"] == "text":
        parsed = {"normalized_value": " ".join(str(observation.get("raw_value", "")).split()), "normalized_unit": None, "resolution_status": "normalized", "reason": None}
    else: parsed = parse_measure(observation.get("raw_value", ""), observation.get("raw_unit"), rule)
    target = rule.get("target_field") if rule else None
    if key in PROHIBITED_ROUTES or target not in STRUCTURED_FIELDS.values(): target = None
    base.update(parsed); base["target_field"] = target
    base["transformation_rule"] = base.pop("reason")
    base["observation_id"] = "normalized-" + fingerprint(base)[:24]
    return base


def _deduplicate_and_conflict(values):
    grouped = {}
    for item in values:
        key = (item["canonical_identity"], item["source_field_key"], item["normalized_value"], item["normalized_unit"])
        if key not in grouped: grouped[key] = dict(item)
        else:
            grouped[key]["evidence_references"] = sorted(set(grouped[key]["evidence_references"] + item["evidence_references"]))
            grouped[key].setdefault("matching_sources", []).append(item["source"])
    result = list(grouped.values())
    competitors = {}
    for item in result:
        if item["normalized_value"] is not None: competitors.setdefault((item["canonical_identity"], item["source_field_key"]), []).append(item)
    reviews = []; conflicts = []
    for (identity, field), items in competitors.items():
        distinct = {(x["normalized_value"], x["normalized_unit"]) for x in items}
        if len(distinct) > 1:
            conflict_id = "conflict-" + fingerprint({"identity": identity, "field": field, "values": sorted(distinct)})[:20]
            evidence = sorted({e for x in items for e in x["evidence_references"]})
            review = _review(identity, "technical_conflict", field, evidence)
            for item in items: item["resolution_status"] = "conflict"; item["conflict_group"] = conflict_id; item["review_references"] = [review["review_id"]]
            conflicts.append({"schema_version": SCHEMA_VERSION, "conflict_id": conflict_id, "canonical_identity": identity,
                              "source_field_key": field, "candidate_observation_ids": sorted(x["observation_id"] for x in items),
                              "status": "unresolved", "review_reference": review["review_id"]})
            reviews.append(review)
    return sorted(result, key=lambda x: x["observation_id"]), sorted(reviews, key=lambda x: x["review_id"]), sorted(conflicts, key=lambda x: x["conflict_id"])


def map_categories(product, matrix, category_catalog):
    available = {x["category_key"] for x in category_catalog["categories"]}
    entries = [x for x in matrix["mappings"] if x["source_category_key"] in product["source_category_keys"]]
    approved = [x for x in entries if x["mapping_status"] == "approved" and x.get("target_category_key") in available]
    primary = [x for x in approved if x["primary"]]
    reviews = []
    if any(x.get("target_category_key") not in available for x in entries if x.get("target_category_key")):
        status = "target_missing"; reviews.append(_review(product["canonical_identity"], "category_target_missing", "category", []))
    elif len(primary) != 1:
        status = "manual_review_required" if entries else "target_missing"; reviews.append(_review(product["canonical_identity"], "category_mapping", "category", []))
    else: status = "approved"
    return {"source_categories": product["source_category_keys"], "target_category_key": primary[0]["target_category_key"] if len(primary) == 1 else None,
            "mapping_status": status, "mapping_references": sorted(x["mapping_id"] for x in entries)}, reviews


def _spec(item, order):
    return {"schema_version": SCHEMA_VERSION, "canonical_identity": item["canonical_identity"],
            "canonical_key": item["source_field_key"], "display_name": item.get("source_label") or item["source_field_key"],
            "display_value": str(item["raw_value"]), "display_unit": item["raw_unit"] or "", "normalized_value": item["normalized_value"],
            "order": order, "source_field_key": item["source_field_key"], "evidence_references": item["evidence_references"],
            "rule_id": item["rule_id"], "resolution_status": item["resolution_status"], "qualifiers": item["qualifiers"],
            "conflict_group": item["conflict_group"], "review_references": item["review_references"]}


def build_plan(bundle):
    validate_inputs(bundle)
    policy = bundle["policy"]
    values = [normalize_observation(x, policy) for x in bundle["observations"]]
    values, reviews, conflicts = _deduplicate_and_conflict(values)
    for item in values:
        if item["resolution_status"] in {"manual_approval_required", "unsupported"}:
            review = _review(item["canonical_identity"], "value_normalization", item["source_field_key"], item["evidence_references"])
            item["review_references"] = sorted(set(item["review_references"] + [review["review_id"]]))
            reviews.append(review)
    products = []; specs = []; gaps = {}
    by_identity = {x["canonical_identity"]: x for x in bundle["products"]}
    for identity, product in sorted(by_identity.items()):
        own = [x for x in values if x["canonical_identity"] == identity]
        mapping, category_reviews = map_categories(product, bundle["category_matrix"], bundle["category_catalog"]); reviews += category_reviews
        structured = {}
        for item in own:
            if item["target_field"] and item["resolution_status"] in {"exact", "normalized", "derived_by_approved_rule", "manual_approved"}:
                structured[item["target_field"]] = {"value": item["normalized_value"], "unit": item["normalized_unit"], "status": item["resolution_status"], "observation_reference": item["observation_id"]}
            else: specs.append(_spec(item, 0))
            if item["source_field_key"] in GAP_FIELDS and item["normalized_value"] is not None:
                concept, magnitude, unit = GAP_FIELDS[item["source_field_key"]]
                gap = gaps.setdefault(concept, {"schema_version": SCHEMA_VERSION, "concept": concept, "source_fields": set(), "magnitude": magnitude,
                  "observed_units": set(), "affected_products": set(), "evidence_references": set(), "provisional_destination": "ProductSpec",
                  "interpretation_risk": "requires semantic and backend review", "proposed_type": "decimal" if unit else "string",
                  "proposed_canonical_unit": unit, "status": "proposed", "approval_required": True})
                gap["source_fields"].add(item["source_field_key"]); gap["observed_units"].add(item["normalized_unit"] or item["raw_unit"] or "unknown")
                gap["affected_products"].add(identity); gap["evidence_references"].update(item["evidence_references"])
        blocking = [x["review_id"] for x in reviews if x["canonical_identity"] == identity and x["blocking"]]
        has_gap = any(x["source_field_key"] in GAP_FIELDS and x["normalized_value"] is not None for x in own)
        readiness = "conflict_blocked" if any(x["canonical_identity"] == identity for x in conflicts) else ("category_mapping_required" if mapping["mapping_status"] != "approved" else ("manual_review_required" if blocking else ("schema_gap_review_required" if has_gap else "normalized_ready_for_audit")))
        assets = bundle.get("asset_decisions", {}).get(identity, {})
        product_specs = sorted([x for x in specs if x["canonical_identity"] == identity], key=lambda x:(x["canonical_key"], x["display_value"], x["display_unit"]))
        for index, spec in enumerate(product_specs): spec["order"] = index
        products.append({"schema_version": SCHEMA_VERSION, "document_kind": "normalized_for_audit_not_api_payload", "canonical_identity": identity,
          "brand_code": product["brand_code"], "canonical_model": product["canonical_model"], "variant": product.get("variant"),
          "source_titles": product.get("source_titles", []), "source_categories": product["source_category_keys"], "category_mapping": mapping,
          "structured_fields": structured, "product_specs": product_specs, "media": assets.get("media", []),
          "technical_sheet": assets.get("technical_sheet"), "additional_documents": assets.get("additional_documents", []),
          "commercial": {"is_published": False, "price_visible": False, "is_featured": False, "price": None,
                         "supplier": None, "condition": None, "stock_status": None, "commercial_text": None},
          "reviews": blocking, "schema_gaps": sorted({GAP_FIELDS[x["source_field_key"]][0] for x in own if x["source_field_key"] in GAP_FIELDS and x["normalized_value"] is not None}),
          "upstream_fingerprints": bundle["upstream_fingerprints"], "normalization_policy_fingerprint": policy["fingerprint"], "readiness": readiness})
    gap_values=[]
    for value in gaps.values():
        value["source_fields"] = sorted(value["source_fields"]); value["observed_units"] = sorted(value["observed_units"]); value["product_count"] = len(value.pop("affected_products")); value["coverage"] = f"{value['product_count']}/{len(products)}"; value["evidence_references"] = sorted(value["evidence_references"]); value["proposal_id"] = "gap-" + fingerprint(value)[:20]; gap_values.append(value)
    payload = {"schema_version": SCHEMA_VERSION, "rules_version": POLICY_VERSION, "producer": "catalog-normalize", "fixture_only": bundle["fixture_only"],
      "structure_verified": bundle["structure_verified"], "input_fingerprints": bundle["upstream_fingerprints"], "observations": values,
      "products": products, "product_specs": sorted(specs,key=lambda x:(x["canonical_identity"],x["canonical_key"],x["display_value"])),
      "category_mapping_results": [x["category_mapping"] for x in products], "reviews": sorted(reviews,key=lambda x:x["review_id"]),
      "conflicts": conflicts, "schema_gaps": sorted(gap_values,key=lambda x:x["concept"]), "offline": True, "network_requests": 0,
      "api_calls": 0, "imported": False, "published": False}
    payload["fingerprint"] = fingerprint(payload)
    return payload


def validate_inputs(bundle, root=None):
    if bundle.get("schema_version") != SCHEMA_VERSION: raise NormalizationError("INPUT_INCOMPATIBLE", "unsupported input schema")
    if not bundle.get("fixture_only") and not bundle.get("structure_verified"): raise NormalizationError("UPSTREAM_BLOCKED", "live structure is not verified")
    identities = [x.get("canonical_identity") for x in bundle.get("products", [])]
    if None in identities or len(identities) != len(set(identities)): raise NormalizationError("IDENTITY_BLOCKED", "missing or duplicate identity")
    unknown = {x.get("canonical_identity") for x in bundle.get("observations", [])} - set(identities)
    if unknown: raise NormalizationError("ORPHAN_REFERENCE", "observation references unknown product")
    unknown_assets = set(bundle.get("asset_decisions", {})) - set(identities)
    if unknown_assets: raise NormalizationError("ASSET_IDENTITY_MISMATCH", "asset decision references another identity")
    for identity, decisions in bundle.get("asset_decisions", {}).items():
        for relative in decisions.get("media", []) + decisions.get("additional_documents", []) + ([decisions["technical_sheet"]] if decisions.get("technical_sheet") else []):
            try: safe_join(Path.cwd(), relative)
            except UnsafePathError as error: raise NormalizationError("UNSAFE_PATH", f"unsafe asset reference for {identity}") from error
    policy = bundle.get("policy", {}); expected = fingerprint({k:v for k,v in policy.items() if k != "fingerprint"})
    if policy.get("fingerprint") != expected: raise NormalizationError("POLICY_FINGERPRINT_MISMATCH", "normalization policy changed")
    if root:
        for reference in bundle.get("artifact_references", []):
            required = {"artifact_type", "schema_version", "path", "sha256", "size", "producer_fingerprint", "policy_version", "scope"}
            if set(reference) != required: raise NormalizationError("INPUT_INCOMPATIBLE", "artifact reference contract is incomplete")
            path = safe_join(Path(root), reference["path"])
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != Path(root).parent): raise NormalizationError("UNEXPECTED_SYMLINK", "artifact reference traverses symlink")
            if not path.is_file(): raise NormalizationError("ARTIFACT_MISSING", reference["path"])
            data = path.read_bytes()
            if len(data) != reference["size"] or hashlib.sha256(data).hexdigest() != reference["sha256"]: raise NormalizationError("ARTIFACT_ALTERED", reference["path"])


def _files(plan):
    collections = {"normalized-observations.json": plan["observations"], "normalized-products.json": plan["products"],
      "product-spec-candidates.json": plan["product_specs"], "category-mapping-results.json": plan["category_mapping_results"],
      "normalization-reviews.json": plan["reviews"], "normalization-conflicts.json": plan["conflicts"], "schema-gap-proposals.json": plan["schema_gaps"]}
    files = {name: canonical_bytes({"schema_version":SCHEMA_VERSION,"items":value}) for name,value in collections.items()}
    for product in plan["products"]: files[f"products/{product['canonical_identity']}/producto.json"] = canonical_bytes(product)
    report = (f"offline: true\nproducts: {len(plan['products'])}\nreviews: {len(plan['reviews'])}\nconflicts: {len(plan['conflicts'])}\nreadiness: audit only; import and publication are not authorized\n").encode()
    files["normalization-report.txt"] = report
    inventory = [{"path":name,"sha256":hashlib.sha256(data).hexdigest(),"size":len(data)} for name,data in sorted(files.items())]
    manifest = {"schema_version":SCHEMA_VERSION,"rules_version":POLICY_VERSION,"producer":"catalog-normalize","plan_fingerprint":plan["fingerprint"],
      "files":inventory,"counts":{"products":len(plan["products"]),"observations":len(plan["observations"]),"reviews":len(plan["reviews"]),"conflicts":len(plan["conflicts"]),"schema_gaps":len(plan["schema_gaps"])},
      "fixture_only":plan["fixture_only"],"structure_verified":plan["structure_verified"],"offline":True,"network_requests":0,"api_calls":0,"imported":False,"published":False}
    manifest["fingerprint"] = fingerprint(manifest); files["normalization-manifest.json"] = canonical_bytes(manifest)
    return files


def normalize_to(plan, expected_fingerprint, destination):
    if plan["fingerprint"] != expected_fingerprint: raise NormalizationError("PLAN_FINGERPRINT_MISMATCH", "inputs differ from plan")
    destination = Path(destination); expected = _files(plan)
    if destination.exists():
        result = verify_output(destination)
        if result["valid"] and set(result["files"]) == set(expected): return {"state":"already_complete","fingerprint":expected_fingerprint}
        raise NormalizationError("DESTINATION_CONFLICT", "existing destination is incomplete, altered, or has extras")
    parent = destination.parent; parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.normalizing-", dir=parent))
    try:
        for relative, data in expected.items():
            target = safe_join(staging, relative); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
            if target.read_bytes() != data: raise NormalizationError("STAGING_VERIFY_FAILED", relative)
        os.replace(staging, destination)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return {"state":"completed","fingerprint":expected_fingerprint}


def verify_output(root):
    root = Path(root)
    if root.is_symlink(): return {"valid":False,"errors":["UNEXPECTED_SYMLINK"],"files":[]}
    manifest_path = root / "normalization-manifest.json"
    if not manifest_path.is_file(): return {"valid":False,"errors":["MANIFEST_MISSING"],"files":[]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict")); expected = {x["path"]:x for x in manifest["files"]}; errors=[]
    actual=[]
    for path in sorted(root.rglob("*"), key=lambda x:x.as_posix()):
        if path.is_symlink(): errors.append("UNEXPECTED_SYMLINK:"+path.relative_to(root).as_posix()); continue
        if path.is_file() and path != manifest_path: actual.append(path.relative_to(root).as_posix())
    for relative, record in expected.items():
        path=safe_join(root,relative)
        if not path.is_file(): errors.append("MISSING:"+relative); continue
        data=path.read_bytes()
        if len(data)!=record["size"] or hashlib.sha256(data).hexdigest()!=record["sha256"]: errors.append("ALTERED:"+relative)
    for relative in sorted(set(actual)-set(expected)): errors.append("EXTRA:"+relative)
    return {"valid":not errors,"errors":errors,"files":sorted(actual+["normalization-manifest.json"])}
