#!/usr/bin/env python3
"""Importador completo, cerrado y reversible de los 36 productos LGMG restantes."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

TOOL_NAME = "import_lgmg_remaining_controlled"
TOOL_VERSION = "2.1.1"
CHECKPOINT_SCHEMA_VERSION = "2.1"
OPERATION_CONTRACT_VERSION = "2.1"
SUPERSEDED_DRY_RUN_FINGERPRINTS = {
    "85bb67b06624bbbb5b7a8d102c00faa776884c9a394eaf62cd8be3e7f9e72553": "superseded_incomplete_dry_run",
    "bda45b2889f54055332a529df141fc6abfcfa5f3e9cfe04320d5313b991cbd31": "superseded_unauditable_specification_dry_run",
}
SUPERSEDED_INCOMPLETE_DRY_RUN_FINGERPRINT_SHA256 = next(iter(SUPERSEDED_DRY_RUN_FINGERPRINTS))
# Los endpoints de catálogo aceptan slugs de categoría/marca como filtros. Por ello
# una taxonomía no canónica es funcionalmente observable y bloquea un plan nuevo.
CATEGORY_SLUG_POLICY = "blocking_functional_filter"
CATEGORY_CONTRACT = {
    "Elevadores tipo tijera todoterreno": "elevadores-tipo-tijera-todoterreno",
    "Elevadores tipo brazo articulado": "elevadores-tipo-brazo-articulado",
    "Elevadores tipo brazo telescópico": "elevadores-tipo-brazo-telescopico",
    "Elevadores tipo mástil vertical": "elevadores-tipo-mastil-vertical",
    "Elevadores tipo tijera sobre orugas": "elevadores-tipo-tijera-sobre-orugas",
    "Manipuladores telescópicos": "manipuladores-telescopicos",
}
ROOT_CATEGORY_CONTRACT = {"name": "Maquinaria", "slug": "maquinaria", "parent": None,
                          "product_type": "machinery", "is_active": True}
CHECKPOINT_STATES = {"dry_run_ready", "apply_in_progress", "apply_partial", "apply_complete",
                     "verify_complete", "rollback_in_progress", "rollback_complete"}
TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
APPLY_CONFIRMATION = "IMPORTAR_36_LGMG_RESTANTES"
ROLLBACK_CONFIRMATION = "REVERTIR_IMPORTACION_36_LGMG_RESTANTES"
MAX_DATASHEET_BYTES = 10_485_760
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 100
APPROVED_FINGERPRINTS = {
    "approved_plan_fingerprint": "75d68378dcd7bf77b19f9c7f0e60806085deaecadf2b7fa70e3102812be4bcb7",
    "approved_media_fingerprint": "b16d7f40250cc9b7a1b4affe029d0a87bba4355968e289fdab99ddbb4d656c9b",
    "remaining_catalog_fingerprint_sha256": "62230925212e866c59197a03975bb5707d40ef416b05bb071de84e43cef7ea39",
    "remaining_audit_input_fingerprint_sha256": "d2b46313a8b9219793c6f9541e383b8eef47f6d1b2f76dbf7bf7bbd984371665",
    "decisions_input_sha256": "280811cc376c2aa480511fcfa6923e120973e252016efb74e3b89e318130d779",
    "repaired_media_fingerprint_sha256": "f9c18b7000a93d37e69e306960da8f3e237e4cc2bbf1122f892053566c01b157",
}
FAMILIES = (
    "Elevadores tipo tijera todoterreno", "Elevadores tipo brazo articulado",
    "Elevadores tipo brazo telescópico", "Elevadores tipo mástil vertical",
    "Elevadores tipo tijera sobre orugas", "Manipuladores telescópicos",
)
OUTPUT_NAMES = (
    "remaining-import-summary.json", "remaining-import-summary.txt",
    "remaining-import-products.csv", "remaining-import-media.csv",
    "remaining-import-operations.csv", "remaining-import-conflicts.csv",
    "remaining-import-manifest.json", "README-remaining-import.txt",
)
VERDICTS = {"DRY_RUN_READY", "APPLY_COMPLETE", "APPLY_PARTIAL", "VERIFY_COMPLETE", "ROLLBACK_COMPLETE", "CONFLICT"}
POWER_ENUM = {"electric_24v", "electric_lithium"}
READ_ENDPOINTS = (
    "/api/auth/me", "/api/categories?include_inactive=true", "/api/brands?include_inactive=true",
    "/api/products?include_unpublished=true", "/api/product-images", "/api/product-specs", "/api/technical-sheets",
)
SPECIFICATION_COLUMNS = (
    "source_key", "metric_model", "group_order", "group_name", "specification_order",
    "source_label", "source_value", "normalized_label", "normalized_value", "unit",
    "requires_review", "maximum_load_capacity_candidate_kg",
)


class ControlledImportError(ValueError):
    """Fallo seguro que no incorpora cuerpos HTTP ni credenciales."""


class ConflictError(ControlledImportError):
    """Estado que impide continuar de forma segura."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def truth(value) -> bool:
    return value is True or str(value).casefold() == "true"


def nested_id(value):
    return value.get("id") if isinstance(value, dict) else value


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or re.match(r"^[A-Za-z]:", value) or any(ord(c) < 32 for c in value):
        raise ConflictError("Ruta relativa insegura")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or any(p in ("", ".", "..") for p in pure.parts):
        raise ConflictError("Ruta relativa no canónica o traversal")
    return value


def regular_bytes(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ConflictError(f"Archivo obligatorio ausente: {label}") from exc
    if path.is_symlink() or not stat.S_ISREG(mode):
        raise ConflictError(f"Archivo inseguro o especial: {label}")
    return path.read_bytes()


def csv_rows(data: bytes, label: str):
    try:
        return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except (UnicodeError, csv.Error) as exc:
        raise ConflictError(f"CSV inválido: {label}") from exc


def specification_csv_rows(data: bytes):
    """Carga el contrato cerrado aprobado de import-specifications.csv."""
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        if tuple(reader.fieldnames or ()) != SPECIFICATION_COLUMNS:
            raise ConflictError("Encabezado cerrado inválido: import-specifications.csv")
        return list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ConflictError("CSV inválido: import-specifications.csv") from exc


def json_value(data: bytes, label: str):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConflictError(f"JSON inválido: {label}") from exc


def _physical_dir(path: Path, label: str):
    if path.is_symlink() or not path.is_dir():
        raise ConflictError(f"{label} debe ser un directorio físico")
    current = path.absolute()
    while current != current.parent:
        if current.is_symlink():
            raise ConflictError(f"{label} atraviesa un symlink")
        current = current.parent


def validate_paths(plan: Path, audit: Path, repaired: Path, output: Path, checkpoint: Path | None, resume=False):
    for path, label in ((plan, "plan-input"), (audit, "remaining-audit-input"), (repaired, "repaired-media-input")):
        _physical_dir(path, label)
    roots = [p.resolve() for p in (plan, audit, repaired)] + [output.resolve(strict=False)]
    if len(set(roots)) != 4 or any(a in b.parents or b in a.parents for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise ConflictError("Las entradas y la salida no pueden solaparse")
    _physical_dir(output.parent, "padre de output-dir")
    if output.exists() and (output.is_symlink() or not output.is_dir() or any(output.iterdir())):
        raise ConflictError("output-dir debe estar ausente o completamente vacío")
    if checkpoint:
        _physical_dir(checkpoint.parent, "padre de checkpoint")
        cp = checkpoint.resolve(strict=False)
        if any(cp == root or cp in root.parents for root in roots[:3]) or checkpoint.is_symlink():
            raise ConflictError("checkpoint inseguro o dentro de una entrada")
        if resume and not checkpoint.is_file():
            raise ConflictError("--resume exige un checkpoint regular existente")
        if not resume and checkpoint.exists():
            raise ConflictError("El checkpoint ya existe; use --resume")


def _closed_files(root: Path):
    result = set()
    for item in root.rglob("*"):
        if item.is_symlink() or (not item.is_file() and not item.is_dir()):
            raise ConflictError("Paquete contiene symlink o tipo especial")
        if item.is_file():
            result.add(item.relative_to(root).as_posix())
    return result


def _load_closed_pairs(tool_dir=None):
    path = (tool_dir or Path(__file__).parent) / "import_lgmg_scissors_minimal.py"
    tree = ast.parse(regular_bytes(path, path.name).decode("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL_SOURCE_KEYS" for t in node.targets):
            pairs = tuple(ast.literal_eval(node.value))
            if len(pairs) == len(set(pairs)) == 21:
                return pairs
    raise ConflictError("MODEL_SOURCE_KEYS contractual inválido")


def _manifest_files(root, manifest, ignored_manifest):
    declared = {x.get("name"): x for x in manifest.get("output_files", manifest.get("generated_files", [])) if isinstance(x, dict)}
    for name, item in declared.items():
        path = root.joinpath(*PurePosixPath(safe_relative(name)).parts)
        data = regular_bytes(path, name)
        if item.get("sha256") != sha(data) or item.get("size") != len(data):
            raise ConflictError(f"Hash o tamaño inconsistente: {name}")
    actual = _closed_files(root)
    if actual != set(declared) | {ignored_manifest}:
        raise ConflictError("Conjunto cerrado de archivos inconsistente")
    return declared


def validate_inputs(plan_root: Path, audit_root: Path, repaired_root: Path, *, tool_dir=None):
    pm_raw = regular_bytes(plan_root / "import-manifest.json", "import-manifest.json")
    pm = json_value(pm_raw, "import-manifest.json")
    if pm.get("combined_fingerprint_sha256") != APPROVED_FINGERPRINTS["approved_plan_fingerprint"]:
        raise ConflictError("Fingerprint del plan no aprobado")
    plan_files = {x.get("name"): x for x in pm.get("generated_files", []) if isinstance(x, dict)}
    if "import-products.csv" not in plan_files or "import-specifications.csv" not in plan_files:
        raise ConflictError("Plan incompleto")
    for name, item in plan_files.items():
        data = regular_bytes(plan_root.joinpath(*PurePosixPath(safe_relative(name)).parts), name)
        if sha(data) != item.get("sha256") or len(data) != item.get("size"):
            raise ConflictError(f"Plan alterado: {name}")
    if _closed_files(plan_root) != set(plan_files) | {"import-manifest.json"}:
        raise ConflictError("Conjunto cerrado del plan alterado")
    products = csv_rows(regular_bytes(plan_root / "import-products.csv", "import-products.csv"), "import-products.csv")
    specs = specification_csv_rows(regular_bytes(plan_root / "import-specifications.csv", "import-specifications.csv"))
    if len(products) != 57:
        raise ConflictError("El plan debe contener 57 productos")

    am_raw = regular_bytes(audit_root / "remaining-manifest.json", "remaining-manifest.json")
    am = json_value(am_raw, "remaining-manifest.json")
    checks = {
        "approved_plan_fingerprint": APPROVED_FINGERPRINTS["approved_plan_fingerprint"],
        "approved_media_fingerprint": APPROVED_FINGERPRINTS["approved_media_fingerprint"],
        "remaining_catalog_fingerprint_sha256": APPROVED_FINGERPRINTS["remaining_catalog_fingerprint_sha256"],
    }
    if any(am.get(k) != v for k, v in checks.items()) or am.get("remaining_products") != 36 or am.get("processed_closed_cohort") != 21:
        raise ConflictError("Auditoría restante no aprobada")
    _manifest_files(audit_root, am, "remaining-manifest.json")
    audit_products = csv_rows(regular_bytes(audit_root / "remaining-products-for-approval.csv", "remaining-products-for-approval.csv"), "remaining-products-for-approval.csv")

    rm_raw = regular_bytes(repaired_root / "repair-manifest.json", "repair-manifest.json")
    rm = json_value(rm_raw, "repair-manifest.json")
    if any(rm.get(k) != v for k, v in APPROVED_FINGERPRINTS.items()) or rm.get("verdict") != "REPAIR_COMPLETE":
        raise ConflictError("Fingerprint o veredicto del paquete reparado no aprobado")
    if rm.get("remaining_audit_input_fingerprint_sha256") != APPROVED_FINGERPRINTS["remaining_audit_input_fingerprint_sha256"]:
        raise ConflictError("Fingerprint de entrada de auditoría no aprobado")
    _manifest_files(repaired_root, rm, "repair-manifest.json")
    readiness = csv_rows(regular_bytes(repaired_root / "controlled-import-readiness.csv", "controlled-import-readiness.csv"), "controlled-import-readiness.csv")
    images = csv_rows(regular_bytes(repaired_root / "repair-images.csv", "repair-images.csv"), "repair-images.csv")
    sheets = csv_rows(regular_bytes(repaired_root / "repair-datasheets.csv", "repair-datasheets.csv"), "repair-datasheets.csv")
    summary = json_value(regular_bytes(repaired_root / "repair-summary.json", "repair-summary.json"), "repair-summary.json")
    conflicts = csv_rows(regular_bytes(repaired_root / "repair-conflicts.csv", "repair-conflicts.csv"), "repair-conflicts.csv")
    if summary.get("human_review_required") is not False or summary.get("ready_for_controlled_import") != 36 or conflicts:
        raise ConflictError("Paquete reparado requiere revisión o contiene conflictos")

    closed = set(_load_closed_pairs(tool_dir))
    plan_by_key = {r.get("source_key"): r for r in products}
    audit_by_model = {r.get("metric_model"): r for r in audit_products}
    if len(readiness) != 36 or len(plan_by_key) != 57 or len(audit_by_model) != 36:
        raise ConflictError("Conteos 57/21/36 incumplidos")
    cohort = []
    approval_keys = set()
    for order, ready in enumerate(readiness, 1):
        model = ready.get("metric_model", "")
        approved = audit_by_model.get(model)
        if not approved or not truth(ready.get("ready_for_controlled_import")) or ready.get("approval_key") != approved.get("approval_key"):
            raise ConflictError("Readiness no coincide con aprobación")
        source_key = approved.get("source_key", "")
        plan_row = plan_by_key.get(source_key)
        identity = (model, source_key)
        if not plan_row or plan_row.get("metric_model") != model or identity in closed:
            raise ConflictError("Identidad source_key + metric_model invade la cohorte cerrada")
        key = ready.get("approval_key", "")
        if not key or key in approval_keys:
            raise ConflictError("approval_key vacío o duplicado")
        approval_keys.add(key)
        family, name = ready.get("approved_family"), ready.get("approved_name")
        if family not in FAMILIES or family != approved.get("proposed_target_subcategory") or name != approved.get("proposed_target_name"):
            raise ConflictError("Familia o nombre aprobado alterado")
        if not name.endswith(" " + model):
            raise ConflictError("Nombre no conserva el modelo literal")
        cohort.append({**plan_row, **approved, **ready, "source_order": order, "source_key": source_key,
                       "metric_model": model, "approved_name": name, "approved_family": family})
    if len(cohort) != 36 or len(approval_keys) != 36 or {r["approved_family"] for r in cohort} != set(FAMILIES):
        raise ConflictError("La cohorte debe contener 36 approval_key y seis familias")

    image_by = {r["metric_model"]: [] for r in cohort}
    for row in images:
        if row.get("metric_model") in image_by:
            image_by[row["metric_model"]].append(row)
    for model, rows in image_by.items():
        rows.sort(key=lambda r: int(r.get("association_order", 0)))
        if not rows or len([r for r in rows if truth(r.get("is_primary"))]) != 1 or not truth(rows[0].get("is_primary")):
            raise ConflictError(f"Imagen principal inválida para {model}")
        for row in rows:
            _validate_local_media(repaired_root, row, "image")
    expected_special = {
        "A13JE": ["21b8e8bbb8d2b40617b01fd86aee1c8c30025e742f90cc8f4229eaea264744ce", "3fc3777d98efadbd36a4cc31fde58887a476e92f1b163250011128ad02f946f4"],
        "A14JE": ["e3e568efc55d1f9dcadc9bdd76f80a2ec1a6fe7d88df776cc3c5b8c1b16fe9de", "b95ee211b2a20be84372f88bfb828be596fe4fce6618b4e32f0dd6dfa9a13541", "acb85d1fbe203d02ef7f1af42ef0e00d6f43cb643be952b8c65c85c572c9ab41"],
    }
    for model, hashes in expected_special.items():
        if [r.get("sha256") for r in image_by[model]] != hashes:
            raise ConflictError(f"Asociaciones aprobadas alteradas para {model}")

    sheet_by = {}
    for row in sheets:
        model = row.get("metric_model")
        if model in sheet_by:
            raise ConflictError("Ficha duplicada")
        sheet_by[model] = row
        allowed = truth(row.get("datasheet_upload_allowed")) and truth(row.get("backend_size_compatible"))
        if allowed:
            _validate_local_media(repaired_root, row, "datasheet")
    if set(sheet_by) != {r["metric_model"] for r in cohort}:
        raise ConflictError("Debe existir una fila de ficha por producto")
    for model in ("AR24JE", "T38JE", "H625E"):
        if truth(sheet_by[model].get("datasheet_upload_allowed")):
            raise ConflictError(f"{model} debe importarse sin ficha")
    for model in ("SR1018E-2", "T28JE"):
        if sheet_by[model].get("corrected_status") != "validated_replacement" or not truth(sheet_by[model].get("datasheet_upload_allowed")):
            raise ConflictError(f"Reemplazo no validado para {model}")

    specs_by = {r["source_key"]: [] for r in cohort}
    for row in specs:
        if row.get("source_key") in specs_by:
            specs_by[row["source_key"]].append(row)
    if sum(len(rows) for rows in specs_by.values()) != 1057:
        raise ConflictError("Las 36 filas aprobadas deben derivar exactamente 1.057 especificaciones")
    return {"products": cohort, "specs": specs_by, "images": image_by, "sheets": sheet_by,
            "fingerprints": dict(APPROVED_FINGERPRINTS)}


def _validate_local_media(root: Path, row, kind):
    relative = row.get("relative_path") if kind == "image" else row.get("corrected_relative_path")
    path = root.joinpath(*PurePosixPath(safe_relative(relative)).parts)
    data = regular_bytes(path, relative)
    digest = row.get("sha256") if kind == "image" else row.get("corrected_sha256")
    size = row.get("size_bytes") if kind == "image" else row.get("corrected_size_bytes")
    mime = row.get("mime", "").casefold()
    if sha(data) != digest or str(len(data)) != str(size) or not data:
        raise ConflictError("Hash o tamaño físico de medio inválido")
    if kind == "datasheet":
        if len(data) > MAX_DATASHEET_BYTES or mime != "application/pdf" or not data.startswith(b"%PDF-"):
            raise ConflictError("Ficha incompatible con límite, MIME o firma")
    else:
        if len(data) > MAX_IMAGE_BYTES or not row.get("width", "").isdigit() or not row.get("height", "").isdigit():
            raise ConflictError("Imagen sin dimensiones válidas")
        valid = ((mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff")) or
                 (mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                 (mime == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
        if not valid:
            raise ConflictError("MIME o firma de imagen inválidos")
    return path, data


def normalize_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/") or not parsed.hostname:
        raise ConflictError("--api-base-url debe ser un origen sin credenciales, ruta, query ni fragmento")
    host = parsed.hostname.casefold()
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ConflictError("La API real exige HTTPS; HTTP se admite solo en loopback para pruebas")
    port = f":{parsed.port}" if parsed.port else ""
    shown_host = f"[{host}]" if ":" in host else host
    return f"{parsed.scheme}://{shown_host}{port}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(request.full_url), urllib.parse.urlsplit(newurl)
        if (old.scheme, old.hostname, old.port) != (new.scheme, new.hostname, new.port):
            raise ControlledImportError("Redirección a otro origen rechazada")
        raise ControlledImportError("Redirección HTTP rechazada")


class ApiClient:
    def __init__(self, origin, token, mode, opener=None):
        self.origin, self._token, self.mode = normalize_origin(origin), token, mode
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.operations = []

    def request(self, method, path, payload=None, *, content_type="application/json", accept="application/json"):
        mutating = method in {"POST", "PATCH", "PUT", "DELETE"}
        if mutating and self.mode not in {"apply", "rollback"}:
            raise ControlledImportError("Solicitud mutadora prohibida en modo de lectura")
        if not path.startswith("/api/") or "//" in path or ".." in path:
            raise ControlledImportError("Ruta API no permitida")
        data = None if payload is None else (payload if isinstance(payload, bytes) else canonical(payload))
        headers = {"Accept": accept, "Authorization": "Bearer " + self._token}
        if data is not None:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.origin + path, data=data, headers=headers, method=method)
        self.operations.append({"method": method, "path": path})
        try:
            response = self.opener.open(request, timeout=20)
            if normalize_origin(response.geturl().split("/api/", 1)[0]) != self.origin:
                raise ControlledImportError("Cambio de origen rechazado")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ControlledImportError("Respuesta API excede el límite")
            actual = response.headers.get_content_type()
            if accept == "application/json" and actual != "application/json":
                raise ControlledImportError("Content-Type JSON inesperado")
            return json.loads(raw.decode("utf-8")) if accept == "application/json" else raw
        except urllib.error.HTTPError as exc:
            raise ControlledImportError(f"HTTP {exc.code} en {method} {path}") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, UnicodeError, json.JSONDecodeError) as exc:
            raise ControlledImportError(f"Fallo API seguro en {method} {path}: {type(exc).__name__}") from None

    def get(self, path): return self.request("GET", path)
    def post(self, path, payload): return self.request("POST", path, payload)
    def patch(self, path, payload): return self.request("PATCH", path, payload)
    def delete(self, path): return self.request("DELETE", path)


def extract_page(value, label):
    if isinstance(value, list):
        return value, None
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return value["results"], value.get("next")
    raise ControlledImportError(f"Paginación inválida para {label}")


def paginated(client, path):
    results, seen = [], set()
    for _ in range(MAX_PAGES):
        if path in seen:
            raise ControlledImportError("Ciclo de paginación detectado")
        seen.add(path)
        items, following = extract_page(client.get(path), path)
        if not all(isinstance(x, dict) for x in items):
            raise ControlledImportError("Elemento paginado inválido")
        results.extend(items)
        if not following:
            return results
        parsed = urllib.parse.urlsplit(following)
        if parsed.scheme:
            if normalize_origin(f"{parsed.scheme}://{parsed.netloc}") != client.origin:
                raise ControlledImportError("Paginación cambia de origen")
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
        else:
            path = following
        if not path.startswith("/api/"):
            raise ControlledImportError("next paginado inválido")
    raise ControlledImportError("Paginación excede el límite")


def snapshot(client):
    me = client.get("/api/auth/me")
    if not isinstance(me, dict) or not me.get("id"):
        raise ConflictError("Identidad autenticada inválida")
    return {"identity": {"id": me["id"]},
            "categories": paginated(client, READ_ENDPOINTS[1]), "brands": paginated(client, READ_ENDPOINTS[2]),
            "products": paginated(client, READ_ENDPOINTS[3]), "images": paginated(client, READ_ENDPOINTS[4]),
            "specs": paginated(client, READ_ENDPOINTS[5]), "sheets": paginated(client, READ_ENDPOINTS[6])}


def resolve_taxonomy(state):
    roots = [x for x in state["categories"] if x.get("name") == "Maquinaria" and x.get("product_type") == "machinery" and x.get("parent") is None and x.get("is_active") is True]
    if len(roots) != 1:
        raise ConflictError("Debe existir una única raíz activa Maquinaria")
    root = roots[0]
    if root.get("slug") != ROOT_CATEGORY_CONTRACT["slug"]:
        raise ConflictError("category_slug_mismatch: Maquinaria")
    categories = {}
    for family in FAMILIES:
        hits = [x for x in state["categories"] if x.get("name") == family]
        if len(hits) != 1 or nested_id(hits[0].get("parent")) != root.get("id") or hits[0].get("product_type") != "machinery" or hits[0].get("is_active") is not True:
            raise ConflictError(f"Subcategoría ausente, duplicada o con jerarquía incorrecta: {family}")
        if hits[0].get("slug") != CATEGORY_CONTRACT[family]:
            raise ConflictError(f"category_slug_mismatch: {family}")
        categories[family] = hits[0]
    brands = [x for x in state["brands"] if x.get("name") == "LGMG" and x.get("is_active") is True]
    if len(brands) != 1:
        raise ConflictError("Debe existir una única marca activa exacta LGMG")
    return root, categories, brands[0]


def _decimal(value, minimum=Decimal("0.01"), maximum=Decimal("1000000")):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return float(number) if number.is_finite() and minimum <= number <= maximum else None


def product_payload(row, category_id, brand_id):
    capacity = _decimal(row.get("maximum_load_capacity_kg"))
    power = row.get("target_power_source") if row.get("target_power_source") in POWER_ENUM else None
    return {
        "name": row["approved_name"], "category": category_id, "brand": brand_id,
        "supplier": None, "technical_sheet": None, "product_type": "machinery", "condition": "new",
        "short_description": row.get("short_description") or "", "description": row.get("description") or "",
        "model": row["metric_model"], "sku": None, "working_height_m": None, "terrain_type": None,
        "year": None, "hours_meter": None, "maximum_load_capacity_kg": capacity, "machine_weight_kg": None,
        "power_source": power, "includes_technical_review": False,
        "includes_commercial_technical_advice": False, "includes_coordinated_delivery": False,
        "price": None, "price_currency": None, "price_tax_mode": None, "price_visible": False,
        "stock_status": row.get("stock_status") or "on_request", "is_featured": False, "is_published": False,
    }


def spec_payload(row, product_id):
    spec = specification_identity(row)
    return {"product": product_id, "name": spec["name"], "key": spec["key"],
            "value": spec["value"], "unit": spec["unit"], "order": spec["order"]}


def specification_identity(row):
    """Adapta una fila aprobada al ProductSpecWriteDto sin perder Unicode.

    El plan no representa una clave de DTO: `key` conserva el contrato vacío. Los
    campos normalizados, cuando existen, tienen precedencia; sus vacíos vuelven a
    la evidencia fuente. El orden procede exclusivamente de specification_order.
    """
    missing = [field for field in SPECIFICATION_COLUMNS if field not in row]
    unexpected = [field for field in row if field not in SPECIFICATION_COLUMNS]
    if missing or unexpected:
        raise ConflictError("Fila de especificación no cumple el esquema aprobado")
    name = row["normalized_label"] or row["source_label"]
    value = row["normalized_value"] or row["source_value"]
    try:
        order = int(row["specification_order"])
    except (TypeError, ValueError) as exc:
        raise ConflictError("specification_order inválido") from exc
    if not name or not value:
        raise ConflictError("Nombre o valor efectivo de especificación vacío")
    return {"name": name, "key": "", "value": value, "unit": row["unit"], "order": order}


def classify_products(data, state, categories, brand):
    decisions = []
    for row in data["products"]:
        payload = product_payload(row, categories[row["approved_family"]]["id"], brand["id"])
        hits = [p for p in state["products"] if p.get("model") == row["metric_model"] or p.get("name") == row["approved_name"]]
        exact = [p for p in hits if p.get("model") == payload["model"] and p.get("name") == payload["name"] and
                 nested_id(p.get("brand")) == brand["id"] and nested_id(p.get("category")) == payload["category"] and
                 p.get("is_published") is False and p.get("is_featured") is False and p.get("price") is None and
                 p.get("price_visible") is False]
        if not hits:
            status, product = "create_candidate", None
        elif len(hits) == len(exact) == 1:
            status, product = "already_imported_exact", exact[0]
        else:
            status, product = "conflict_existing_product", hits[0] if len(hits) == 1 else None
        decisions.append({"row": row, "payload": payload, "status": status, "product": product})
    return decisions


def batch_ranges(count=36, batch_size=20):
    if not 1 <= batch_size <= 20:
        raise ConflictError("--batch-size debe estar entre 1 y 20")
    return [list(range(i, min(i + batch_size, count))) for i in range(0, count, batch_size)]


def resource_view(root, categories, brand):
    def category(item):
        return {"id": item.get("id"), "name": item.get("name"), "slug": item.get("slug"),
                "parent": nested_id(item.get("parent")), "product_type": item.get("product_type"),
                "is_active": item.get("is_active")}
    return {"categories": [category(root)] + [category(categories[name]) for name in FAMILIES],
            "brand": {"id": brand.get("id"), "name": brand.get("name")}}


def remote_fingerprint(state):
    compact = {key: state[key] for key in ("categories", "brands", "products", "images", "specs", "sheets")}
    return sha(canonical(compact))


def build_operations(data, decisions, batch_size):
    operations = []
    def append(operation):
        operation["operation_order"] = len(operations) + 1
        identity = {"contract_version": OPERATION_CONTRACT_VERSION,
                    **{k: operation.get(k, "") for k in ("approval_key", "source_key", "metric_model",
                        "product_source_order", "phase", "action", "method", "path_template",
                        "specification_index", "payload_sha256", "file_sha256", "depends_on_operation_key")}}
        operation["operation_key"] = sha(canonical(identity))
        operations.append(operation)
        return operation
    for index, decision in enumerate(decisions):
        if decision["status"] != "create_candidate":
            continue
        row, model = decision["row"], decision["row"]["metric_model"]
        batch, dependency = index // batch_size + 1, ""
        sheet = data["sheets"][model]
        if truth(sheet.get("datasheet_upload_allowed")):
            operation = {"batch": batch, "product_source_order": row["source_order"], "approval_key": row["approval_key"], "source_key": row["source_key"], "metric_model": model,
                         "phase": "datasheet", "method": "POST", "path_template": "/api/technical-sheets",
                         "resource_type": "datasheet", "action": "upload", "depends_on_operation": "", "depends_on_operation_key": "",
                         "payload_sha256": sha(canonical({"name": f"Ficha técnica LGMG {model}"})),
                         "file_sha256": sheet.get("corrected_sha256", ""), "file_size_bytes": sheet.get("corrected_size_bytes", ""),
                         "request_template": {"name": f"Ficha técnica LGMG {model}"}, "resolved_payload_sha256": "", "association_order": "", "is_primary": "", "embedded_specification_count": 0, "status": "planned"}
            dependency_op = append(operation); dependency = dependency_op["operation_order"]
        payload = dict(decision["payload"])
        if dependency: payload["technical_sheet"] = "{created_datasheet_id}"
        product_template = payload
        operation = {"batch": batch, "product_source_order": row["source_order"], "approval_key": row["approval_key"], "source_key": row["source_key"], "metric_model": model,
                     "phase": "product", "method": "POST", "path_template": "/api/products", "resource_type": "product",
                     "action": "create", "depends_on_operation": dependency, "depends_on_operation_key": dependency_op["operation_key"] if dependency else "", "payload_sha256": sha(canonical(product_template)), "request_template": product_template, "resolved_payload_sha256": "",
                     "file_sha256": "", "file_size_bytes": "", "association_order": "", "is_primary": "",
                     "embedded_specification_count": 0, "status": "planned"}
        product_operation = append(operation); product_op = product_operation["operation_order"]
        seen_specs = set()
        for spec_index, spec in enumerate(data["specs"][row["source_key"]], 1):
            individual = specification_identity(spec)
            template = {"product_id_ref": {"operation_key": product_operation["operation_key"]}, **individual}
            duplicate_identity = canonical(template)
            if duplicate_identity in seen_specs:
                raise ConflictError(f"duplicate_specification_request: {model} índice {spec_index}")
            seen_specs.add(duplicate_identity)
            append({"batch": batch, "product_source_order": row["source_order"], "approval_key": row["approval_key"], "source_key": row["source_key"], "metric_model": model,
                "phase": "specification", "method": "POST", "path_template": "/api/product-specs",
                "resource_type": "specification", "action": "create", "depends_on_operation": product_op,
                "depends_on_operation_key": product_operation["operation_key"], "payload_sha256": sha(canonical(template)),
                "request_template": template, "resolved_payload_sha256": "", "file_sha256": "", "file_size_bytes": "", "association_order": "",
                "is_primary": "", "specification_index": spec_index, "specification_name": individual["name"],
                "specification_key": individual["key"], "specification_value": individual["value"],
                "specification_unit": individual["unit"], "specification_order": individual["order"],
                "embedded_specification_count": 0, "status": "planned"})
        for image in data["images"][model]:
            template = {"product_id_ref": {"operation_key": product_operation["operation_key"]}, "alt_text": image.get("original_filename", ""), "order": int(image["association_order"]) - 1, "is_main": truth(image["is_primary"])}
            append({"batch": batch, "product_source_order": row["source_order"], "approval_key": row["approval_key"], "source_key": row["source_key"], "metric_model": model,
                "phase": "image", "method": "POST", "path_template": "/api/product-images",
                "resource_type": "image", "action": "upload_and_associate", "depends_on_operation": product_op, "depends_on_operation_key": product_operation["operation_key"],
                "payload_sha256": sha(canonical(template)), "request_template": template, "resolved_payload_sha256": "",
                "file_sha256": image["sha256"], "file_size_bytes": image["size_bytes"],
                "association_order": image["association_order"], "is_primary": truth(image["is_primary"]),
                "embedded_specification_count": 0, "status": "planned"})
    keys = [operation["operation_key"] for operation in operations]
    if len(keys) != len(set(keys)):
        raise ConflictError("duplicate_operation_key")
    return operations


def operations_fingerprint(operations):
    return sha(canonical([{k: v for k, v in operation.items() if k != "status"} for operation in operations]))


def validate_operation_dependencies(operations):
    by_order = {op["operation_order"]: op for op in operations}
    by_key = {op["operation_key"]: op for op in operations}
    if len(by_order) != len(operations) or len(by_key) != len(operations):
        raise ConflictError("Órdenes u operation keys duplicadas")
    for operation in operations:
        order, key = operation.get("depends_on_operation"), operation.get("depends_on_operation_key")
        if bool(order) != bool(key):
            raise ConflictError("Dependencia incompleta por order/key")
        if order:
            dependency = by_order.get(order)
            if dependency is None or by_key.get(key) is not dependency or order >= operation["operation_order"] or dependency["metric_model"] != operation["metric_model"]:
                raise ConflictError("Dependencia inexistente, posterior o de otro producto")


def dry_run_fingerprint(data, decisions, origin, remote_fp, tool_head_value, operations=None, batch_size=20,
                        resources_preexisting=None):
    operations = operations or []
    contract = {"tool": TOOL_NAME, "version": TOOL_VERSION, "tool_head": tool_head_value, "api_base": origin,
                "batch_size": batch_size, "fingerprints": data["fingerprints"], "remote_state_fingerprint_sha256": remote_fp,
                "category_slug_policy": CATEGORY_SLUG_POLICY,
                "resources_preexisting": resources_preexisting or {},
                "products": [{"source_key": d["row"].get("source_key"), "metric_model": d["row"].get("metric_model"),
                    "approval_key": d["row"]["approval_key"], "status": d["status"],
                    "payload_sha256": sha(canonical(d["payload"])), "payload": d["payload"],
                    "specifications": data.get("specs", {}).get(d["row"].get("source_key"), []),
                    "images": data.get("images", {}).get(d["row"].get("metric_model"), []),
                    "datasheet": data.get("sheets", {}).get(d["row"].get("metric_model"), {})} for d in decisions],
                "planned_operations": operations, "planned_batches": [len(x) for x in batch_ranges(len(decisions), batch_size)]}
    return sha(canonical(contract))


def tool_head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, check=True,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".staging", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def operation_counts(operations):
    result = {"total": len(operations)}
    for operation in operations:
        key = operation["resource_type"] + "_operations"
        result[key] = result.get(key, 0) + 1
    return result


def checkpoint_contract(batch_size, origin, data, dry_fp, remote_fp, operations_fp, resources, operations):
    products = {}
    for row in sorted(data["products"], key=lambda item: item["approval_key"]):
        products[row["approval_key"]] = {"metric_model": row["metric_model"], "status": "not_started", "created": {}}
    return {"schema_version": CHECKPOINT_SCHEMA_VERSION, "tool": TOOL_NAME, "version": TOOL_VERSION,
            "tool_head": tool_head(), "state": "dry_run_ready", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "api_base": origin, "batch_size": batch_size, "fingerprints": data["fingerprints"],
            "remote_state_fingerprint_sha256": remote_fp, "planned_operations_fingerprint_sha256": operations_fp,
            "dry_run_fingerprint_sha256": dry_fp,
            "superseded_dry_run_fingerprints": dict(SUPERSEDED_DRY_RUN_FINGERPRINTS),
            "category_slug_policy": CATEGORY_SLUG_POLICY,
            "slug_diagnostic": "category_and_brand_slugs_are_backend_catalog_filters; importer_resolves_names_to_ids",
            "resource_warnings": [],
            "approval_keys": sorted(products), "models": sorted(r["metric_model"] for r in data["products"]),
            "resolved_categories": resources["categories"], "resolved_brand": resources["brand"],
            "resources_preexisting": resources, "planned_batches": [len(x) for x in batch_ranges(36, batch_size)],
            "planned_operation_counts": operation_counts(operations), "planned_operations": operations,
            "products": products, "completed_operations": [], "resources_created": {"products": [], "images": [], "specifications": [], "datasheets": []},
            "mutations_executed": 0, "external_effects_zero": True, "apply_started": False, "rollback_started": False}


def read_checkpoint(path):
    value = json_value(regular_bytes(path, "checkpoint"), "checkpoint")
    dry_fp = value.get("dry_run_fingerprint_sha256")
    if dry_fp in SUPERSEDED_DRY_RUN_FINGERPRINTS:
        raise ConflictError(f"Checkpoint rechazado explícitamente: {SUPERSEDED_DRY_RUN_FINGERPRINTS[dry_fp]}")
    if value.get("state") not in CHECKPOINT_STATES:
        raise ConflictError("Checkpoint vacío o inválido")
    serialized = json.dumps(value, ensure_ascii=False)
    if any(word in serialized for word in ("Authorization", "Bearer ", "password", "cookie")):
        raise ConflictError("Checkpoint contiene material secreto")
    return value


def validate_checkpoint(value, expected):
    keys = ("schema_version", "tool", "version", "tool_head", "api_base", "batch_size", "fingerprints",
            "remote_state_fingerprint_sha256", "planned_operations_fingerprint_sha256", "dry_run_fingerprint_sha256",
            "resources_preexisting", "approval_keys", "models")
    if any(value.get(key) != expected.get(key) for key in keys):
        raise ConflictError("Checkpoint incompatible: inputs, API, herramienta, recursos, estado remoto o plan cambiaron")
    if value.get("planned_operations") != expected.get("planned_operations"):
        raise ConflictError("Checkpoint incompatible: operation keys, dependencias, templates o payloads cambiaron")


def validate_checkpoint_static(value, expected):
    keys = ("schema_version", "tool", "version", "tool_head", "api_base", "batch_size", "fingerprints",
            "resources_preexisting", "approval_keys", "models")
    if any(value.get(key) != expected.get(key) for key in keys):
        raise ConflictError("Checkpoint incompatible con inputs, API, herramienta o recursos preexistentes")
    planned = value.get("planned_operations", [])
    if operations_fingerprint(planned) != value.get("planned_operations_fingerprint_sha256"):
        raise ConflictError("Checkpoint incompatible: operaciones o claves alteradas")
    validate_operation_dependencies(planned)


def _csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader(); writer.writerows({k: _csv_safe(row.get(k, "")) for k in fields} for row in rows)


def write_outputs(output: Path, result, checkpoint: Path):
    output.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".remaining-import-staging-", dir=output))
    try:
        product_fields = ("source_order", "source_key", "metric_model", "approval_key", "approved_name", "approved_family", "status", "product_id", "verified", "category_id", "category_name", "category_parent_id", "brand_id", "brand_name", "payload_sha256", "specification_count", "image_count", "primary_image_sha256", "datasheet_action", "datasheet_sha256", "maximum_load_capacity_candidate_kg", "power_source_candidate", "power_source_representable", "show_price", "is_published", "is_featured", "price", "technical_followup_required", "planned_operation_count")
        operation_fields = ("operation_order", "operation_key", "batch", "product_source_order", "approval_key", "metric_model", "phase", "method", "path_template", "resource_type", "action", "depends_on_operation", "depends_on_operation_key", "payload_sha256", "resolved_payload_sha256", "file_sha256", "file_size_bytes", "association_order", "is_primary", "specification_index", "specification_name", "specification_key", "specification_value", "specification_unit", "specification_order", "embedded_specification_count", "status")
        write_csv(staging / OUTPUT_NAMES[2], product_fields, result["products"])
        write_csv(staging / OUTPUT_NAMES[3], ("metric_model", "kind", "association_order", "sha256", "size_bytes", "status", "followup"), result["media"])
        write_csv(staging / OUTPUT_NAMES[4], operation_fields, result["operations"])
        write_csv(staging / OUTPUT_NAMES[5], ("metric_model", "code", "detail", "blocking"), result["conflicts"])
        summary_keys = ("mode", "verdict", "fingerprints", "api_base", "batch_size", "batches", "counts", "planned_operation_counts", "errors", "followups", "resource_warnings", "category_slug_policy", "remote_state_fingerprint_sha256", "planned_operations_fingerprint_sha256", "dry_run_fingerprint_sha256", "superseded_dry_run_fingerprints")
        summary = {key: result[key] for key in summary_keys}
        (staging / OUTPUT_NAMES[0]).write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        lines = [f"Veredicto: {result['verdict']}", f"Modo: {result['mode']}", f"Política de slugs: {result['category_slug_policy']}", f"Productos: {len(result['products'])}"] + [f"{k}: {v}" for k, v in sorted(result["planned_operation_counts"].items())]
        (staging / OUTPUT_NAMES[1]).write_text("\n".join(lines) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[7]).write_text("IMPORTACIÓN CONTROLADA LGMG RESTANTE\n\nLos siete informes y el checkpoint 2.1 quedan enlazados criptográficamente. Cada ProductSpec conserva template, identidad y operation_key. Nunca publica productos ni corrige categorías.\n", encoding="utf-8")
        non_manifest = sorted(name for name in OUTPUT_NAMES if name != OUTPUT_NAMES[6])
        output_files = [{"name": name, "sha256": sha((staging / name).read_bytes()), "size_bytes": (staging / name).stat().st_size} for name in non_manifest]
        checkpoint_raw = regular_bytes(checkpoint, "checkpoint")
        manifest = {**summary, "tool": TOOL_NAME, "version": TOOL_VERSION, "tool_head": result["tool_head"],
                    "resources_preexisting": result["resources_preexisting"], "resources_created": result["resources_created"],
                    "checkpoint_file_name": checkpoint.name, "checkpoint_sha256": sha(checkpoint_raw),
                    "checkpoint_size_bytes": len(checkpoint_raw), "output_files": output_files,
                    "external_effects": result["external_effects"], "credentials_persisted": False}
        (staging / OUTPUT_NAMES[6]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if {p.name for p in staging.iterdir()} != set(OUTPUT_NAMES): raise ControlledImportError("No se generaron exactamente ocho informes")
        for name in OUTPUT_NAMES: os.replace(staging / name, output / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _base_result(mode, origin, data, batches, remote_fp, operations_fp, dry_fp, resources, operations, decisions, batch_size):
    media = []
    for model, rows in data["images"].items():
        media.extend({"metric_model": model, "kind": "image", "association_order": r["association_order"], "sha256": r["sha256"], "size_bytes": r["size_bytes"], "status": "planned", "followup": ""} for r in rows)
        sheet = data["sheets"][model]
        media.append({"metric_model": model, "kind": "datasheet", "association_order": "", "sha256": sheet.get("corrected_sha256", ""), "size_bytes": sheet.get("corrected_size_bytes", ""), "status": "planned" if truth(sheet.get("datasheet_upload_allowed")) else "excluded", "followup": sheet.get("warnings", "")})
    products = []
    for decision in decisions:
        row, payload = decision["row"], decision["payload"]; model = row["metric_model"]
        specs, images, sheet = data["specs"][row["source_key"]], data["images"][model], data["sheets"][model]
        category = next(x for x in resources["categories"] if x["name"] == row["approved_family"])
        products.append({"source_order": row["source_order"], "source_key": row["source_key"], "metric_model": model, "approval_key": row["approval_key"], "approved_name": row["approved_name"], "approved_family": row["approved_family"], "status": decision["status"], "product_id": (decision["product"] or {}).get("id", ""), "verified": decision["status"] == "already_imported_exact", "category_id": category["id"], "category_name": category["name"], "category_parent_id": category["parent"], "brand_id": resources["brand"]["id"], "brand_name": resources["brand"]["name"], "payload_sha256": sha(canonical(payload)), "specification_count": len(specs), "image_count": len(images), "primary_image_sha256": next(x["sha256"] for x in images if truth(x["is_primary"])), "datasheet_action": "upload" if truth(sheet.get("datasheet_upload_allowed")) else "excluded", "datasheet_sha256": sheet.get("corrected_sha256", ""), "maximum_load_capacity_candidate_kg": payload["maximum_load_capacity_kg"], "power_source_candidate": row.get("target_power_source", ""), "power_source_representable": payload["power_source"] is not None, "show_price": False, "is_published": False, "is_featured": False, "price": "", "technical_followup_required": not truth(sheet.get("datasheet_upload_allowed")), "planned_operation_count": sum(x["metric_model"] == model for x in operations)})
    return {"mode": mode, "verdict": "CONFLICT", "fingerprints": data["fingerprints"], "api_base": origin, "batch_size": batch_size,
            "batches": [len(x) for x in batches], "counts": {}, "planned_operation_counts": operation_counts(operations), "errors": [],
            "followups": [x for x in media if x["followup"] or x["status"] == "excluded"], "remote_state_fingerprint_sha256": remote_fp,
            "planned_operations_fingerprint_sha256": operations_fp, "dry_run_fingerprint_sha256": dry_fp,
            "superseded_dry_run_fingerprints": dict(SUPERSEDED_DRY_RUN_FINGERPRINTS),
            "category_slug_policy": CATEGORY_SLUG_POLICY, "resource_warnings": [],
            "tool_head": tool_head(), "products": products, "media": media, "operations": operations, "conflicts": [],
            "resources_preexisting": resources, "resources_created": {"products": [], "images": [], "specifications": [], "datasheets": []},
            "external_effects": {"api_called": True, "database_modified": False, "products_created": 0, "products_updated": 0,
                "products_deleted": 0, "images_uploaded": 0, "datasheets_uploaded": 0, "content_published": False,
                "mutating_requests_executed": 0}}


def _record_mutation(checkpoint_path, checkpoint, operation, resource_type, resource_id):
    completed = {"operation_order": operation["operation_order"], "operation_key": operation["operation_key"],
                 "resource_type": operation["resource_type"], "depends_on_operation_key": operation.get("depends_on_operation_key", ""),
                 "request_template_sha256": operation["payload_sha256"],
                 "resolved_payload_sha256": operation.get("resolved_payload_sha256", ""),
                 "resource_id": resource_id, "metric_model": operation["metric_model"], "status": "completed"}
    checkpoint["completed_operations"].append(completed)
    checkpoint["mutations_executed"] += 1
    checkpoint["external_effects_zero"] = False
    checkpoint["resources_created"][resource_type].append(resource_id)
    atomic_json(checkpoint_path, checkpoint)


def run(plan, audit, repaired, output, origin, mode, token, checkpoint=None, batch_size=20, resume=False,
        client_factory=ApiClient):
    if checkpoint is None:
        raise ConflictError("--checkpoint es obligatorio en dry-run, apply, verify y rollback")
    validate_paths(plan, audit, repaired, output, checkpoint, resume if mode == "dry_run" else True)
    data = validate_inputs(plan, audit, repaired)
    origin = normalize_origin(origin); batches = batch_ranges(36, batch_size)
    if mode == "apply" and (not checkpoint.is_file() or checkpoint.stat().st_size == 0):
        raise ConflictError("Apply exige un checkpoint dry-run preexistente y no vacío")
    client = client_factory(origin, token, mode)
    state = snapshot(client); root, categories, brand = resolve_taxonomy(state)
    decisions = classify_products(data, state, categories, brand)
    if len(decisions) != 36 or any(d["status"] == "conflict_existing_product" for d in decisions):
        raise ConflictError("CONFLICT: la clasificación remota no contiene exactamente 36 candidatas sin conflictos")
    resources = resource_view(root, categories, brand)
    operations = build_operations(data, decisions, batch_size)
    remote_fp, operations_fp, head = remote_fingerprint(state), operations_fingerprint(operations), tool_head()
    dry_fp = dry_run_fingerprint(data, decisions, origin, remote_fp, head, operations, batch_size, resources)
    if dry_fp in SUPERSEDED_DRY_RUN_FINGERPRINTS:
        raise ConflictError("El fingerprint supersedido nunca es aplicable")
    validate_operation_dependencies(operations)
    counts = operation_counts(operations)
    required = {"datasheet_operations": 33, "product_operations": 36,
                "specification_operations": 1057, "image_operations": 71, "total": 1197}
    if any(counts.get(key) != value for key, value in required.items()):
        raise ConflictError("Conteos contractuales 33/36/1057/71/1197 incumplidos")
    expected = checkpoint_contract(batch_size, origin, data, dry_fp, remote_fp, operations_fp, resources, operations)
    result = _base_result(mode, origin, data, batches, remote_fp, operations_fp, dry_fp, resources, operations, decisions, batch_size)
    if mode == "dry_run":
        if resume:
            existing = read_checkpoint(checkpoint)
            if existing.get("state") != "dry_run_ready":
                raise ConflictError("Dry-run resume no puede convertir un apply parcial")
            validate_checkpoint(existing, expected)
            expected = existing
        else:
            atomic_json(checkpoint, expected)
        result["verdict"] = "DRY_RUN_READY"
        result["counts"] = {"candidates": 36, "conflicts": 0, "writes": 0, "images_planned": 71,
                            "datasheets_planned": 33, "datasheets_excluded": 3, "mutating_requests_executed": 0}
        write_outputs(output, result, checkpoint); return 0

    cp = read_checkpoint(checkpoint)
    if mode == "apply" and not resume:
        validate_checkpoint(cp, expected)
    else:
        validate_checkpoint_static(cp, expected)
    if mode == "apply":
        if cp["state"] in {"apply_in_progress", "apply_partial"} and not resume:
            raise ConflictError("--resume es obligatorio para continuar apply parcial")
        if cp["state"] not in ({"apply_in_progress", "apply_partial"} if resume else {"dry_run_ready"}):
            raise ConflictError("Estado de checkpoint no permite apply")
        if not resume:
            cp["state"] = "apply_in_progress"; cp["apply_started"] = True; atomic_json(checkpoint, cp)
        if resume:
            operations = cp["planned_operations"]
            planned_keys = {operation["operation_key"] for operation in operations}
            if any(done.get("operation_key") not in planned_keys for done in cp["completed_operations"]):
                raise ConflictError("Operación completada no coincide con ninguna operation_key del plan")
        try:
            for operation in operations:
                if any(done.get("operation_key") == operation["operation_key"] for done in cp["completed_operations"]):
                    continue
                key = next(r["approval_key"] for r in data["products"] if r["metric_model"] == operation["metric_model"])
                created = cp["products"][key]["created"]
                if operation["resource_type"] == "datasheet":
                    sheet = data["sheets"][operation["metric_model"]]; path, raw = _validate_local_media(repaired, sheet, "datasheet")
                    body, mime = _multipart_sheet(operation["metric_model"], path.name, raw)
                    made = client.request("POST", "/api/technical-sheets", body, content_type=mime); created["datasheet"] = made["id"]
                elif operation["resource_type"] == "product":
                    decision = next(d for d in decisions if d["row"]["metric_model"] == operation["metric_model"])
                    payload = dict(decision["payload"]); payload["technical_sheet"] = created.get("datasheet")
                    made = client.post("/api/products", payload); created["product"] = made["id"]
                elif operation["resource_type"] == "specification":
                    rows = data["specs"][next(r["source_key"] for r in data["products"] if r["metric_model"] == operation["metric_model"])]
                    row = rows[int(operation["specification_index"]) - 1]
                    expected_template = {"product_id_ref": {"operation_key": operation["depends_on_operation_key"]},
                                         **specification_identity(row)}
                    if expected_template != operation["request_template"] or sha(canonical(expected_template)) != operation["payload_sha256"]:
                        raise ConflictError("Template individual de especificación divergente")
                    resolved = spec_payload(row, created["product"])
                    operation["resolved_payload_sha256"] = sha(canonical(resolved))
                    made = client.post("/api/product-specs", resolved)
                else:
                    image = next(r for r in data["images"][operation["metric_model"]] if r["sha256"] == operation["file_sha256"])
                    path, raw = _validate_local_media(repaired, image, "image"); body, mime = _multipart_image(created["product"], image, path.name, raw)
                    made = client.request("POST", "/api/product-images", body, content_type=mime)
                _record_mutation(checkpoint, cp, operation, operation["resource_type"] + "s", made["id"])
                cp["products"][key]["status"] = "in_progress"; atomic_json(checkpoint, cp)
            final = snapshot(client); _, final_categories, final_brand = resolve_taxonomy(final)
            if any(d["status"] != "already_imported_exact" for d in classify_products(data, final, final_categories, final_brand)):
                raise ControlledImportError("Verificación final de 36 productos incompleta")
            cp["state"] = "apply_complete"
            for item in cp["products"].values(): item["status"] = "verified"
            atomic_json(checkpoint, cp); result["verdict"] = "APPLY_COMPLETE"
        except (ControlledImportError, KeyError, IndexError) as exc:
            cp["state"] = "apply_partial"; atomic_json(checkpoint, cp)
            result["verdict"] = "APPLY_PARTIAL"; result["errors"] = [{"code": "apply_stopped", "message": str(exc)[:240]}]
            write_outputs(output, result, checkpoint); return 2
    elif mode == "verify":
        if cp["state"] not in {"apply_complete", "verify_complete"} or any(d["status"] != "already_imported_exact" for d in decisions):
            raise ConflictError("Verify exige checkpoint apply_complete y 36 productos exactos")
        cp["state"] = "verify_complete"; atomic_json(checkpoint, cp); result["verdict"] = "VERIFY_COMPLETE"
    else:
        if cp["state"] not in {"apply_partial", "apply_complete", "verify_complete", "rollback_in_progress"}:
            raise ConflictError("Checkpoint no permite rollback")
        cp["state"] = "rollback_in_progress"; cp["rollback_started"] = True; atomic_json(checkpoint, cp)
        endpoints = {"specifications": "product-specs", "images": "product-images", "products": "products", "datasheets": "technical-sheets"}
        for done in reversed(cp["completed_operations"]):
            if done.get("rollback_completed") or done["resource_type"] not in {"specification", "image", "product", "datasheet"}: continue
            client.delete(f"/api/{endpoints[done['resource_type'] + 's']}/{int(done['resource_id'])}")
            done["rollback_completed"] = True; atomic_json(checkpoint, cp)
        cp["state"] = "rollback_complete"; atomic_json(checkpoint, cp); result["verdict"] = "ROLLBACK_COMPLETE"
    result["resources_created"] = cp["resources_created"]
    result["external_effects"]["mutating_requests_executed"] = cp["mutations_executed"]
    result["counts"] = {"products": 36, "mutating_requests_executed": cp["mutations_executed"]}
    write_outputs(output, result, checkpoint); return 0


def _multipart_image(product_id, row, filename, data):
    boundary = "----jem-controlled-" + uuid.uuid4().hex
    fields = (("product", product_id), ("alt_text", row.get("original_filename", "")), ("order", int(row["association_order"]) - 1), ("is_main", str(truth(row["is_primary"])).lower()))
    body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields)
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename.replace(chr(34), '')}\"\r\nContent-Type: {row['mime']}\r\n\r\n".encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, "multipart/form-data; boundary=" + boundary


def _multipart_sheet(model, filename, data):
    boundary = "----jem-sheet-" + uuid.uuid4().hex
    body = f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\nFicha técnica LGMG {model}\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename.replace(chr(34), '')}\"\r\nContent-Type: application/pdf\r\n\r\n".encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, "multipart/form-data; boundary=" + boundary


def access_token(environ=os.environ):
    token = environ.get(TOKEN_ENV, "")
    if not token or "\r" in token or "\n" in token:
        raise ConflictError(f"Defina {TOKEN_ENV} mediante el entorno")
    return token


def build_parser():
    parser = argparse.ArgumentParser(description="Importación completa controlada de 36 productos LGMG restantes")
    for name in ("plan-input", "remaining-audit-input", "repaired-media-input", "output-dir", "api-base-url"):
        parser.add_argument("--" + name, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("dry-run", "apply", "verify", "rollback"): modes.add_argument("--" + mode, action="store_true")
    parser.add_argument("--checkpoint", required=True); parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--resume", action="store_true"); parser.add_argument("--confirm-apply")
    parser.add_argument("--confirm-rollback")
    return parser


def validate_cli(args):
    mode = next(x.replace("_", "-") for x in ("dry_run", "apply", "verify", "rollback") if getattr(args, x))
    mode = mode.replace("-", "_") if mode == "dry-run" else mode
    if not 1 <= args.batch_size <= 20: raise ConflictError("--batch-size debe estar entre 1 y 20")
    if not args.checkpoint: raise ConflictError("--checkpoint es obligatorio en los cuatro modos")
    if mode == "apply" and args.confirm_apply != APPLY_CONFIRMATION: raise ConflictError("Confirmación exacta de apply ausente")
    if mode == "rollback" and args.confirm_rollback != ROLLBACK_CONFIRMATION: raise ConflictError("Confirmación exacta de rollback ausente")
    if mode in {"dry_run", "verify"} and (args.confirm_apply is not None or args.confirm_rollback is not None): raise ConflictError("Modos de lectura no aceptan confirmaciones de escritura")
    if mode == "apply" and args.confirm_rollback is not None or mode == "rollback" and args.confirm_apply is not None: raise ConflictError("Confirmación incompatible")
    if args.resume and not args.checkpoint: raise ConflictError("--resume exige --checkpoint")
    return mode


def main(argv=None):
    try:
        args = build_parser().parse_args(argv); mode = validate_cli(args); token = access_token()
        return run(Path(args.plan_input), Path(args.remaining_audit_input), Path(args.repaired_media_input), Path(args.output_dir),
                   args.api_base_url, mode, token, Path(args.checkpoint) if args.checkpoint else None, args.batch_size, args.resume)
    except ConflictError as exc:
        print("CONFLICT: " + str(exc)[:240], file=sys.stderr); return 3
    except (ControlledImportError, OSError) as exc:
        print("Error operativo seguro: " + str(exc)[:240], file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
