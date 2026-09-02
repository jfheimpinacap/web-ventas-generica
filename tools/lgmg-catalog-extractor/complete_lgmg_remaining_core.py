#!/usr/bin/env python3
"""Finalización local, reducida y reversible del catálogo LGMG."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


def _load_base():
    path = Path(__file__).with_name("import_lgmg_remaining_controlled.py")
    spec = importlib.util.spec_from_file_location("lgmg_controlled_import", path)
    if spec is None or spec.loader is None:
        raise ImportError("No se pudo cargar el importador controlado")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_base()  # El módulo base protege su CLI con __name__ == "__main__".

TOOL_NAME = "complete_lgmg_remaining_core"
TOOL_VERSION = "1.0.2"
CHECKPOINT_SCHEMA_VERSION = "1.0"
COMPLETION_PROFILE = "core_products_with_primary_images"
HUMAN_APPROVAL = "APRUEBO LA FINALIZACIÓN REDUCIDA CON 34 PRODUCTOS Y 34 IMÁGENES PRINCIPALES"
APPLY_CONFIRMATION = "CREAR_34_LGMG_CON_IMAGEN_PRINCIPAL"
ROLLBACK_CONFIRMATION = "REVERTIR_FINALIZACION_REDUCIDA_LGMG"
TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
SOURCE_SHA256 = "dbb5ece22d1dcaabf16e8cb9c3bba1ebb57c1acec30fde68ec8bfe40a9a25eef"
SOURCE_SIZE = 1_825_474
PARTIAL_RESUME_FINGERPRINT = "8490bae3e3693fbef8752eafcf231d86528da6bbbb895b93d507eb0b84edf177"
APPROVED_101_SHA256 = "1e655c651425d543c99c650d1730849bb8a86a6fbff9b218c1022dfdbcbc4dc9"
APPROVED_101_SIZE = 138_358
APPROVED_101_PLAN_FINGERPRINT = "d6bdd8571e8b0b977afe27d222d55e39f77933d836aa44ff671b21642db55be4"
APPROVED_101_REMOTE_FINGERPRINT = "9a5a64bf4a234cb5c0648b72fe7ede34773820771075cf9cd894e969cc37d9c2"
HISTORICAL_MODELS = {"SR0818E-2", "SR1018E-2"}
PARTIAL_MODEL = "SR1218E-2"
PARTIAL_SHEET_KEY = "1163d8780457d6ecfbf64b6fa2733b930cb36b221e9ba8a0e7b5168d77915458"
PARTIAL_SHEET_NAME = "Ficha técnica LGMG SR1218E-2"
PARTIAL_SHEET_SHA256 = "fbfb3916b94d600e19df841560bf11bdf6dee9d7dd26500da44f5894cafde409"
PARTIAL_SHEET_SIZE = 406_080
PARTIAL_SHEET_ORIGINAL_FILENAME = PARTIAL_SHEET_SHA256 + ".pdf"
OUTPUT_NAMES = (
    "core-products.csv", "core-images.csv", "core-operations.csv", "core-conflicts.csv",
    "core-summary.json", "core-manifest.json", "README-core-completion.txt",
)
STATES = {"core_dry_run_ready", "core_apply_in_progress", "core_apply_partial",
          "core_apply_complete", "core_rollback_in_progress", "core_rollback_complete"}

ConflictError = base.ConflictError
ControlledImportError = base.ControlledImportError
RequestCoordinator = base.RateLimitCoordinator
ApiClient = base.ApiClient
canonical = base.canonical
sha = base.sha


def access_token(environ=os.environ):
    return base.access_token(environ)


def normalize_origin(value):
    origin = base.normalize_origin(value)
    from urllib.parse import urlsplit
    parsed = urlsplit(origin)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.port is None:
        raise ConflictError("--api-base-url solo admite http://localhost:<puerto> o http://127.0.0.1:<puerto>")
    return origin


def validate_source_checkpoint(path: Path, *, expected_sha256=SOURCE_SHA256, expected_size=SOURCE_SIZE):
    raw = base.regular_bytes(path, "source-checkpoint")
    if len(raw) != expected_size or sha(raw) != expected_sha256:
        raise ConflictError("Hash o tamaño del source checkpoint histórico no coincide")
    value = base.json_value(raw, "source-checkpoint")
    if value.get("version") != "2.1.1" or value.get("state") != "apply_partial":
        raise ConflictError("Versión o estado del source checkpoint histórico inválido")
    planned, completed = value.get("planned_operations"), value.get("completed_operations")
    if not isinstance(planned, list) or len(planned) != 1197 or not isinstance(completed, list) or len(completed) != 65:
        raise ConflictError("El source checkpoint debe contener 1.197 planificadas y 65 completadas")
    keys = [item.get("operation_key") for item in planned]
    if len(set(keys)) != 1197 or any(not re.fullmatch(r"[0-9a-f]{64}", str(k)) for k in keys):
        raise ConflictError("Plan histórico no cerrado")
    done = {item.get("operation_key"): item for item in completed}
    if set(done) != set(keys[:65]):
        raise ConflictError("Las 65 operaciones históricas no forman un prefijo cerrado")
    product_done = [x for x in completed if x.get("resource_type") == "product"]
    image_done = [x for x in completed if x.get("resource_type") == "image"]
    sheet_done = [x for x in completed if x.get("resource_type") == "datasheet"]
    spec_done = [x for x in completed if x.get("resource_type") == "specification"]
    if tuple(map(len, (product_done, image_done, sheet_done, spec_done))) != (2, 2, 3, 58):
        raise ConflictError("Recursos históricos no coinciden con 2/2/3/58")
    models = {x.get("metric_model") for x in product_done}
    if models != HISTORICAL_MODELS:
        raise ConflictError("Los dos productos históricos exactos no coinciden")
    partial = done.get(PARTIAL_SHEET_KEY)
    if not partial or partial.get("metric_model") != PARTIAL_MODEL or partial.get("resource_type") != "datasheet":
        raise ConflictError("La ficha histórica de SR1218E-2 no deriva de la operación 65")
    operation = planned[keys.index(PARTIAL_SHEET_KEY)]
    template = operation.get("request_template", {})
    if template.get("name") != PARTIAL_SHEET_NAME or operation.get("file_sha256") != PARTIAL_SHEET_SHA256 or int(operation.get("file_size_bytes", 0)) != PARTIAL_SHEET_SIZE:
        raise ConflictError("Identidad física de la ficha histórica divergente")
    return value, raw, {"products": product_done, "images": image_done, "datasheets": sheet_done,
                        "specifications": spec_done, "partial_sheet_id": partial.get("resource_id")}


def validate_historical_sheet(sheets, resource_id, name, digest, size, allowed_product_ids=()):
    """Validate the historical sheet against the backend's read DTO, field by field."""
    from urllib.parse import urlsplit

    hits = [item for item in sheets if item.get("id") == resource_id]
    if len(hits) != 1:
        raise ConflictError("historical_sheet_id_mismatch")
    sheet = hits[0]
    if sheet.get("name") != name:
        raise ConflictError("historical_sheet_name_mismatch")
    expected_filename = digest + ".pdf"
    filename = sheet.get("original_file_name")
    if filename != expected_filename or not filename.endswith(".pdf") or filename[:-4] != digest:
        raise ConflictError("historical_sheet_original_filename_mismatch")
    if sheet.get("content_type") != "application/pdf":
        raise ConflictError("historical_sheet_content_type_mismatch")
    if type(sheet.get("size_bytes")) is not int or sheet["size_bytes"] != size:
        raise ConflictError("historical_sheet_size_mismatch")
    expected_url = f"/technical-sheets/{resource_id}/file"
    file_url = sheet.get("file_url")
    parsed = urlsplit(file_url) if isinstance(file_url, str) else None
    if (file_url != expected_url or parsed is None or parsed.scheme or parsed.netloc or
            parsed.username or parsed.password or parsed.query or parsed.fragment or ".." in parsed.path.split("/")):
        raise ConflictError("historical_sheet_file_url_mismatch")
    explicit_digest = sheet.get("sha256")
    if explicit_digest not in (None, "") and explicit_digest != digest:
        raise ConflictError("historical_sheet_explicit_sha256_mismatch")
    associations = []
    for key in ("product_id", "productId"):
        if sheet.get(key) is not None:
            associations.append(sheet[key])
    if sheet.get("product") is not None:
        product = sheet["product"]
        associations.append(product.get("id") if isinstance(product, dict) else product)
    allowed = set(allowed_product_ids)
    if any(value not in allowed for value in associations):
        raise ConflictError("historical_sheet_unexpected_product_association")
    return sheet


def derive_core(data, state, categories, brand, historical, sheet_validator=None):
    decisions = base.classify_products(data, state, categories, brand)
    if len(decisions) != 36:
        raise ConflictError("La cohorte aprobada debe contener 36 productos")
    exact = [d for d in decisions if d["status"] == "already_imported_exact"]
    missing = [d for d in decisions if d["status"] == "create_candidate"]
    conflicts = [d for d in decisions if d["status"] == "conflict_existing_product"]
    if conflicts or {d["row"]["metric_model"] for d in exact} != HISTORICAL_MODELS or len(exact) != 2 or len(missing) != 34:
        raise ConflictError("CONFLICT: se exigen exactamente 2 históricos y 34 ausentes")
    if len({(d["row"]["source_key"], d["row"]["metric_model"], d["row"]["approval_key"]) for d in decisions}) != 36:
        raise ConflictError("Identidad source_key + metric_model + approval_key duplicada")
    sheet_id = historical["partial_sheet_id"]
    if not isinstance(sheet_id, int) or sheet_id <= 0:
        raise ConflictError("ID derivado de ficha histórica inválido")
    if sheet_validator is not None:
        sheet_validator(sheet_id, PARTIAL_SHEET_NAME, PARTIAL_SHEET_SHA256, PARTIAL_SHEET_SIZE)
    operations = build_core_operations(data, missing, sheet_id)
    return decisions, operations


def build_core_operations(data, missing, partial_sheet_id):
    operations = []
    for index, decision in enumerate(missing):
        row, payload = decision["row"], dict(decision["payload"])
        payload["technical_sheet"] = partial_sheet_id if row["metric_model"] == PARTIAL_MODEL else None
        batch = 1 if index < 20 else 2
        product = {"operation_order": len(operations) + 1, "batch": batch,
                   "approval_key": row["approval_key"], "source_key": row["source_key"],
                   "metric_model": row["metric_model"], "phase": "product", "method": "POST",
                   "path_template": "/api/products", "resource_type": "product", "action": "create",
                   "depends_on_operation_key": "", "request_template": payload,
                   "payload_sha256": sha(canonical(payload))}
        product["operation_key"] = operation_key(product)
        operations.append(product)
        primary = [x for x in data["images"][row["metric_model"]] if base.truth(x.get("is_primary"))]
        if len(primary) != 1:
            raise ConflictError("Cada producto ausente exige exactamente una imagen principal")
        image = primary[0]
        template = {"product_id_ref": {"operation_key": product["operation_key"]},
                    "is_main": True, "order": 0, "alt_text": image.get("original_filename", "")}
        operation = {"operation_order": len(operations) + 1, "batch": batch,
                     "approval_key": row["approval_key"], "source_key": row["source_key"],
                     "metric_model": row["metric_model"], "phase": "primary_image", "method": "POST",
                     "path_template": "/api/product-images", "resource_type": "image", "action": "upload_primary",
                     "depends_on_operation_key": product["operation_key"], "request_template": template,
                     "payload_sha256": sha(canonical(template)), "file_sha256": image["sha256"],
                     "file_size_bytes": int(image["size_bytes"]), "relative_path": image["relative_path"]}
        operation["operation_key"] = operation_key(operation)
        operations.append(operation)
    validate_core_operations(operations)
    return operations


def operation_key(operation):
    stable = {k: v for k, v in operation.items() if k not in {"operation_key", "operation_order"}}
    return sha(canonical(stable))


def operations_fingerprint(operations):
    return sha(canonical(operations))


def validate_core_operations(operations):
    if len(operations) != 68 or [x["operation_order"] for x in operations] != list(range(1, 69)):
        raise ConflictError("El plan reducido debe contener exactamente 68 operaciones continuas")
    if len({x["operation_key"] for x in operations}) != 68:
        raise ConflictError("operation_key duplicada")
    if len({x["approval_key"] for x in operations}) != 34 or len({x["metric_model"] for x in operations}) != 34:
        raise ConflictError("El plan debe derivar 34 approval_key y modelos únicos")
    counts = {kind: sum(x["resource_type"] == kind for x in operations) for kind in ("product", "image")}
    if counts != {"product": 34, "image": 34} or [sum(x["batch"] == b and x["resource_type"] == "product" for x in operations) for b in (1, 2)] != [20, 14]:
        raise ConflictError("El plan debe ser 34+34 en lotes de productos 20+14")
    keys = {x["operation_key"] for x in operations}
    for item in operations:
        if item["operation_key"] != operation_key(item) or item["payload_sha256"] != sha(canonical(item["request_template"])):
            raise ConflictError("Hash recalculable divergente")
        if item["resource_type"] == "image" and item["depends_on_operation_key"] not in keys:
            raise ConflictError("Dependencia de imagen inválida")


def atomic_checkpoint(path, value):
    base.atomic_json(path, value)


def new_checkpoint(origin, source_raw, historical, operations, resources, remote_fp, inputs):
    return {"tool": TOOL_NAME, "version": TOOL_VERSION, "schema": CHECKPOINT_SCHEMA_VERSION,
            "completion_profile": COMPLETION_PROFILE, "human_approval": HUMAN_APPROVAL,
            "state": "core_dry_run_ready", "api_base_url": origin, "input_fingerprints": inputs["fingerprints"],
            "source_checkpoint_sha256": sha(source_raw), "source_checkpoint_size": len(source_raw),
            "source_checkpoint_status": "superseded_by_core_completion", "source_checkpoint_modified": False,
            "full_resume_authorized": False, "partial_resume_fingerprint_sha256": PARTIAL_RESUME_FINGERPRINT,
            "remote_dry_run_fingerprint_sha256": remote_fp, "planned_operations": operations,
            "planned_operations_fingerprint_sha256": operations_fingerprint(operations),
            "operation_keys": [x["operation_key"] for x in operations], "completed_operations": [],
            "resources_created": {"products": [], "images": []}, "resources_historical": historical,
            "batches": [{"batch": 1, "products": 20, "operations": 40}, {"batch": 2, "products": 14, "operations": 28}],
            "external_effects": {"writes": 0, "published": 0}, "errors": [], "next_operation": 1}


def _checkpoint_bytes(path):
    """Read core checkpoints directly; the base reader only recognizes full-import states."""
    if not path.exists():
        raise ConflictError("Checkpoint vacío o inválido: archivo ausente")
    raw = base.regular_bytes(path, "checkpoint")
    if not raw:
        raise ConflictError("Checkpoint vacío o inválido")
    value = base.json_value(raw, "checkpoint")
    if not isinstance(value, dict) or not value:
        raise ConflictError("Checkpoint vacío o inválido")
    if not all(key in value for key in ("tool", "version", "schema", "state", "planned_operations")):
        raise ConflictError("Checkpoint vacío o inválido")
    _secret_free(raw)
    return value, raw


def _validate_checkpoint_content(value):
    if value.get("tool") != TOOL_NAME or value.get("schema") != CHECKPOINT_SCHEMA_VERSION or value.get("completion_profile") != COMPLETION_PROFILE:
        raise ConflictError("Checkpoint reducido incompatible: identidad o schema")
    if value.get("state") not in STATES:
        raise ConflictError("Checkpoint reducido incompatible: estado")
    validate_core_operations(value.get("planned_operations", []))
    if value.get("planned_operations_fingerprint_sha256") != operations_fingerprint(value["planned_operations"]):
        raise ConflictError("Fingerprint del plan reducido divergente")
    if value.get("operation_keys") != [op["operation_key"] for op in value["planned_operations"]]:
        raise ConflictError("Lista operation_key divergente")
    completed = value.get("completed_operations")
    if not isinstance(completed, list) or len({op.get("operation_key") for op in completed}) != len(completed):
        raise ConflictError("Operaciones completadas inválidas o duplicadas")
    planned_keys = value["operation_keys"]
    if [op.get("operation_key") for op in completed] != planned_keys[:len(completed)]:
        raise ConflictError("Operaciones completadas no forman un prefijo canónico")
    return value


def _validate_approved_101(value, raw, *, digest=sha):
    if len(raw) != APPROVED_101_SIZE or digest(raw) != APPROVED_101_SHA256:
        raise ConflictError("Checkpoint 1.0.1 no autorizado: hash o tamaño")
    if (value.get("version") != "1.0.1" or value.get("human_approval") != HUMAN_APPROVAL or
            value.get("state") != "core_dry_run_ready" or value.get("completed_operations") != [] or
            value.get("resources_created") != {"products": [], "images": []} or
            value.get("external_effects") != {"writes": 0, "published": 0} or value.get("errors") != [] or
            value.get("next_operation") != 1 or value.get("source_checkpoint_modified") is not False or
            value.get("full_resume_authorized") is not False or
            value.get("source_checkpoint_sha256") != SOURCE_SHA256 or value.get("source_checkpoint_size") != SOURCE_SIZE or
            value.get("source_checkpoint_status") != "superseded_by_core_completion" or
            value.get("partial_resume_fingerprint_sha256") != PARTIAL_RESUME_FINGERPRINT or
            value.get("planned_operations_fingerprint_sha256") != APPROVED_101_PLAN_FINGERPRINT or
            value.get("remote_dry_run_fingerprint_sha256") != APPROVED_101_REMOTE_FINGERPRINT):
        raise ConflictError("Checkpoint 1.0.1 aprobado semánticamente incompatible")
    return _validate_checkpoint_content(value)


def read_core_checkpoint(path, *, digest=sha):
    value, raw = _checkpoint_bytes(path)
    if value.get("version") == "1.0.1":
        _validate_approved_101(value, raw, digest=digest)
        return value, True
    if value.get("version") != TOOL_VERSION:
        raise ConflictError("Checkpoint reducido incompatible: versión")
    return _validate_checkpoint_content(value), False


def _secret_free(raw):
    text = raw.decode("utf-8", "ignore")
    if re.search(r"(?i)Authorization|Bearer\s+|eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.|password|credential", text):
        raise ConflictError("Secreto potencial detectado en salidas")


def _csv(path, fields, rows):
    base.write_csv(path, fields, rows)


def write_outputs(output: Path, result):
    if output.exists() and (output.is_symlink() or not output.is_dir() or any(output.iterdir())):
        raise ConflictError("output-dir debe estar ausente o completamente vacío")
    output.parent.mkdir(parents=False, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".core-stage-", dir=output.parent))
    try:
        _csv(stage / "core-products.csv", result["product_fields"], result["products"])
        _csv(stage / "core-images.csv", result["image_fields"], result["images"])
        _csv(stage / "core-operations.csv", result["operation_fields"], result["operations"])
        _csv(stage / "core-conflicts.csv", ("code", "metric_model", "message"), result.get("conflicts", []))
        summary = result["summary"]
        (stage / "core-summary.json").write_bytes(canonical(summary) + b"\n")
        files = []
        for name in OUTPUT_NAMES[:5]:
            raw = (stage / name).read_bytes(); files.append({"name": name, "sha256": sha(raw), "size": len(raw)})
        manifest = {"tool": TOOL_NAME, "version": TOOL_VERSION, "completion_profile": COMPLETION_PROFILE,
                    "source_checkpoint_status": "superseded_by_core_completion", "source_checkpoint_modified": False,
                    "full_resume_authorized": False, "files": files}
        (stage / "core-manifest.json").write_bytes(canonical(manifest) + b"\n")
        (stage / "README-core-completion.txt").write_text(
            "Finalización reducida LGMG: 34 productos, 34 imágenes principales y 68 operaciones.\n"
            "Sin publicación, precios, especificaciones, fichas nuevas ni imágenes secundarias.\n", encoding="utf-8", newline="\n")
        for path in stage.iterdir(): _secret_free(path.read_bytes())
        if {p.name for p in stage.iterdir()} != set(OUTPUT_NAMES):
            raise ConflictError("Conjunto de siete salidas incompleto")
        os.replace(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def report_data(data, decisions, operations, checkpoint, mode, writes=0):
    done = {x["operation_key"]: x for x in checkpoint.get("completed_operations", [])}
    historical = {d["row"]["metric_model"] for d in decisions if d["status"] == "already_imported_exact"}
    products, images = [], []
    for d in decisions:
        r, p = d["row"], d.get("product") or {}
        model = r["metric_model"]
        created = next((x for x in checkpoint.get("resources_created", {}).get("products", []) if x.get("metric_model") == model), {})
        status = "historical_existing" if model in historical else "created_by_core_completion" if created else "planned_create"
        products.append({"source_order": r["source_order"], "source_key": r["source_key"], "approval_key": r["approval_key"],
            "metric_model": model, "approved_name": r["approved_name"], "family": r["approved_family"],
            "category_id": d["payload"]["category"], "brand_id": d["payload"]["brand"],
            "remote_product_id": p.get("id", created.get("id", "")),
            "technical_sheet_action": "reuse_historical" if model == PARTIAL_MODEL else "none",
            "primary_image_action": "preserve" if model in historical else "upload_one",
            "core_status": status, "is_published": False, "price_visible": False, "warnings": ""})
        images.append({"source_order": r["source_order"], "source_key": r["source_key"], "approval_key": r["approval_key"],
                       "metric_model": model, "is_primary": True,
                       "core_status": "historical_existing" if model in historical else "planned_upload"})
    op_rows = [{**op, "request_template": json.dumps(op["request_template"], ensure_ascii=False, sort_keys=True),
                "status": "completed" if op["operation_key"] in done else "planned"} for op in operations]
    summary = {"verdict": mode, "source_checkpoint_status": "superseded_by_core_completion",
        "source_checkpoint_modified": False, "full_resume_authorized": False,
        "historical_resources": checkpoint["resources_historical"], "resources_created_by_core_completion": checkpoint["resources_created"],
        "previous_cumulative_effects": 65, "invocation_effects": {"writes": writes},
        "products": {"approved": 36, "historical_existing": 2, "create_candidates": 34},
        "images": {"historical_existing": 2, "primary_planned": 34}, "total_operations": 68,
        "datasheets_omitted": 30, "specifications_omitted": 999, "secondary_images_omitted": True,
        "publication_disabled": True, "prices_visible": 0}
    return {"product_fields": tuple(products[0]), "products": products, "image_fields": tuple(images[0]), "images": images,
            "operation_fields": tuple(op_rows[0]), "operations": op_rows, "conflicts": [], "summary": summary}


def run(plan, audit, repaired, source_checkpoint, output, origin, checkpoint, mode, token,
        resume=False, confirm_apply=None, confirm_rollback=None, client_factory=ApiClient):
    origin = normalize_origin(origin)
    if source_checkpoint.resolve() == checkpoint.resolve():
        raise ConflictError("--checkpoint nuevo debe diferir de --source-checkpoint")
    source, source_raw, historical = validate_source_checkpoint(source_checkpoint)
    before = (sha(source_raw), source_checkpoint.stat().st_size, source_checkpoint.stat().st_mtime_ns)
    data = base.validate_inputs(plan, audit, repaired)
    cp, migrate_101 = read_core_checkpoint(checkpoint) if mode != "dry_run" else (None, False)
    client = client_factory(origin, token, mode)
    state = base.snapshot(client); _, categories, brand = base.resolve_taxonomy(state)
    def validate_sheet(sheet_id, name, digest, size):
        exact_partial_ids = {
            d["product"].get("id") for d in decisions
            if d["row"]["metric_model"] == PARTIAL_MODEL and d["status"] == "already_imported_exact"
            and isinstance(d.get("product"), dict) and d["product"].get("id") is not None
        }
        return validate_historical_sheet(state["sheets"], sheet_id, name, digest, size, exact_partial_ids)
    decisions = base.classify_products(data, state, categories, brand)
    conflicts = [d for d in decisions if d["status"] == "conflict_existing_product"]
    exact_models = {d["row"]["metric_model"] for d in decisions if d["status"] == "already_imported_exact"}
    if len(decisions) != 36 or conflicts or not HISTORICAL_MODELS <= exact_models:
        raise ConflictError("CONFLICT: identidad remota incompatible con la cohorte cerrada")
    validate_sheet(historical["partial_sheet_id"], PARTIAL_SHEET_NAME, PARTIAL_SHEET_SHA256, PARTIAL_SHEET_SIZE)
    if mode == "dry_run":
        decisions, computed = derive_core(data, state, categories, brand, historical, validate_sheet)
        if checkpoint.exists(): raise ConflictError("Dry-run exige checkpoint nuevo ausente")
        cp = new_checkpoint(origin, source_raw, historical, computed, base.resource_view(_, categories, brand), base.remote_fingerprint(state), data)
        atomic_checkpoint(checkpoint, cp); verdict = "CORE_DRY_RUN_READY"; writes = 0
    else:
        planned_models = {x["metric_model"] for x in cp["planned_operations"]}
        if planned_models | HISTORICAL_MODELS != {d["row"]["metric_model"] for d in decisions}:
            raise ConflictError("Checkpoint reducido no cubre exactamente los 34 modelos restantes")
        if exact_models != HISTORICAL_MODELS or sum(d["status"] == "create_candidate" for d in decisions) != 34:
            raise ConflictError("El snapshot remoto debe conservar 2 históricos, 34 ausentes y cero conflictos")
        if cp["api_base_url"] != origin or cp["source_checkpoint_sha256"] != sha(source_raw):
            raise ConflictError("Apply/verify no coincide criptográficamente con dry-run")
        # El plan persistido es canónico: aquí solo se validan sus medios, nunca se reconstruye.
        for op in cp["planned_operations"]:
            if op["resource_type"] == "image":
                image = next((x for x in data["images"].get(op["metric_model"], []) if x["sha256"] == op["file_sha256"]), None)
                if image is None: raise ConflictError("Imagen persistida no coincide con inputs")
                base._validate_local_media(repaired, image, "image")
        if mode == "verify":
            verdict = "CORE_DRY_RUN_STILL_READY" if cp["state"] == "core_dry_run_ready" else "CORE_IMPORT_VERIFIED"
            writes = 0
        elif mode == "apply":
            if confirm_apply != APPLY_CONFIRMATION: raise ConflictError("Confirmación exacta de apply ausente")
            if (resume and cp["state"] != "core_apply_partial") or (not resume and cp["state"] != "core_dry_run_ready"):
                raise ConflictError("Estado o --resume incompatible con apply")
            if not resume and (cp["completed_operations"] or cp["resources_created"] != {"products": [], "images": []} or
                               cp.get("external_effects") != {"writes": 0, "published": 0} or cp.get("next_operation") != 1):
                raise ConflictError("Apply inicial exige cero operaciones y efectos previos")
            if migrate_101:
                cp["migrated_from"] = {"version": "1.0.1", "sha256": APPROVED_101_SHA256,
                                       "size_bytes": APPROVED_101_SIZE, "approved": True}
                cp["version"] = TOOL_VERSION
            cp["state"] = "core_apply_in_progress"; atomic_checkpoint(checkpoint, cp); writes = 0
            done = {x["operation_key"] for x in cp["completed_operations"]}
            try:
                for op in cp["planned_operations"]:
                    if op["operation_key"] in done: continue
                    if op["resource_type"] == "product": made = client.post(op["path_template"], op["request_template"])
                    else:
                        image = next(x for x in data["images"][op["metric_model"]] if x["sha256"] == op["file_sha256"])
                        path, raw = base._validate_local_media(repaired, image, "image")
                        product_id = next(x["id"] for x in cp["resources_created"]["products"] if x["metric_model"] == op["metric_model"])
                        body, mime = base._multipart_image(product_id, image, path.name, raw)
                        made = client.request("POST", op["path_template"], body, content_type=mime)
                    record = {"operation_key": op["operation_key"], "operation_order": op["operation_order"], "resource_type": op["resource_type"], "resource_id": made["id"], "metric_model": op["metric_model"]}
                    cp["completed_operations"].append(record); cp["resources_created"][op["resource_type"] + "s"].append({"id": made["id"], "metric_model": op["metric_model"]})
                    writes += 1; cp["external_effects"]["writes"] += 1; cp["next_operation"] = op["operation_order"] + 1; atomic_checkpoint(checkpoint, cp)
                final = base.snapshot(client); _, fc, fb = base.resolve_taxonomy(final)
                fd = base.classify_products(data, final, fc, fb)
                if len(fd) != 36 or any(x["status"] != "already_imported_exact" for x in fd): raise ControlledImportError("Verificación final 36/36 incompleta")
                cp["state"] = "core_apply_complete"; atomic_checkpoint(checkpoint, cp); verdict = "CORE_APPLY_COMPLETE"
            except Exception:
                cp["state"] = "core_apply_partial"; atomic_checkpoint(checkpoint, cp); raise
        else:
            if confirm_rollback != ROLLBACK_CONFIRMATION: raise ConflictError("Confirmación exacta de rollback ausente")
            if cp["state"] not in {"core_apply_partial", "core_apply_complete", "core_rollback_in_progress"}:
                raise ConflictError("Estado incompatible con rollback reducido")
            if resume and cp["state"] != "core_rollback_in_progress": raise ConflictError("--rollback --resume exige rollback parcial")
            cp["state"] = "core_rollback_in_progress"; atomic_checkpoint(checkpoint, cp); writes = 0
            for kind, endpoint in (("images", "product-images"), ("products", "products")):
                for resource in reversed(cp["resources_created"][kind]):
                    if resource.get("rollback_completed"): continue
                    client.delete(f"/api/{endpoint}/{int(resource['id'])}"); resource["rollback_completed"] = True; writes += 1; atomic_checkpoint(checkpoint, cp)
            cp["state"] = "core_rollback_complete"; atomic_checkpoint(checkpoint, cp); verdict = "CORE_ROLLBACK_COMPLETE"
    if (sha(base.regular_bytes(source_checkpoint, "source-checkpoint")), source_checkpoint.stat().st_size, source_checkpoint.stat().st_mtime_ns) != before:
        raise ConflictError("El source checkpoint fue modificado durante la ejecución")
    write_outputs(output, report_data(data, decisions, cp["planned_operations"], cp, verdict, writes))
    print(verdict)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Finalización reducida de 34 productos LGMG con una imagen principal")
    for name in ("plan-input", "remaining-audit-input", "repaired-media-input", "source-checkpoint", "output-dir", "api-base-url", "checkpoint"):
        parser.add_argument("--" + name, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("dry-run", "apply", "verify", "rollback"): modes.add_argument("--" + name, action="store_true")
    parser.add_argument("--resume", action="store_true"); parser.add_argument("--confirm-apply"); parser.add_argument("--confirm-rollback")
    return parser


def validate_cli(args):
    mode = next(x for x in ("dry_run", "apply", "verify", "rollback") if getattr(args, x))
    if args.resume and mode not in {"apply", "rollback"}: raise ConflictError("--resume solo puede utilizarse con --apply o --rollback")
    if mode == "apply" and args.confirm_apply != APPLY_CONFIRMATION: raise ConflictError("Confirmación exacta de apply ausente")
    if mode == "rollback" and args.confirm_rollback != ROLLBACK_CONFIRMATION: raise ConflictError("Confirmación exacta de rollback ausente")
    if mode in {"dry_run", "verify"} and (args.confirm_apply is not None or args.confirm_rollback is not None): raise ConflictError("Modo de lectura no acepta confirmaciones")
    if (mode == "apply" and args.confirm_rollback is not None) or (mode == "rollback" and args.confirm_apply is not None): raise ConflictError("Confirmación incompatible")
    return mode


def main(argv=None):
    try:
        args = build_parser().parse_args(argv); mode = validate_cli(args); token = access_token()
        return run(Path(args.plan_input), Path(args.remaining_audit_input), Path(args.repaired_media_input), Path(args.source_checkpoint),
                   Path(args.output_dir), args.api_base_url, Path(args.checkpoint), mode, token, args.resume, args.confirm_apply, args.confirm_rollback)
    except ConflictError as exc:
        print("CONFLICT: " + str(exc)[:240], file=sys.stderr); return 3
    except (ControlledImportError, OSError) as exc:
        print("Error operativo seguro: " + str(exc)[:240], file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
