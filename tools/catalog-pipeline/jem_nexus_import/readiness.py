"""Pure, deterministic certification of an already captured local snapshot.

This module deliberately accepts in-memory values only.  It owns no transport,
environment, persistence, authorization, or mutation concern.
"""
from __future__ import annotations

import copy
import hashlib
import unicodedata

from catalog_pipeline_common.serialization import canonical_bytes, content_fingerprint
from .contract import root_category_contract, select_contract_root
from .snapshot import semantic_fingerprint

SCHEMA_VERSION = "1.0.0"
RULES_VERSION = "jem-local-readiness-v1"
RESULTS = frozenset(("read_compatible", "read_compatible_manual_binary_verification", "read_incompatible"))


def contract_fingerprint(contract):
    """Fingerprint the complete inspected contract using canonical UTF-8 JSON."""
    return hashlib.sha256(canonical_bytes(contract)).hexdigest()


def _fold(value):
    return unicodedata.normalize("NFC", value).casefold() if isinstance(value, str) else None


def _valid(value, kind):
    if kind == "positive_integer": return isinstance(value, int) and not isinstance(value, bool) and value > 0
    if kind == "non_negative_integer": return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if kind == "non_empty_string": return isinstance(value, str) and bool(value.strip())
    if kind == "string": return isinstance(value, str)
    if kind == "boolean": return isinstance(value, bool)
    if kind == "object": return isinstance(value, dict)
    if kind == "nullable_object": return value is None or isinstance(value, dict)
    if kind == "nullable_string": return value is None or isinstance(value, str)
    if kind == "nullable_positive_integer": return value is None or _valid(value, "positive_integer")
    return False


def _issue(code, collection=None, field=None, detail=None):
    value = {"code": code}
    if collection is not None: value["collection"] = collection
    if field is not None: value["field"] = field
    if detail is not None: value["detail"] = detail
    return value


def _binary(name, items):
    image = name == "product_images"
    relation = [isinstance(x.get("product", x.get("product_id")), int) for x in items]
    filename = [isinstance(x.get("image" if image else "original_file_name"), str) for x in items]
    mime = [isinstance(x.get("content_type"), str) for x in items]
    size = [isinstance(x.get("size_bytes"), int) and not isinstance(x.get("size_bytes"), bool) for x in items]
    sha = [isinstance(x.get("sha256"), str) and len(x["sha256"]) == 64 for x in items]
    raw = [isinstance(x.get("bytes"), str) and bool(x["bytes"]) for x in items]
    all_if_any = lambda values: not items or all(values)
    exact = all_if_any(sha) and all_if_any(raw)
    return {"class": "images" if image else "technical_sheets", "count": len(items),
            "relation_observable": all_if_any(relation) if image else False,
            "filename_observable": all_if_any(filename), "mime_observable": all_if_any(mime),
            "size_observable": all_if_any(size), "sha256_observable": all_if_any(sha),
            "bytes_observable": all_if_any(raw), "exact_verification_capable": exact}


def assess(snapshot, contract):
    """Return a report without changing either input."""
    snapshot = copy.deepcopy(snapshot)
    contract = copy.deepcopy(contract)
    blockers, warnings, collection_checks, relation_checks, dto = [], [], [], [], []
    metadata = contract.get("local_readiness")
    actual_contract = contract_fingerprint(contract)
    if not isinstance(metadata, dict) or metadata.get("rules_version") != RULES_VERSION:
        blockers.append(_issue("RULES_VERSION_INCOMPATIBLE"))
        definitions = []
    else:
        definitions = metadata.get("collections", []) if isinstance(metadata.get("collections"), list) else []
    if snapshot.get("schema_version") != SCHEMA_VERSION or snapshot.get("complete") is not True:
        blockers.append(_issue("SCHEMA_VERSION_INCOMPATIBLE"))
    if snapshot.get("contract_fingerprint") != actual_contract:
        blockers.append(_issue("CONTRACT_FINGERPRINT_MISMATCH"))
    try: actual_snapshot = semantic_fingerprint(snapshot)
    except (AttributeError, TypeError, ValueError): actual_snapshot = None
    if snapshot.get("semantic_fingerprint") != actual_snapshot:
        blockers.append(_issue("SNAPSHOT_FINGERPRINT_MISMATCH"))

    collections = snapshot.get("collections")
    if not isinstance(collections, dict): collections = {}
    ids = {}
    for definition in sorted(definitions, key=lambda x: x.get("name", "")):
        name, endpoint = definition.get("name"), definition.get("endpoint")
        present, items = name in collections, collections.get(name)
        valid_type = isinstance(items, list)
        safe_items = items if valid_type else []
        if not present: blockers.append(_issue("COLLECTION_MISSING", name))
        elif not valid_type: blockers.append(_issue("COLLECTION_TYPE_INVALID", name))
        values = [x.get("id") for x in safe_items if isinstance(x, dict)]
        unique = all(_valid(value, "positive_integer") for value in values) and len(values) == len(set(values)) and len(values) == len(safe_items)
        if not unique: blockers.append(_issue("DUPLICATE_ID", name))
        ids[name] = set(x for x in values if _valid(x, "positive_integer"))
        identity_field = definition.get("identity_field")
        identities = [_fold(x.get(identity_field)) for x in safe_items if isinstance(x, dict)] if identity_field else []
        canonical = not identity_field or (None not in identities and len(identities) == len(safe_items))
        collision = bool(identity_field and canonical and len(identities) != len(set(identities)))
        if collision: blockers.append(_issue("IDENTITY_COLLISION", name, identity_field))
        required = definition.get("required_fields", {})
        fields_ok = True
        received = sorted({field for item in safe_items if isinstance(item, dict) for field in item})
        for index, item in enumerate(safe_items):
            if not isinstance(item, dict):
                fields_ok = False; blockers.append(_issue("DTO_FIELD_TYPE_INVALID", name, None, str(index))); continue
            for field, kind in sorted(required.items()):
                aliases = field.split("|")
                observed = next((item[key] for key in aliases if key in item), None)
                if not any(key in item for key in aliases):
                    fields_ok = False; blockers.append(_issue("DTO_FIELD_MISSING", name, field))
                elif not _valid(observed, kind):
                    fields_ok = False; blockers.append(_issue("DTO_FIELD_TYPE_INVALID", name, field))
        collection_checks.append({"collection": name, "source_endpoint": endpoint, "present": present,
                                  "valid_type": valid_type, "count": len(safe_items), "ids_unique": unique,
                                  "canonical_identity_valid": canonical and not collision,
                                  "relations_valid": True, "required_fields_present": fields_ok})
        dto.append({"collection": name, "source_endpoint": endpoint, "fields_received": received,
                    "fields_consumed": sorted(required), "types": {k: required[k] for k in sorted(required)},
                    "identity": identity_field, "relations": [], "unknown_fields_ignored": True,
                    "compatibility": "compatible" if valid_type and fields_ok else "incompatible"})

    def orphan(collection, field, target, extractor=None, nullable=False):
        items = collections.get(collection, []) if isinstance(collections.get(collection), list) else []
        bad = 0
        for item in items:
            value = extractor(item) if extractor else item.get(field)
            if value is None and nullable: continue
            if value not in ids.get(target, set()): bad += 1
        if bad: blockers.append(_issue("ORPHAN_RELATION", collection, field, str(bad)))
        relation_checks.append({"collection": collection, "field": field, "target_collection": target,
                                "observable": True, "valid": bad == 0, "orphan_count": bad})
        for row in dto:
            if row["collection"] == collection: row["relations"].append(field)
        for row in collection_checks:
            if row["collection"] == collection: row["relations_valid"] = row["relations_valid"] and bad == 0

    orphan("categories", "parent", "categories", nullable=True)
    orphan("products", "category", "categories", lambda x: x.get("category", {}).get("id") if isinstance(x.get("category"), dict) else None)
    orphan("products", "brand", "brands", lambda x: x.get("brand", {}).get("id") if isinstance(x.get("brand"), dict) else None, nullable=True)
    orphan("products", "supplier", "suppliers", lambda x: x.get("supplier", {}).get("id") if isinstance(x.get("supplier"), dict) else None, nullable=True)
    orphan("product_images", "product", "products", lambda x: x.get("product", x.get("product_id")))
    orphan("product_specs", "product", "products", lambda x: x.get("product", x.get("product_id")))
    sheets = collections.get("technical_sheets", []) if isinstance(collections.get("technical_sheets"), list) else []
    sheet_relation_observable = any("product" in x or "product_id" in x for x in sheets if isinstance(x, dict))
    if sheet_relation_observable: orphan("technical_sheets", "product", "products", lambda x: x.get("product", x.get("product_id")))
    else: relation_checks.append({"collection":"technical_sheets","field":"product","target_collection":"products","observable":False,"valid":True,"orphan_count":0})

    try:
        root_contract = root_category_contract(contract)
        root_selection = select_contract_root(collections.get(root_contract["collection"]), root_contract)
    except ValueError:
        root_contract = {"identity": None}
        root_selection = {"status":"invalid", "matches":[], "root":None}
        blockers.append(_issue("ROOT_CATEGORY_CONTRACT_INVALID", "categories"))
    roots = root_selection["matches"]
    if root_selection["status"] == "missing": blockers.append(_issue("ROOT_CATEGORY_MISSING", "categories"))
    elif root_selection["status"] == "ambiguous": blockers.append(_issue("ROOT_CATEGORY_AMBIGUOUS", "categories"))
    elif root_selection["status"] == "invalid": blockers.append(_issue("ROOT_CATEGORY_INVALID", "categories"))
    root_result = {"identity": root_contract.get("identity"), "count": len(roots),
                   "unique": len(roots) == 1,
                   "positive_integer_id": len(roots) == 1 and _valid(roots[0].get("id"), "positive_integer"),
                   "valid": root_selection["status"] == "valid"}

    binaries = [_binary("product_images", collections.get("product_images", []) if isinstance(collections.get("product_images"), list) else []),
                _binary("technical_sheets", sheets)]
    needs_manual = any(x["count"] and not x["exact_verification_capable"] for x in binaries)
    if needs_manual: warnings.append(_issue("BINARY_CONTENT_NOT_OBSERVABLE"))
    blockers = sorted(blockers, key=lambda x: (x["code"], x.get("collection", ""), x.get("field", ""), x.get("detail", "")))
    warnings = sorted(warnings, key=lambda x: x["code"])
    result = "read_incompatible" if blockers else ("read_compatible_manual_binary_verification" if needs_manual else "read_compatible")
    report = {"schema_version": SCHEMA_VERSION, "rules_version": RULES_VERSION, "result": result,
              "snapshot_fingerprint": snapshot.get("semantic_fingerprint", ""), "contract_fingerprint": actual_contract,
              "assessment_mode": "offline", "source_mode": "local_get_snapshot", "snapshot_capture_mode": "local_get_read_only",
              "mutation_authorized": False, "checks": sorted(collection_checks, key=lambda x: x["collection"]),
              "counts": {"collections_required": len(definitions), "collections_present": sum(x["present"] for x in collection_checks),
                         "resources_observed": sum(x["count"] for x in collection_checks), "blockers": len(blockers), "warnings": len(warnings)},
              "root_category": root_result, "relation_checks": sorted(relation_checks, key=lambda x: (x["collection"], x["field"])),
              "dto_compatibility": sorted(dto, key=lambda x: x["collection"]), "binary_observability": binaries,
              "blockers": blockers, "warnings": warnings,
              "next_permitted_step": "correct_snapshot_or_contract" if blockers else ("manual_binary_verification" if needs_manual else "planning_or_dry_run"),
              "zero_mutation_manifest": {"assessment_network_requests": 0, "mutation_requests": 0, "resources_created": 0,
                                           "resources_updated": 0, "resources_deleted": 0, "content_published": False,
                                           "mutation_authorized": False}}
    report["report_fingerprint"] = content_fingerprint(report)
    return report
