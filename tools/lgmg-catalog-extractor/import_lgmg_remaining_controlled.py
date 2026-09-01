#!/usr/bin/env python3
"""Importador completo, cerrado y reversible de los 36 productos LGMG restantes."""

from __future__ import annotations

import argparse
import ast
import csv
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
TOOL_VERSION = "1.0.0"
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
    specs = csv_rows(regular_bytes(plan_root / "import-specifications.csv", "import-specifications.csv"), "import-specifications.csv")
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
    categories = {}
    for family in FAMILIES:
        hits = [x for x in state["categories"] if x.get("name") == family]
        if len(hits) != 1 or nested_id(hits[0].get("parent")) != root.get("id") or hits[0].get("product_type") != "machinery" or hits[0].get("is_active") is not True:
            raise ConflictError(f"Subcategoría ausente, duplicada o con jerarquía incorrecta: {family}")
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
    return {"product": product_id, "name": row.get("name") or row.get("spec_name"),
            "key": row.get("key") or row.get("spec_key"), "value": row.get("value") or row.get("spec_value"),
            "unit": row.get("unit") or None, "order": int(row.get("order") or row.get("spec_order") or 0)}


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


def remote_fingerprint(state):
    compact = {key: state[key] for key in ("categories", "brands", "products", "images", "specs", "sheets")}
    return sha(canonical(compact))


def dry_run_fingerprint(data, decisions, origin, remote_fp, tool_head):
    contract = {"tool": TOOL_NAME, "version": TOOL_VERSION, "head": tool_head, "api_base": origin,
                "fingerprints": data["fingerprints"], "remote_fingerprint": remote_fp,
                "operations": [{"approval_key": d["row"]["approval_key"], "status": d["status"], "payload": d["payload"]} for d in decisions]}
    return sha(canonical(contract))


def tool_head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, check=True,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def checkpoint_contract(mode, batch_size, origin, data, dry_fp):
    return {"tool": TOOL_NAME, "version": TOOL_VERSION, "mode": mode, "batch_size": batch_size,
            "api_base": origin, "fingerprints": data["fingerprints"], "dry_run_fingerprint_sha256": dry_fp,
            "products": {r["approval_key"]: {"status": "not_started", "created": {}} for r in data["products"]},
            "preexisting": {}, "created": {"products": [], "images": [], "specs": [], "datasheets": [], "categories": [], "brands": []},
            "mutating_requests": [], "rollback_completed": []}


def load_checkpoint(path, expected, resume):
    if not resume:
        atomic_json(path, expected); return expected
    value = json_value(regular_bytes(path, "checkpoint"), "checkpoint")
    for key in ("tool", "version", "mode", "batch_size", "api_base", "fingerprints", "dry_run_fingerprint_sha256"):
        if value.get(key) != expected.get(key):
            raise ConflictError("Checkpoint incompatible con entradas, API, modo o configuración")
    if "Authorization" in json.dumps(value) or "Bearer " in json.dumps(value):
        raise ConflictError("Checkpoint inseguro")
    return value


def _csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader(); writer.writerows({k: _csv_safe(row.get(k, "")) for k in fields} for row in rows)


def write_outputs(output: Path, result):
    output.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".remaining-import-staging-", dir=output))
    try:
        write_csv(staging / OUTPUT_NAMES[2], ("source_order", "source_key", "metric_model", "approval_key", "approved_name", "approved_family", "status", "product_id", "verified"), result["products"])
        write_csv(staging / OUTPUT_NAMES[3], ("metric_model", "kind", "association_order", "sha256", "size_bytes", "status", "followup"), result["media"])
        write_csv(staging / OUTPUT_NAMES[4], ("order", "batch", "method", "path", "metric_model", "status"), result["operations"])
        write_csv(staging / OUTPUT_NAMES[5], ("metric_model", "code", "detail", "blocking"), result["conflicts"])
        summary = {k: result[k] for k in ("mode", "verdict", "fingerprints", "api_base", "counts", "batches", "errors", "followups", "dry_run_fingerprint_sha256")}
        (staging / OUTPUT_NAMES[0]).write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[1]).write_text(f"Veredicto: {result['verdict']}\nModo: {result['mode']}\nProductos: {len(result['products'])}\n", encoding="utf-8")
        manifest = {**summary, "tool": TOOL_NAME, "version": TOOL_VERSION, "tool_head": result["tool_head"],
                    "products": result["products"], "resources_preexisting": result["preexisting"],
                    "resources_created": result["created"], "external_effects": result["external_effects"],
                    "credentials_persisted": False, "output_files": []}
        (staging / OUTPUT_NAMES[6]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[7]).write_text("IMPORTACIÓN CONTROLADA LGMG RESTANTE\n\nRevise veredicto, conflictos, operaciones, seguimientos y efectos externos. Nunca publica productos.\n", encoding="utf-8")
        if {p.name for p in staging.iterdir()} != set(OUTPUT_NAMES):
            raise ControlledImportError("No se generaron exactamente ocho informes")
        for name in OUTPUT_NAMES: os.replace(staging / name, output / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _base_result(mode, origin, data, batches, dry_fp):
    media = []
    for model, rows in data["images"].items():
        media.extend({"metric_model": model, "kind": "image", "association_order": r["association_order"], "sha256": r["sha256"], "size_bytes": r["size_bytes"], "status": "planned", "followup": ""} for r in rows)
        sheet = data["sheets"][model]
        media.append({"metric_model": model, "kind": "datasheet", "association_order": "", "sha256": sheet.get("corrected_sha256", ""), "size_bytes": sheet.get("corrected_size_bytes", ""), "status": "planned" if truth(sheet.get("datasheet_upload_allowed")) else "excluded", "followup": sheet.get("warnings", "")})
    return {"mode": mode, "verdict": "CONFLICT", "fingerprints": data["fingerprints"], "api_base": origin,
            "counts": {}, "batches": [len(x) for x in batches], "errors": [], "followups": [x for x in media if x["followup"]],
            "dry_run_fingerprint_sha256": dry_fp, "tool_head": tool_head(), "products": [], "media": media,
            "operations": [], "conflicts": [], "preexisting": {}, "created": {},
            "external_effects": {"api_called": True, "database_modified": False, "products_imported": 0, "content_published": False}}


def run(plan, audit, repaired, output, origin, mode, token, checkpoint=None, batch_size=20, resume=False, client_factory=ApiClient):
    validate_paths(plan, audit, repaired, output, checkpoint, resume)
    data = validate_inputs(plan, audit, repaired)
    origin = normalize_origin(origin); batches = batch_ranges(36, batch_size)
    client = client_factory(origin, token, mode)
    state = snapshot(client); _, categories, brand = resolve_taxonomy(state)
    decisions = classify_products(data, state, categories, brand)
    remote_fp = remote_fingerprint(state); head = tool_head()
    dry_fp = dry_run_fingerprint(data, decisions, origin, remote_fp, head)
    result = _base_result(mode, origin, data, batches, dry_fp); result["tool_head"] = head
    for decision in decisions:
        row = decision["row"]
        result["products"].append({"source_order": row["source_order"], "source_key": row["source_key"], "metric_model": row["metric_model"],
            "approval_key": row["approval_key"], "approved_name": row["approved_name"], "approved_family": row["approved_family"],
            "status": decision["status"], "product_id": (decision["product"] or {}).get("id", ""), "verified": decision["status"] == "already_imported_exact"})
    conflicts = [d for d in decisions if d["status"] == "conflict_existing_product"]
    if conflicts:
        result["conflicts"] = [{"metric_model": d["row"]["metric_model"], "code": "existing_product_conflict", "detail": "Coincidencia ambigua o incompatible", "blocking": True} for d in conflicts]
        write_outputs(output, result); return 3
    if mode == "dry_run":
        for index, d in enumerate(decisions):
            if d["status"] == "create_candidate":
                result["operations"].append({"order": len(result["operations"]) + 1, "batch": index // batch_size + 1, "method": "POST", "path": "/api/products", "metric_model": d["row"]["metric_model"], "status": "planned"})
        result["verdict"] = "DRY_RUN_READY"; result["counts"] = {"candidates": sum(d["status"] == "create_candidate" for d in decisions), "writes": 0}
        write_outputs(output, result); return 0
    if checkpoint is None:
        raise ConflictError("apply, verify y rollback exigen --checkpoint")
    if mode == "apply":
        dry_report = checkpoint.parent / "remaining-import-summary.json"
        if not dry_report.is_file():
            raise ConflictError("Apply exige el informe dry-run compatible junto al checkpoint")
        prior = json_value(regular_bytes(dry_report, dry_report.name), dry_report.name)
        if prior.get("verdict") != "DRY_RUN_READY" or prior.get("dry_run_fingerprint_sha256") != dry_fp:
            raise ConflictError("Apply rechazado sin dry-run compatible y estado remoto estable")
        cp = load_checkpoint(checkpoint, checkpoint_contract(mode, batch_size, origin, data, dry_fp), resume)
        result["created"], result["preexisting"] = cp["created"], cp["preexisting"]
        try:
            for indexes in batches:
                for index in indexes:
                    d = decisions[index]; row = d["row"]; key = row["approval_key"]
                    if cp["products"][key]["status"] == "completed": continue
                    if d["status"] == "already_imported_exact":
                        cp["preexisting"][key] = d["product"]["id"]; cp["products"][key]["status"] = "completed"; atomic_json(checkpoint, cp); continue
                    product = client.post("/api/products", d["payload"])
                    if not isinstance(product, dict) or not isinstance(product.get("id"), int): raise ControlledImportError("Respuesta de creación inválida")
                    pid = product["id"]; cp["created"]["products"].append(pid); cp["products"][key]["created"]["product"] = pid; atomic_json(checkpoint, cp)
                    for spec in data["specs"][row["source_key"]]:
                        made = client.post("/api/product-specs", spec_payload(spec, pid)); cp["created"]["specs"].append(made["id"]); atomic_json(checkpoint, cp)
                    # El multipart y el enlace de ficha reutilizan exactamente los endpoints probados; se registran antes de cada escritura.
                    for image in data["images"][row["metric_model"]]:
                        path, raw = _validate_local_media(repaired, image, "image")
                        payload = _multipart_image(pid, image, path.name, raw)
                        made = client.request("POST", "/api/product-images", payload[0], content_type=payload[1]); cp["created"]["images"].append(made["id"]); atomic_json(checkpoint, cp)
                    sheet = data["sheets"][row["metric_model"]]
                    if truth(sheet.get("datasheet_upload_allowed")):
                        path, raw = _validate_local_media(repaired, sheet, "datasheet")
                        body, mime = _multipart_sheet(row["metric_model"], path.name, raw)
                        made = client.request("POST", "/api/technical-sheets", body, content_type=mime); cp["created"]["datasheets"].append(made["id"])
                        client.patch(f"/api/products/{pid}", {"technical_sheet": made["id"]})
                    cp["products"][key]["status"] = "completed"; atomic_json(checkpoint, cp)
            final = snapshot(client); _, fcats, fbrand = resolve_taxonomy(final)
            if any(d["status"] != "already_imported_exact" for d in classify_products(data, final, fcats, fbrand)):
                raise ControlledImportError("Verificación final incompleta")
            result["verdict"] = "APPLY_COMPLETE"; result["external_effects"]["database_modified"] = bool(cp["created"]["products"]); result["external_effects"]["products_imported"] = len(cp["created"]["products"])
        except ControlledImportError as exc:
            result["verdict"] = "APPLY_PARTIAL"; result["errors"] = [{"code": "apply_stopped", "message": str(exc)[:240]}]
            write_outputs(output, result); return 2
    elif mode == "verify":
        if any(d["status"] != "already_imported_exact" for d in decisions): raise ConflictError("Verify requiere los 36 productos exactos")
        result["verdict"] = "VERIFY_COMPLETE"
    elif mode == "rollback":
        cp = json_value(regular_bytes(checkpoint, "checkpoint"), "checkpoint")
        if cp.get("tool") != TOOL_NAME or cp.get("fingerprints") != data["fingerprints"] or cp.get("api_base") != origin:
            raise ConflictError("Checkpoint no pertenece a esta importación")
        for kind, endpoint in (("specs", "product-specs"), ("images", "product-images"), ("datasheets", "technical-sheets"), ("products", "products"), ("categories", "categories"), ("brands", "brands")):
            for resource_id in reversed(cp.get("created", {}).get(kind, [])):
                marker = f"{kind}:{resource_id}"
                if marker not in cp.get("rollback_completed", []):
                    client.delete(f"/api/{endpoint}/{int(resource_id)}"); cp.setdefault("rollback_completed", []).append(marker); atomic_json(checkpoint, cp)
        result["verdict"] = "ROLLBACK_COMPLETE"; result["created"] = cp.get("created", {})
    result["counts"] = {"products": 36, "writes": sum(x["method"] != "GET" for x in client.operations)}
    write_outputs(output, result); return 0


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
    parser.add_argument("--checkpoint"); parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--resume", action="store_true"); parser.add_argument("--confirm-apply")
    parser.add_argument("--confirm-rollback")
    return parser


def validate_cli(args):
    mode = next(x.replace("_", "-") for x in ("dry_run", "apply", "verify", "rollback") if getattr(args, x))
    mode = mode.replace("-", "_") if mode == "dry-run" else mode
    if not 1 <= args.batch_size <= 20: raise ConflictError("--batch-size debe estar entre 1 y 20")
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
