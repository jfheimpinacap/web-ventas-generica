"""Pure, fail-closed planning for a later local binary observation pass."""
from __future__ import annotations

import hashlib
import copy
import re
from urllib.parse import unquote, urlsplit

from catalog_pipeline_common.serialization import canonical_bytes, content_fingerprint
from catalog_pipeline_common.binary_validation import validate_observed_binary
from .contract import root_category_contract
from .readiness import contract_fingerprint
from .snapshot import semantic_fingerprint, validate_snapshot

SCHEMA_VERSION = "2.0.0"
RULES_VERSION = "jem-local-binary-observation-plan-v2"
REPORT_SCHEMA_VERSION = "1.0.0"
REPORT_RULES_VERSION = "jem-local-binary-observation-report-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PATH_POLICY = {
    "kind": "root_relative_url_path",
    "percent_decoding": "reject_encoded_separators_and_ambiguous_double_decoding",
    "filesystem_resolution": False,
}
MEDIA_RULES = {
    "image": {"future_validation": ["bytes", "actual_mime", "sha256"]},
    "technical_sheet": {"future_validation": ["pdf_signature", "pdf_structure", "security", "size", "sha256"]},
}
CAPTURE_POLICY = {
    "allowed_method": "GET", "redirects_allowed": False, "proxies_allowed": False,
    "retries": 0, "cookies_allowed": False, "concurrent_requests": 1,
    "timeout_seconds": 15, "max_image_bytes": 10_000_000,
    "max_pdf_bytes": 25_000_000, "max_total_bytes": 250_000_000,
    "allowed_mime_types": {"image": ["image/jpeg", "image/png"],
                           "technical_sheet": ["application/pdf"]},
    "allowed_signatures": {"image": ["jpeg", "png"], "technical_sheet": ["pdf"]},
    "invalid_response": "abort_without_report", "byte_storage": "discard_after_validation",
}


class BinaryObservationError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(detail or code)


def normalize_base_url(value):
    if not isinstance(value, str) or not value:
        raise BinaryObservationError("BASE_URL_INVALID")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise BinaryObservationError("BASE_URL_INVALID") from error
    if ("?" in value or "#" in value or parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
            or port is None or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise BinaryObservationError("BASE_URL_NOT_EXACT_LOOPBACK")
    host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{port}"


def normalize_reference(value):
    if not isinstance(value, str) or not value or not value.startswith("/") or value.startswith("//"):
        raise BinaryObservationError("REFERENCE_NOT_ROOT_RELATIVE")
    if "\\" in value or "?" in value or "#" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise BinaryObservationError("REFERENCE_UNSAFE_CHARACTER")
    if urlsplit(value).scheme or urlsplit(value).netloc:
        raise BinaryObservationError("REFERENCE_URL_FORBIDDEN")
    lowered = value.casefold()
    if "http:" in lowered or "https:" in lowered:
        raise BinaryObservationError("REFERENCE_URL_FORBIDDEN")
    decoded = unquote(value)
    if decoded != value and ("/" in decoded[1:] and "%2f" in lowered or "\\" in decoded or "%" in decoded):
        raise BinaryObservationError("REFERENCE_AMBIGUOUS_ENCODING")
    segments = value[1:].split("/")
    if not segments or any(not segment or segment in (".", "..") or ":" in segment
                           or segment.endswith((".", " ")) for segment in segments):
        raise BinaryObservationError("REFERENCE_UNSAFE_SEGMENT")
    decoded_segments = decoded[1:].split("/")
    if (any(ord(char) < 32 or ord(char) == 127 for char in decoded)
            or any(segment in (".", "..") or ":" in segment or segment.endswith((".", " "))
                   for segment in decoded_segments)):
        raise BinaryObservationError("REFERENCE_TRAVERSAL")
    return value


def _fingerprint_is(value):
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def _validate_readiness(report, snapshot_fp, contract_fp):
    if not isinstance(report, dict):
        raise BinaryObservationError("READINESS_INVALID")
    required = {"schema_version", "rules_version", "report_fingerprint", "result", "snapshot_fingerprint",
                "contract_fingerprint", "assessment_mode", "source_mode", "snapshot_capture_mode",
                "mutation_authorized", "checks", "counts", "root_category", "relation_checks",
                "dto_compatibility", "binary_observability", "blockers", "warnings",
                "next_permitted_step", "zero_mutation_manifest"}
    if set(report) != required or report.get("schema_version") != "1.0.0" or report.get("rules_version") != "jem-local-readiness-v1":
        raise BinaryObservationError("READINESS_CONTRACT_INVALID")
    supplied = report.get("report_fingerprint")
    semantic = dict(report)
    semantic.pop("report_fingerprint", None)
    if not _fingerprint_is(supplied) or content_fingerprint(semantic) != supplied:
        raise BinaryObservationError("READINESS_FINGERPRINT")
    zero = report.get("zero_mutation_manifest")
    required_zero = {"assessment_network_requests": 0, "mutation_requests": 0, "resources_created": 0, "resources_updated": 0,
                     "resources_deleted": 0, "content_published": False, "mutation_authorized": False}
    if (report.get("result") != "read_compatible_manual_binary_verification" or report.get("blockers") != []
            or report.get("mutation_authorized") is not False or not isinstance(zero, dict)
            or set(zero) != set(required_zero)
            or any(zero.get(key) != expected for key, expected in required_zero.items())
            or not isinstance(report.get("counts"), dict) or report["counts"].get("blockers") != 0):
        raise BinaryObservationError("READINESS_NOT_ELIGIBLE")
    if report.get("snapshot_fingerprint") != snapshot_fp or report.get("contract_fingerprint") != contract_fp:
        raise BinaryObservationError("READINESS_INPUT_MISMATCH")
    warning_codes = sorted(item.get("code") for item in report.get("warnings", []) if isinstance(item, dict))
    if "BINARY_CONTENT_NOT_OBSERVABLE" not in warning_codes:
        raise BinaryObservationError("READINESS_WARNING_REQUIRED")
    return warning_codes


def _extension(path):
    final = path.rsplit("/", 1)[-1]
    return ("." + final.rsplit(".", 1)[-1].lower()) if "." in final else None


def _binding(collection, row, field, media_class, path):
    row_id = row.get("id")
    if type(row_id) is not int:
        raise BinaryObservationError("BINDING_ROW_ID_INVALID")
    product = row.get("product", row.get("product_id"))
    observable = type(product) is int
    if media_class == "image" and not observable:
        raise BinaryObservationError("IMAGE_RELATION_NOT_OBSERVABLE")
    value = {"collection": collection, "row_id": row_id, "field": field, "media_class": media_class,
             "root_relative_path": path, "product_id": product if observable else None,
             "relation_observable": observable,
             "manual_relation_verification_required": not observable,
             "declared_extension": _extension(path), "declared_content_type": None,
             "declared_size_bytes": None,
             "state": "planned" if observable else "manual_relation_verification_required"}
    if media_class == "technical_sheet":
        value["declared_content_type"] = row.get("content_type")
        size = row.get("size_bytes")
        if value["declared_content_type"] != "application/pdf" or type(size) is not int or size < 0:
            raise BinaryObservationError("TECHNICAL_SHEET_DECLARATION_INVALID")
        value["declared_size_bytes"] = size
    return value


def validate_plan(plan, *, capture=False):
    if not isinstance(plan, dict):
        raise BinaryObservationError("PLAN_CONTRACT_INVALID")
    if plan.get("schema_version") == "1.0.0" and plan.get("rules_version") == "jem-local-binary-observation-plan-v1":
        if capture: raise BinaryObservationError("CAPTURE_PLAN_VERSION_UNSUPPORTED")
        supplied=plan.get("plan_fingerprint"); semantic=dict(plan); semantic.pop("plan_fingerprint",None)
        if not _fingerprint_is(supplied) or content_fingerprint(semantic)!=supplied: raise BinaryObservationError("PLAN_FINGERPRINT")
        return plan
    if plan.get("schema_version") != SCHEMA_VERSION or plan.get("rules_version") != RULES_VERSION:
        raise BinaryObservationError("CAPTURE_PLAN_VERSION_UNSUPPORTED" if capture else "PLAN_VERSION_INVALID")
    if plan.get("state") not in ("planned", "blocked"):
        raise BinaryObservationError("PLAN_STATE_INVALID")
    for field in ("network_executed", "bytes_observed", "mutation_authorized", "content_published"):
        if plan.get(field) is not False:
            raise BinaryObservationError("PLAN_SAFETY_INVARIANT")
    if plan.get("capture_supported") is not True or plan.get("next_permitted_step") != "limited_local_get_capture":
        raise BinaryObservationError("CAPTURE_NOT_SUPPORTED")
    if plan.get("capture_policy") != CAPTURE_POLICY: raise BinaryObservationError("CAPTURE_POLICY_INVALID")
    supplied = plan.get("plan_fingerprint")
    semantic = dict(plan)
    semantic.pop("plan_fingerprint", None)
    if not _fingerprint_is(supplied) or content_fingerprint(semantic) != supplied:
        raise BinaryObservationError("PLAN_FINGERPRINT")
    return plan


def build_plan(snapshot, readiness, contract, base_url, snapshot_file_sha256, readiness_file_sha256,
               *, fixture_only=False):
    """Validate in-memory inputs and return a deterministic plan; perform no I/O."""
    if fixture_only:
        raise BinaryObservationError("FIXTURE_PLAN_NOT_CAPTURE_ELIGIBLE")
    if not _fingerprint_is(snapshot_file_sha256) or not _fingerprint_is(readiness_file_sha256):
        raise BinaryObservationError("INPUT_FILE_HASH_INVALID")
    contract_fp = contract_fingerprint(contract)
    metadata = contract.get("local_readiness") if isinstance(contract, dict) else None
    definitions = metadata.get("collections") if isinstance(metadata, dict) else None
    if (not isinstance(definitions, list)
            or {item.get("name") for item in definitions if isinstance(item, dict)} != set(snapshot.get("collections", {}))):
        raise BinaryObservationError("CONTRACT_COLLECTIONS_INVALID")
    try:
        root_category_contract(contract)
    except ValueError as error:
        raise BinaryObservationError("CONTRACT_ROOT_CATEGORY_INVALID") from error
    validate_snapshot(snapshot, contract_fp)
    if snapshot.get("classification") != "local_development" or snapshot.get("fixture_only") is True:
        raise BinaryObservationError("SNAPSHOT_NOT_LOCAL_DEVELOPMENT")
    snapshot_fp = semantic_fingerprint(snapshot)
    warnings = _validate_readiness(readiness, snapshot_fp, contract_fp)
    grouped = {}
    sources = (("product_images", "image", "image"),
               ("technical_sheets", "file_url", "technical_sheet"))
    for collection, field, media_class in sources:
        for row in snapshot["collections"][collection]:
            path = normalize_reference(row.get(field))
            binding = _binding(collection, row, field, media_class, path)
            entry = grouped.setdefault(path, {"classes": set(), "bindings": []})
            entry["classes"].add(media_class)
            entry["bindings"].append(binding)
    conflicts = sorted(path for path, item in grouped.items() if len(item["classes"]) != 1)
    if conflicts:
        raise BinaryObservationError("MEDIA_CLASS_CONFLICT", ",".join(conflicts))
    targets = []
    for path in sorted(grouped):
        item = grouped[path]
        media_class = next(iter(item["classes"]))
        bindings = sorted(item["bindings"], key=lambda value: canonical_bytes(value))
        target_id = "target-" + hashlib.sha256((media_class + "\0" + path).encode("utf-8")).hexdigest()[:24]
        targets.append({"target_id": target_id, "root_relative_path": path, "media_class": media_class,
                        "policy": MEDIA_RULES[media_class], "bindings": bindings})
    all_bindings = [binding for target in targets for binding in target["bindings"]]
    counts = {"targets_total": len(targets),
              "image_targets": sum(target["media_class"] == "image" for target in targets),
              "technical_sheet_targets": sum(target["media_class"] == "technical_sheet" for target in targets),
              "bindings_total": len(all_bindings),
              "relations_observable": sum(binding["relation_observable"] for binding in all_bindings),
              "manual_relations": sum(binding["manual_relation_verification_required"] for binding in all_bindings),
              "blockers": 0, "warnings": len(warnings)}
    plan = {"schema_version": SCHEMA_VERSION, "rules_version": RULES_VERSION, "fixture_only": False,
            "state": "planned", "base_url": normalize_base_url(base_url),
            "contract_fingerprint": contract_fp, "snapshot_semantic_fingerprint": snapshot_fp,
            "snapshot_file_sha256": snapshot_file_sha256, "readiness_file_sha256": readiness_file_sha256,
            "path_policy": PATH_POLICY, "media_rules": MEDIA_RULES, "targets": targets, "counts": counts,
            "blockers": [], "warnings": warnings, "network_executed": False, "bytes_observed": False,
            "capture_policy": copy.deepcopy(CAPTURE_POLICY), "capture_supported": True, "mutation_authorized": False,
            "content_published": False, "next_permitted_step": "limited_local_get_capture"}
    plan["plan_fingerprint"] = content_fingerprint(plan)
    return validate_plan(plan)

def _fail(code): raise BinaryObservationError(code)

def capture_plan(plan, expected_fingerprint, plan_file_sha256, transport):
    """Execute the sealed targets through an injected GET-only callable; retain no body bytes."""
    validate_plan(plan, capture=True)
    if plan.get("plan_fingerprint") != expected_fingerprint: _fail("CAPTURE_PLAN_FINGERPRINT_MISMATCH")
    if not _fingerprint_is(plan_file_sha256): _fail("CAPTURE_PLAN_FILE_HASH_INVALID")
    if plan.get("fixture_only") is not False or plan.get("state") != "planned": _fail("CAPTURE_NOT_SUPPORTED")
    if plan.get("blockers") != [] or plan.get("counts",{}).get("blockers") != 0: _fail("CAPTURE_NOT_SUPPORTED")
    normalize_base_url(plan.get("base_url"))
    targets=plan.get("targets"); counts=plan.get("counts")
    if not isinstance(targets,list) or not isinstance(counts,dict): _fail("CAPTURE_PLAN_INVALID")
    if len({t.get("target_id") for t in targets})!=len(targets) or len({t.get("root_relative_path") for t in targets})!=len(targets): _fail("CAPTURE_PLAN_INVALID")
    expected={"targets_total":len(targets),"image_targets":sum(t.get("media_class")=="image" for t in targets),"technical_sheet_targets":sum(t.get("media_class")=="technical_sheet" for t in targets),"bindings_total":sum(len(t.get("bindings",[])) for t in targets),"relations_observable":sum(bool(b.get("relation_observable")) for t in targets for b in t.get("bindings",[])),"manual_relations":sum(bool(b.get("manual_relation_verification_required")) for t in targets for b in t.get("bindings",[])),"blockers":0,"warnings":len(plan.get("warnings",[]))}
    if counts!=expected: _fail("CAPTURE_PLAN_INVALID")
    receipts=[]; total=0; policy=CAPTURE_POLICY
    for target in targets:
        path=normalize_reference(target.get("root_relative_path")); media=target.get("media_class")
        if media not in ("image","technical_sheet") or not isinstance(target.get("bindings"),list) or not target["bindings"]: _fail("CAPTURE_PLAN_INVALID")
        if any(normalize_reference(binding.get("root_relative_path"))!=path or binding.get("media_class")!=media for binding in target["bindings"]): _fail("CAPTURE_PLAN_INVALID")
        limit=policy["max_image_bytes" if media=="image" else "max_pdf_bytes"]
        response=transport(plan["base_url"],path,{"Accept":", ".join(policy["allowed_mime_types"].get(media,[]))},policy["timeout_seconds"],limit)
        if not isinstance(response,dict) or set(response)!={"status","mime","body","content_length"}: _fail("BINARY_READ_RESPONSE_INVALID")
        if response["status"]!=200: _fail("BINARY_READ_STATUS")
        mime=response["mime"].split(";",1)[0].strip().lower() if isinstance(response["mime"],str) else ""
        if mime not in policy["allowed_mime_types"].get(media,[]): _fail("BINARY_READ_MIME")
        body=response["body"]
        if not isinstance(body,bytes) or not body: _fail("BINARY_READ_EMPTY")
        if len(body)>limit: _fail("BINARY_READ_TOO_LARGE")
        declared=response["content_length"]
        if declared is not None:
            if not isinstance(declared,str) or not declared.isascii() or not declared.isdecimal(): _fail("BINARY_CONTENT_LENGTH_INVALID")
            if int(declared)>limit: _fail("BINARY_READ_TOO_LARGE")
            if int(declared)!=len(body): _fail("BINARY_CONTENT_LENGTH_MISMATCH")
        total+=len(body)
        if total>policy["max_total_bytes"]: _fail("BINARY_TOTAL_LIMIT_EXCEEDED")
        validation=validate_observed_binary(body,media,mime,target.get("bindings",[]))
        if validation["code"]: _fail(validation["code"])
        receipts.append({"target_id":target["target_id"],"media_class":media,"bindings":target["bindings"],"observed_status":200,"observed_mime":mime,"observed_size_bytes":len(body),"observed_sha256":hashlib.sha256(body).hexdigest(),"binary_validation":validation["validation"],"declared_size_match":validation["declared_size_match"],"relation_observable":all(b["relation_observable"] for b in target["bindings"]),"manual_relation_verification_required":any(b["manual_relation_verification_required"] for b in target["bindings"])})
        del body
    manual=sum(r["manual_relation_verification_required"] for r in receipts)
    report={"schema_version":REPORT_SCHEMA_VERSION,"rules_version":REPORT_RULES_VERSION,"fixture_only":False,"plan_fingerprint":plan["plan_fingerprint"],"plan_file_sha256":plan_file_sha256,"contract_fingerprint":plan["contract_fingerprint"],"snapshot_semantic_fingerprint":plan["snapshot_semantic_fingerprint"],"base_url":plan["base_url"],"state":"observed_manual_relation_verification_required" if manual else "observed","receipts":receipts,"counts":{"targets_expected":len(targets),"targets_observed":len(receipts),"get_requests":len(receipts),"images":expected["image_targets"],"pdfs":expected["technical_sheet_targets"],"bytes_total":total,"manual_relations":manual,"blockers":0,"warnings":len(plan["warnings"])},"blockers":[],"warnings":plan["warnings"],"network_manifest":{"network_executed":True,"bytes_observed":True,"method":"GET","requests":len(receipts),"redirects":0,"retries":0,"concurrency":1},"zero_mutation_manifest":{"mutation_authorized":False,"content_published":False,"post_requests":0,"put_requests":0,"patch_requests":0,"delete_requests":0},"next_permitted_step":"prompt_304_readiness_integration"}
    report["report_fingerprint"]=content_fingerprint(report); return report
