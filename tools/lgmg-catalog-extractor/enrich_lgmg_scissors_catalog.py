#!/usr/bin/env python3
"""Enriquecimiento fail-closed de las 21 tijeras LGMG (solo Windows)."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
TOOL_NAME = "enrich_lgmg_scissors_catalog"
TOOL_VERSION = "1.0.0"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DATASHEET_BYTES = 10 * 1024 * 1024
UPLOAD_LIMIT = 20
UPLOAD_WINDOW_SECONDS = 600
OUTPUT_NAMES = (
    "enrichment-products.csv", "enrichment-datasheets.csv", "enrichment-actions.csv",
    "enrichment-errors.csv", "enrichment-summary.json", "enrichment-summary.txt",
    "enrichment-manifest.json", "README-enrichment.txt",
)
PATCH_FIELDS = frozenset({"working_height_m", "maximum_load_capacity_kg",
    "machine_weight_kg", "power_source", "technical_sheet"})
APPROVED_ROWS = (
    ("S0607E-2", "S0607E-2", "7.8", 230, 1550), ("S0808E-2", "S0808E-2", "9.8", 230, 2160),
    ("S0812E-2", "S0812E-2", "10", 450, 2260), ("S1012E-2", "S1012E-2", "12", 320, 2925),
    ("S1212E-2", "S1212E-2", "14", 320, 2940), ("S1413E-2", "S1413E-2", "15.8", 320, 3430),
    ("SS0407ER", "SS0407ER", "5.6", 240, 880), ("SS0507E", "SS0507E", "6.3", 230, 985),
    ("SS0607E", "SS0607E", "7.5", 230, 1335), ("S0607EⅡ", "S0607E", "7.8", 230, 1610),
    ("S0808EⅡ", "S0808E", "9.8", 230, 2200), ("S0812EⅡ", "S0812E", "10", 450, 2318),
    ("S1012EⅡ", "S1012E", "12", 320, 2995), ("S1212EⅡ", "S1212E", "14", 320, 2970),
    ("S1413EⅡ", "S1413E", "15.8", 320, 3500), ("S0607Ⅱ", "S0607", "7.8", 230, 1610),
    ("S0808Ⅱ", "S0808", "9.8", 230, 2200), ("S0812Ⅱ", "S0812", "10", 450, 2395),
    ("S1012Ⅱ", "S1012", "12", 320, 2995), ("S1212Ⅱ", "S1212", "14", 320, 2970),
    ("S1413Ⅱ", "S1413", "15.8", 320, 3500),
)


class SafeError(Exception):
    """Error controlado que nunca incluye credenciales ni cuerpos binarios."""

    def __init__(self, message="", *, failure_stage="input_validation",
            failure_code="INPUT_VALIDATION_FAILED", failed_product=None):
        super().__init__(message)
        self.failure_stage = failure_stage
        self.failure_code = failure_code
        self.failed_product = failed_product


class RatePause(SafeError):
    def __init__(self, verdict, retry_after=None):
        super().__init__(verdict); self.verdict, self.retry_after = verdict, retry_after


def _audit_module():
    path = Path(__file__).with_name("audit_lgmg_scissors_technical_data.py")
    spec = importlib.util.spec_from_file_location("_lgmg_enrichment_audit", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def approved_catalog(tool_dir=None):
    audit = _audit_module()
    provenance = audit.closed_catalog(Path(tool_dir) if tool_dir else None)
    by_source = {r[0]: r for r in APPROVED_ROWS}
    if len(APPROVED_ROWS) != 21 or len(by_source) != 21 or len({r[1] for r in APPROVED_ROWS}) != 21:
        raise SafeError("La tabla aprobada no contiene 21 filas únicas")
    if tuple(by_source) != tuple(x["source_model"] for x in provenance):
        raise SafeError("La tabla aprobada no coincide con MODEL_SOURCE_KEYS")
    result = []
    for base in provenance:
        source, target, height, capacity, weight = by_source[base["source_model"]]
        if target != base["target_model"]:
            raise SafeError("La tabla aprobada no coincide con SOURCE_TARGET_MODELS")
        result.append({**base, "working_height_m": float(height),
            "maximum_load_capacity_kg": capacity, "machine_weight_kg": weight,
            "power_source": "electric_24v", "datasheet_name": f"Ficha técnica LGMG {target}"})
    return tuple(result)


def normalize_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "http" or parsed.netloc not in ("localhost:5000", "127.0.0.1:5000")
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        raise SafeError("--api-base-url debe ser exactamente un origen local autorizado")
    return f"http://{parsed.hostname}:5000"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise SafeError("Redirección HTTP rechazada")


class LocalApiClient:
    STATIC_GETS = frozenset({
        "/api/categories?include_inactive=true", "/api/brands?include_inactive=true",
        "/api/products?include_unpublished=true", "/api/product-images",
        "/api/product-specs", "/api/technical-sheets",
    })
    DYNAMIC_GET = re.compile(r"/api/(?:products/\d+|technical-sheets/\d+/file)\Z")

    def __init__(self, origin, token, apply=False, opener=None):
        self.origin, self._token, self.apply = normalize_origin(origin), token, apply
        self.opener = opener or urllib.request.build_opener(NoRedirect()); self.calls = []

    def _validate(self, method, path, payload):
        if method == "GET":
            if path not in self.STATIC_GETS and not self.DYNAMIC_GET.fullmatch(path):
                raise SafeError("Destino GET no permitido")
        elif method == "POST":
            if not self.apply or path != "/api/technical-sheets": raise SafeError("Destino POST no permitido")
        elif method == "PATCH":
            if not self.apply or not re.fullmatch(r"/api/products/\d+", path): raise SafeError("Destino PATCH no permitido")
            if not isinstance(payload, dict) or not payload or not set(payload) <= PATCH_FIELDS:
                raise SafeError("Payload PATCH no permitido")
            if any(value is None for value in payload.values()):
                raise SafeError("Payload PATCH no permite null")
            if any(isinstance(payload.get(k), (str, bool)) for k in PATCH_FIELDS - {"power_source"} if k in payload):
                raise SafeError("Los campos numéricos deben ser números JSON")
            if "power_source" in payload and payload["power_source"] != "electric_24v": raise SafeError("Energía no permitida")
        else: raise SafeError("Método HTTP no permitido")

    def request(self, method, path, payload=None, body=None, content_type=None, binary=False, expected_content_type=None):
        self._validate(method, path, payload)
        if payload is not None: body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"Accept": (expected_content_type or "application/octet-stream") if binary else "application/json",
            "Authorization": "Bearer " + self._token}
        if content_type: headers["Content-Type"] = content_type
        elif payload is not None: headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(self.origin + path, data=body, headers=headers, method=method)
        self.calls.append((method, path))
        try:
            response = self.opener.open(request, timeout=15)
            if not response.geturl().startswith(self.origin + "/api/"): raise SafeError("Cambio de origen rechazado")
            raw = response.read((MAX_DATASHEET_BYTES if binary else MAX_RESPONSE_BYTES) + 1)
            if len(raw) > (MAX_DATASHEET_BYTES if binary else MAX_RESPONSE_BYTES): raise SafeError("Respuesta demasiado grande")
            if binary:
                if response.headers.get_content_type() != expected_content_type: raise SafeError("MIME descargado inválido")
                return raw
            if response.headers.get_content_type() != "application/json": raise SafeError("MIME JSON inválido")
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                value = exc.headers.get("Retry-After"); retry = int(value) if value and value.isdigit() else None
                raise RatePause("PAUSED_RATE_LIMIT", retry) from None
            raise SafeError(f"HTTP {exc.code} en {method} {path}") from None
        except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise SafeError(f"Respuesta local inválida: {type(exc).__name__}") from None

    def get_json(self, path): return self.request("GET", path)
    def download(self, sheet_id, expected_content_type="application/pdf"):
        return self.request("GET", f"/api/technical-sheets/{int(sheet_id)}/file", binary=True,
            expected_content_type=expected_content_type)
    def patch_product(self, product_id, payload): return self.request("PATCH", f"/api/products/{int(product_id)}", payload=payload)
    def post_datasheet(self, name, filename, data):
        if Path(filename).name != filename or any(c in filename for c in ('"', "\r", "\n")): raise SafeError("Nombre original inseguro")
        boundary = "----jem-enrichment-" + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\n{name}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            'Content-Type: application/pdf\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
        return self.request("POST", "/api/technical-sheets", body=body, content_type="multipart/form-data; boundary=" + boundary)


def extract_list(value, label):
    if isinstance(value, dict) and isinstance(value.get("results"), list): value = value["results"]
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value): raise SafeError(f"Contrato inválido: {label}")
    return value


def read_rate_limit(repo_root):
    data = json.loads((Path(repo_root) / "backend-dotnet/JemNexus.Api/appsettings.json").read_text(encoding="utf-8"))
    upload = data.get("RateLimiting", {}).get("Upload", {})
    if upload != {"PermitLimit": UPLOAD_LIMIT, "WindowSeconds": UPLOAD_WINDOW_SECONDS}:
        raise SafeError("La configuración Upload cambió")
    return upload


def _number(value):
    if isinstance(value, bool) or value is None or value == "": return None
    try: return Decimal(str(value))
    except Exception: return None


_COMPOUND_HEIGHT = re.compile(
    r"(?P<inside>[0-9]+(?:[.,][0-9]+)?)\s*m?\s*/\s*"
    r"(?P<outside>[0-9]+(?:[.,][0-9]+)?)\s*m\s*"
    r"\(\s*dentro\s*/\s*fuera\s*\)\Z", re.I)


def _working_height(value, audit):
    """Parse only a metric scalar or the approved inside/outside cell shape."""
    original = str(value)
    match = _COMPOUND_HEIGHT.fullmatch(original)
    if match:
        inside = Decimal(match.group("inside").replace(",", "."))
        outside = Decimal(match.group("outside").replace(",", "."))
        if not inside.is_finite() or not outside.is_finite() or inside <= 0 or outside <= 0 or inside < outside:
            return None
        return inside, outside, original
    simple = audit.metric_number(original, "m")
    if simple is None: return None
    inside = Decimal(simple)
    if not inside.is_finite() or inside <= 0: return None
    return inside, None, original


def _evidence_error(code, product):
    raise SafeError(f"Evidencia incompatible: {product['source_model']}",
        failure_stage="evidence_validation", failure_code=code,
        failed_product=product["target_model"])


def validate_evidence(selected, specifications):
    audit = _audit_module(); grouped = {}
    for row in specifications: grouped.setdefault(row.get("source_key"), []).append(row)
    evidence_rows = []
    for product in selected:
        specs = grouped.get(product["source_key"], [])
        heights = []
        for row in specs:
            label = audit.normalized(row.get("source_label"))
            if label in {"altura maxima de trabajo", "max. altura de trabajo", "maximum working height", "max. working height"}:
                parsed = _working_height(row.get("source_value", ""), audit)
                if parsed: heights.append((*parsed, row))
        approved_height = Decimal(str(product["working_height_m"]))
        if not heights or {inside for inside, _, _, _ in heights} != {approved_height}:
            _evidence_error("EVIDENCE_WORKING_HEIGHT_INCOMPATIBLE", product)
        caps = audit.capacity_evidence(specs, str(product["maximum_load_capacity_kg"]))
        if not caps: _evidence_error("EVIDENCE_CAPACITY_INCOMPATIBLE", product)
        weights = []
        allowed_weight = re.compile(r"^(?:peso de la maquina|peso de maquina|peso total de la maquina|machine weight|overall machine weight)(?: \(ce/ansi\)| \(ce\))?$")
        for row in specs:
            if allowed_weight.fullmatch(audit.normalized(row.get("source_label"))):
                value = audit.metric_number(row.get("source_value", ""), "kg")
                if value: weights.append((Decimal(value), row))
        if {v for v, _ in weights} != {Decimal(product["machine_weight_kg"])}:
            _evidence_error("EVIDENCE_MACHINE_WEIGHT_INCOMPATIBLE", product)
        power = [r for r in specs if re.search(r"(?:24\s*v|24v)", str(r.get("source_value", "")), re.I)
            and audit.normalized(r.get("source_label")) in {"fuente de potencia", "fuente de alimentacion", "power source", "bateria de plomo-acido", "lead-acid battery"}]
        if not power: _evidence_error("EVIDENCE_POWER_24V_MISSING", product)
        evidence_rows.append({"source_model": product["source_model"], "height_labels": " | ".join(r.get("source_label", "") for _, _, _, r in heights),
            "height_values": " | ".join(original for _, _, original, _ in heights),
            "height_inside_m": " | ".join(str(inside) for inside, _, _, _ in heights),
            "height_outside_m": " | ".join("" if outside is None else str(outside) for _, outside, _, _ in heights),
            "capacity_labels": " | ".join(r.get("source_label", "") for r in caps),
            "capacity_values": " | ".join(r.get("source_value", "") for r in caps),
            "weight_labels": " | ".join(r.get("source_label", "") for _, r in weights),
            "weight_values": " | ".join(r.get("source_value", "") for _, r in weights)})
    return evidence_rows


DIRECT_FIELDS = ("working_height_m", "maximum_load_capacity_kg", "machine_weight_kg", "power_source")
SHEET_FIELDS = frozenset({"id", "name", "original_file_name", "content_type", "size_bytes",
    "created_at", "updated_at", "file_url"})
MUTABLE_PRODUCT_FIELDS = frozenset((*DIRECT_FIELDS, "technical_sheet", "updated_at", "updated_by"))


@dataclass(frozen=True)
class ProductPlan:
    approved: dict
    datasheet: dict
    summary: dict
    detail: dict
    direct_patch: dict
    associated_sheet_id: int | None
    resolved_sheet: dict | None
    sheet_status: str


def validate_direct_fields(detail, approved):
    """Validate only direct technical values; sheet resolution is deliberately separate."""
    payload = {}
    for key in DIRECT_FIELDS:
        expected, current = approved[key], detail.get(key)
        if current in (None, ""):
            payload[key] = expected
        elif (key != "power_source" and _number(current) == Decimal(str(expected))) or current == expected:
            continue
        else:
            raise SafeError(f"Conflicto no vacío en {key}")
    return payload


def build_minimal_patch(detail, direct_patch, sheet_id=None):
    payload = dict(direct_patch)
    current = detail.get("technical_sheet")
    current_id = current.get("id") if isinstance(current, dict) else current
    if current_id in (None, ""):
        if sheet_id is not None:
            payload["technical_sheet"] = int(sheet_id)
    elif sheet_id is not None and int(current_id) != int(sheet_id):
        raise SafeError("Conflicto no vacío en technical_sheet")
    if not set(payload) <= PATCH_FIELDS or payload.get("technical_sheet", 1) is None:
        raise SafeError("PATCH mínimo inválido")
    return payload


def minimal_patch(detail, approved, sheet_id=None):
    """Compatibility helper whose missing sheet never creates technical_sheet:null."""
    return build_minimal_patch(detail, validate_direct_fields(detail, approved), sheet_id)


def validate_sheet_contract(sheet):
    if not isinstance(sheet, dict) or set(sheet) != SHEET_FIELDS:
        raise SafeError("Contrato de ficha técnica inválido")
    if not isinstance(sheet["id"], int) or isinstance(sheet["size_bytes"], bool):
        raise SafeError("Tipos de ficha técnica inválidos")


def sheet_hash(client, sheet, cache, actions=None, product_id=None):
    sheet_id = sheet["id"]
    if sheet_id not in cache:
        cache[sheet_id] = hashlib.sha256(client.download(sheet_id, sheet["content_type"])).hexdigest()
        if actions is not None:
            actions.append({"method": "GET", "path": f"/api/technical-sheets/{sheet_id}/file",
                "product_id": product_id, "sheet_id": sheet_id, "result": "hash_verified"})
    return cache[sheet_id]


def resolve_existing_sheet(client, sheets, approved, datasheet, cache, actions=None, product_id=None):
    """Resolve all related candidates by real content, never by size/MIME alone."""
    name, filename, expected_hash = approved["datasheet_name"], datasheet["file_name"], datasheet["sha256"]
    related = []
    for sheet in sheets:
        validate_sheet_contract(sheet)
        administrative = sheet["name"] == name or sheet["original_file_name"] == filename
        compatible = sheet["content_type"] == "application/pdf" and sheet["size_bytes"] == datasheet["size_bytes"]
        if administrative or compatible:
            digest = sheet_hash(client, sheet, cache, actions, product_id) if compatible else None
            # Same size/MIME but unrelated name and unequal hash is an unrelated sheet.
            if administrative or digest == expected_hash:
                related.append((sheet, digest))
    exact = [(s, h) for s, h in related if s["name"] == name and s["original_file_name"] == filename
        and s["content_type"] == "application/pdf" and s["size_bytes"] == datasheet["size_bytes"] and h == expected_hash]
    if len(exact) > 1:
        raise SafeError("Varias fichas exactas")
    for sheet, digest in related:
        if exact and sheet["id"] == exact[0][0]["id"]:
            continue
        if sheet["name"] == name or sheet["original_file_name"] == filename or digest == expected_hash:
            raise SafeError("Colisión de ficha técnica")
    return exact[0][0] if exact else None


def _ref_id(value):
    return value.get("id") if isinstance(value, dict) else value


def preflight(client, state, catalog, datasheets, actions=None):
    actions = actions if actions is not None else []
    brands = [b for b in state["brands"] if b.get("name") == "LGMG" and b.get("is_active") is not False]
    roots = [c for c in state["categories"] if c.get("name") == "Maquinaria" and c.get("is_active") is not False]
    cats = [c for c in state["categories"] if c.get("name") == "Elevadores tipo tijera eléctricos" and c.get("is_active") is not False]
    if len(brands) != 1 or len(roots) != 1 or len(cats) != 1:
        raise SafeError("Marca/categoría activa ausente o ambigua")
    if roots[0].get("parent") is not None or roots[0].get("product_type") != "machinery":
        raise SafeError("Jerarquía raíz incorrecta")
    if _ref_id(cats[0].get("parent")) != roots[0].get("id") or cats[0].get("product_type") != "machinery":
        raise SafeError("Jerarquía de subcategoría incorrecta")
    cache, result = {}, []
    # Establish a content baseline for every pre-existing sheet before writes.
    for sheet in state["sheets"]:
        validate_sheet_contract(sheet)
        sheet_hash(client, sheet, cache, actions)
    for approved, datasheet in zip(catalog, datasheets):
        matches = [p for p in state["products"] if p.get("model") == approved["target_model"] and p.get("name") == approved["target_name"]]
        if len(matches) != 1: raise SafeError("Producto ausente o ambiguo")
        summary = matches[0]; detail = state["details"].get(summary["id"])
        if not detail: raise SafeError("Detalle de producto ausente")
        if _ref_id(detail.get("brand")) != brands[0]["id"] or _ref_id(detail.get("category") or detail.get("subcategory")) != cats[0]["id"]:
            raise SafeError("Marca o subcategoría incorrecta")
        if detail.get("name") != approved["target_name"] or detail.get("model") != approved["target_model"]:
            raise SafeError("Identidad final incorrecta")
        if detail.get("is_published") is not False or detail.get("is_featured") is not False: raise SafeError("Producto publicado o destacado")
        if any(detail.get(k) not in (None, "") for k in ("terrain_type", "year", "hours_meter")): raise SafeError("Campo preservado no vacío")
        images = [x for x in state["images"] if _ref_id(x.get("product")) == summary["id"]]
        if len(images) != 1 or sum(x.get("is_main") is True for x in images) != 1: raise SafeError("Imagen principal única incumplida")
        direct = validate_direct_fields(detail, approved)
        resolved = resolve_existing_sheet(client, state["sheets"], approved, datasheet, cache, actions, summary["id"])
        associated = _ref_id(detail.get("technical_sheet"))
        if associated not in (None, ""):
            by_id = next((s for s in state["sheets"] if s["id"] == associated), None)
            if by_id is None or resolved is None or resolved["id"] != associated:
                raise SafeError("Ficha asociada incorrecta")
            status = "already_associated"
        else:
            status = "reuse_required" if resolved else "upload_required"
        result.append(ProductPlan(approved, datasheet, summary, detail, direct,
            int(associated) if associated not in (None, "") else None, resolved, status))
    return tuple(result), cache


def resolve_sheet(client, sheets, approved, datasheet, media_root, cache=None, actions=None, product_id=None):
    existing = resolve_existing_sheet(client, sheets, approved, datasheet, cache if cache is not None else {}, actions, product_id)
    if existing: return existing, True
    path = Path(media_root).joinpath(*datasheet["relative_path"].split("/"))
    return client.post_datasheet(approved["datasheet_name"], datasheet["file_name"], path.read_bytes()), False


def snapshot(client, catalog):
    state = {"categories": extract_list(client.get_json("/api/categories?include_inactive=true"), "categorías"),
        "brands": extract_list(client.get_json("/api/brands?include_inactive=true"), "marcas"),
        "products": extract_list(client.get_json("/api/products?include_unpublished=true"), "productos"),
        "images": extract_list(client.get_json("/api/product-images"), "imágenes"),
        "specs": extract_list(client.get_json("/api/product-specs"), "especificaciones"),
        "sheets": extract_list(client.get_json("/api/technical-sheets"), "fichas")}
    wanted = {x["target_model"] for x in catalog}
    state["details"] = {p["id"]: client.get_json(f"/api/products/{p['id']}")
        for p in state["products"] if p.get("model") in wanted}
    return state


def immutable_projection(detail):
    return {k: v for k, v in detail.items() if k not in MUTABLE_PRODUCT_FIELDS}


def by_id(rows):
    return {row["id"]: row for row in rows}


def verify_final(client, before, after, plans, cache, created_ids):
    if by_id(before["categories"]) != by_id(after["categories"]) or by_id(before["brands"]) != by_id(after["brands"]):
        raise SafeError("Categorías o marcas cambiaron")
    if by_id(before["images"]) != by_id(after["images"]) or by_id(before["specs"]) != by_id(after["specs"]):
        raise SafeError("Imágenes o ProductSpecs cambiaron")
    before_products, after_products = by_id(before["products"]), by_id(after["products"])
    if set(before_products) != set(after_products): raise SafeError("Conjunto de productos cambió")
    selected = {p.summary["id"] for p in plans}
    for product_id, old in before_products.items():
        new = after_products[product_id]
        if (immutable_projection(old) != immutable_projection(new) if product_id in selected else old != new):
            raise SafeError("Colección de productos cambió")
    for product_id, old in before["details"].items():
        new = after["details"].get(product_id)
        if new is None or immutable_projection(old) != immutable_projection(new):
            raise SafeError("Campo comercial concurrente modificado")
    old_sheets, new_sheets = by_id(before["sheets"]), by_id(after["sheets"])
    if not set(old_sheets) <= set(new_sheets) or set(new_sheets) - set(old_sheets) != set(created_ids):
        raise SafeError("Conjunto de fichas cambió fuera del alcance")
    for sheet_id, old in old_sheets.items():
        if old != new_sheets[sheet_id]: raise SafeError("Ficha previa modificada")
    current_hashes = {}
    for sheet_id in old_sheets:
        if sheet_hash(client, new_sheets[sheet_id], current_hashes) != cache[sheet_id]:
            raise SafeError("Contenido de ficha previa modificado")
    for plan in plans:
        detail = after["details"][plan.summary["id"]]
        associated = _ref_id(detail.get("technical_sheet"))
        sheet = new_sheets.get(associated)
        if not sheet: raise SafeError("Asociación final ausente")
        expected = resolve_existing_sheet(client, list(new_sheets.values()), plan.approved, plan.datasheet, cache)
        if expected is None or expected["id"] != associated or build_minimal_patch(detail, validate_direct_fields(detail, plan.approved), associated):
            raise SafeError("Verificación final incompleta")

def excel(value):
    text = "" if value is None else (str(value).lower() if isinstance(value, bool) else str(value))
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_csv(path, fields, rows):
    stream = io.StringIO(newline=""); writer = csv.DictWriter(stream, fields, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader(); writer.writerows({f: excel(row.get(f)) for f in fields} for row in rows)
    path.write_bytes(b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8"))


def write_outputs(output, result):
    output = Path(output); parent = output.parent; parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".enrichment-staging-", dir=parent))
    try:
        products = result.get("products", []); sheets = result.get("datasheets", []); actions = result.get("actions", []); errors = result.get("errors", [])
        write_csv(staging / OUTPUT_NAMES[0], ["source_model", "target_model", "product_id", "status", "working_height_m", "maximum_load_capacity_kg", "machine_weight_kg", "power_source", "direct_fields_pending", "technical_sheet_status", "final_verified"], products)
        write_csv(staging / OUTPUT_NAMES[1], ["source_model", "target_model", "product_id", "datasheet_name", "file_name", "sha256", "size_bytes", "content_type", "sheet_id", "status", "hash_verified", "associated"], sheets)
        write_csv(staging / OUTPUT_NAMES[2], ["order", "method", "path", "product_id", "sheet_id", "result"], actions)
        write_csv(staging / OUTPUT_NAMES[3], ["product", "error"], errors)
        summary = {k: v for k, v in result.items() if k not in {"products", "datasheets", "actions", "errors"}}
        summary.update({"zero_products_created_or_deleted": True, "zero_product_specs_created": True,
            "zero_images_modified": True, "zero_publication": True, "zero_terrain_year_hours_description_changes": True,
            "zero_credentials_persisted": True})
        (staging / OUTPUT_NAMES[4]).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[5]).write_text("\n".join(f"{k}: {v}" for k, v in summary.items()) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[7]).write_text("Informes del enriquecimiento controlado LGMG. No contienen credenciales ni PDF.\n", encoding="utf-8")
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in staging.iterdir()}
        manifest = {"tool": TOOL_NAME, "version": TOOL_VERSION, "files": hashes,
            "input_hashes": result.get("input_hashes", {}), "credentials_persisted": False}
        (staging / OUTPUT_NAMES[6]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if set(p.name for p in staging.iterdir()) != set(OUTPUT_NAMES): raise SafeError("Conjunto de informes incompleto")
        if output.exists():
            if any(output.iterdir()): raise SafeError("La salida debe estar vacía")
            output.rmdir()
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True); raise


def _report_rows(plans):
    products, datasheets = [], []
    for plan in plans:
        products.append({"source_model": plan.approved["source_model"], "target_model": plan.approved["target_model"],
            "product_id": plan.summary["id"], "status": plan.sheet_status,
            "working_height_m": plan.approved["working_height_m"],
            "maximum_load_capacity_kg": plan.approved["maximum_load_capacity_kg"],
            "machine_weight_kg": plan.approved["machine_weight_kg"], "power_source": plan.approved["power_source"],
            "direct_fields_pending": "|".join(plan.direct_patch), "technical_sheet_status": plan.sheet_status,
            "final_verified": False})
        datasheets.append({"source_model": plan.approved["source_model"], "target_model": plan.approved["target_model"],
            "product_id": plan.summary["id"], "datasheet_name": plan.approved["datasheet_name"],
            "file_name": plan.datasheet["file_name"], "sha256": plan.datasheet["sha256"],
            "size_bytes": plan.datasheet["size_bytes"], "content_type": "application/pdf",
            "sheet_id": plan.resolved_sheet["id"] if plan.resolved_sheet else "", "status": plan.sheet_status,
            "hash_verified": bool(plan.resolved_sheet), "associated": plan.sheet_status == "already_associated"})
    return products, datasheets


def _safe_failure(result, plans, index, exc):
    wrote = bool(result["created_datasheet_ids"] or result["updated_product_ids"] or
        any(action.get("method") in {"POST", "PATCH"} for action in result["actions"]))
    result["verdict"] = "PARTIAL_FAILURE" if wrote else "CONFLICT"
    result["conflicts"] += 1
    result["failed_product"] = plans[index].approved["target_model"] if index < len(plans) else "final_verification"
    safe = exc if isinstance(exc, SafeError) else SafeError()
    result.update({"failure_stage": safe.failure_stage,
        "failure_code": safe.failure_code})
    result["errors"].append({"product": result["failed_product"], "error": safe.failure_code})
    if index < len(plans):
        result["products"][index]["status"] = "partial_failure" if wrote else "conflict"
        result["datasheets"][index]["status"] = "partial_failure" if wrote else "conflict"
        for later in range(index + 1, len(plans)):
            result["products"][later]["status"] = "not_started"
            result["datasheets"][later]["status"] = "not_started"
    return 1, result


def _validate_uploaded_sheet(sheet, plan):
    validate_sheet_contract(sheet)
    if (sheet["name"] != plan.approved["datasheet_name"] or
            sheet["original_file_name"] != plan.datasheet["file_name"] or
            sheet["content_type"] != "application/pdf" or
            sheet["size_bytes"] != plan.datasheet["size_bytes"]):
        raise SafeError("UPLOADED_SHEET_METADATA_MISMATCH")


def orchestrate(client, before, catalog, datasheets, media_root, apply=False):
    """Run a complete immutable preflight, preserving progress on every failure."""
    actions = []
    plans, cache = preflight(client, before, catalog, datasheets, actions)
    products, sheet_rows = _report_rows(plans)
    result = {"mode": "apply" if apply else "dry-run", "verdict": "DRY_RUN_APPROVED",
        "products_examined": len(plans), "pending": sum(bool(p.direct_patch) or p.sheet_status != "already_associated" for p in plans),
        "updated": 0, "already_enriched": 0, "datasheets_pending": sum(p.sheet_status == "upload_required" for p in plans),
        "datasheets_uploaded": 0, "datasheets_reused": 0, "conflicts": 0,
        "updated_product_ids": [], "created_datasheet_ids": [], "failed_product": None,
        "retry_after_seconds": None, "final_verification": False, "products": products,
        "datasheets": sheet_rows, "actions": actions, "errors": []}
    if not apply: return 0, result
    sheets, uploads = list(before["sheets"]), 0
    for index, plan in enumerate(plans):
        product_row, sheet_row = products[index], sheet_rows[index]
        try:
            sheet = plan.resolved_sheet
            if sheet is None:
                if uploads >= UPLOAD_LIMIT:
                    product_row["status"] = sheet_row["status"] = "pending_upload_window"
                    for later in range(index + 1, len(plans)):
                        products[later]["status"] = sheet_rows[later]["status"] = "not_started"
                    result.update({"verdict": "PAUSED_UPLOAD_WINDOW", "retry_after_seconds": UPLOAD_WINDOW_SECONDS,
                        "failed_product": plan.approved["target_model"]})
                    return 2, result
                path = Path(media_root).joinpath(*plan.datasheet["relative_path"].split("/")); data = path.read_bytes()
                sheet = client.post_datasheet(plan.approved["datasheet_name"], plan.datasheet["file_name"], data)
                uploads += 1; result["datasheets_uploaded"] += 1
                # Preserve the created ID as soon as the POST contract provides one.
                if isinstance(sheet, dict) and isinstance(sheet.get("id"), int):
                    result["created_datasheet_ids"].append(sheet["id"]); sheet_row["sheet_id"] = sheet["id"]
                actions.append({"method": "POST", "path": "/api/technical-sheets", "product_id": plan.summary["id"],
                    "sheet_id": sheet.get("id") if isinstance(sheet, dict) else "", "result": "uploaded"})
                product_row["status"] = sheet_row["status"] = "uploaded"
                _validate_uploaded_sheet(sheet, plan); sheets.append(sheet)
                digest = sheet_hash(client, sheet, cache, actions, plan.summary["id"])
                if digest != plan.datasheet["sha256"]: raise SafeError("UPLOADED_SHEET_HASH_MISMATCH")
                sheet_row["status"] = "hash_verified"; sheet_row["hash_verified"] = True
            elif plan.sheet_status == "reuse_required":
                result["datasheets_reused"] += 1; sheet_row["status"] = "hash_verified"

            fresh = client.get_json(f"/api/products/{plan.summary['id']}")
            actions.append({"method": "GET", "path": f"/api/products/{plan.summary['id']}", "product_id": plan.summary["id"],
                "sheet_id": sheet["id"], "result": "pre_patch_revalidated"})
            if immutable_projection(fresh) != immutable_projection(plan.detail):
                raise SafeError("PRE_PATCH_IMMUTABLE_CONFLICT")
            fresh_direct = validate_direct_fields(fresh, plan.approved)
            payload = build_minimal_patch(fresh, fresh_direct, sheet["id"])
            if payload:
                client.patch_product(plan.summary["id"], payload)
                result["updated"] += 1; result["updated_product_ids"].append(plan.summary["id"])
                actions.append({"method": "PATCH", "path": f"/api/products/{plan.summary['id']}", "product_id": plan.summary["id"],
                    "sheet_id": sheet["id"], "result": "associated"})
                product_row["status"] = sheet_row["status"] = "associated"
            else: result["already_enriched"] += 1
            verified = client.get_json(f"/api/products/{plan.summary['id']}")
            actions.append({"method": "GET", "path": f"/api/products/{plan.summary['id']}", "product_id": plan.summary["id"],
                "sheet_id": sheet["id"], "result": "verified"})
            if build_minimal_patch(verified, validate_direct_fields(verified, plan.approved), sheet["id"]):
                raise SafeError("IMMEDIATE_VERIFICATION_FAILED")
            product_row["status"] = sheet_row["status"] = "verified"
            sheet_row.update({"sheet_id": sheet["id"], "hash_verified": True, "associated": True})
        except RatePause as pause:
            product_row["status"] = sheet_row["status"] = "pending_upload_window"
            result.update({"verdict": pause.verdict, "retry_after_seconds": pause.retry_after,
                "failed_product": plan.approved["target_model"]})
            return 2, result
        except Exception as exc:
            return _safe_failure(result, plans, index, exc)
    try:
        after = snapshot(client, catalog)
        verify_final(client, before, after, plans, cache, result["created_datasheet_ids"])
    except Exception as exc:
        return _safe_failure(result, plans, len(plans), exc)
    for row in products: row["final_verified"] = True
    result["final_verification"] = True
    result["verdict"] = "IDEMPOTENT_VERIFIED" if result["updated"] == 0 and result["datasheets_uploaded"] == 0 else "APPLY_VERIFIED"
    return 0, result


def validate_datasheet_sizes(datasheets):
    if any(not isinstance(x.get("size_bytes"), int) or isinstance(x.get("size_bytes"), bool)
            or x["size_bytes"] < 0 or x["size_bytes"] > MAX_DATASHEET_BYTES for x in datasheets):
        raise SafeError("DATASHEET_SIZE_LIMIT")

def run(plan_input, media_input, base_url, output, apply=False, confirmed=False, token="", client_factory=LocalApiClient, platform=None):
    if apply != confirmed: raise SafeError("Aplicación requiere ambas confirmaciones")
    if (platform or sys.platform) != "win32": raise SafeError("Esta herramienta solo puede ejecutarse en Windows")
    audit = _audit_module(); plan_root, media_root = Path(plan_input), Path(media_input)
    audit.safe_paths(plan_root, media_root, Path(output))
    client = None; plan = media = None
    try:
        plan, media = audit.validate_inputs(plan_root, media_root)
        catalog = approved_catalog(); selected = audit.select_products(plan["rows"]["import-products.csv"], catalog)
        datasheets = audit.validate_datasheets(selected, plan, media, media_root)
        if len(datasheets) != 21 or len({x["sha256"] for x in datasheets}) != 21:
            raise SafeError("Se requieren 21 PDF físicos únicos")
        validate_datasheet_sizes(datasheets)
        validate_evidence(selected, plan["rows"]["import-specifications.csv"])
        read_rate_limit(Path(__file__).resolve().parents[2]); client = client_factory(normalize_origin(base_url), token, apply=apply)
        before = snapshot(client, catalog)
        code, result = orchestrate(client, before, catalog, datasheets, media_root, apply)
    except Exception as exc:
        safe = exc if isinstance(exc, SafeError) else SafeError()
        result = {"mode": "apply" if apply else "dry-run", "verdict": "CONFLICT", "conflicts": 1,
            "failure_stage": safe.failure_stage, "failure_code": safe.failure_code,
            "failed_product": safe.failed_product, "products": [], "datasheets": [], "actions": [],
            "errors": [{"product": safe.failed_product or "", "error": safe.failure_code}]}
        code = 1
    result["input_hashes"] = {"plan": plan["manifest"].get("combined_fingerprint_sha256") if plan else None,
        "media": media["manifest"].get("combined_fingerprint_sha256") if media else None}
    for order, action in enumerate(result.get("actions", []), 1): action["order"] = order
    result["http_methods_and_paths"] = client.calls if client else []
    result["post_requests"] = sum(method == "POST" for method, _ in result["http_methods_and_paths"])
    result["patch_requests"] = sum(method == "PATCH" for method, _ in result["http_methods_and_paths"])
    write_outputs(output, result)
    if code == 1 and result.get("failure_code"):
        print(f"ERROR: {result['failure_code']}", file=sys.stderr)
    return code

def access_token(environ=os.environ):
    token = environ.get(TOKEN_ENV, "")
    if not token or any(c in token for c in "\r\n"): raise SafeError(f"Defina {TOKEN_ENV} en el entorno")
    return token


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-input", required=True, type=Path); parser.add_argument("--media-input", required=True, type=Path)
    parser.add_argument("--api-base-url", required=True); parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--apply", action="store_true"); parser.add_argument("--confirm-lgmg-scissors-enrichment", action="store_true", dest="confirmed")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try: return run(args.plan_input, args.media_input, args.api_base_url, args.output_dir, args.apply, args.confirmed, access_token())
    except Exception as exc:
        code = exc.failure_code if isinstance(exc, SafeError) else "UNEXPECTED_FAILURE"
        print(f"ERROR: {code}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
