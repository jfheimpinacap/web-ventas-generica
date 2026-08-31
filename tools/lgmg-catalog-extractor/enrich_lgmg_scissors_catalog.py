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
MAX_DATASHEET_BYTES = 20 * 1024 * 1024
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
    DYNAMIC_GET = re.compile(r"/api/(?:products/\d+|technical-sheets/\d+/download)\Z")

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
            if any(isinstance(payload.get(k), (str, bool)) for k in PATCH_FIELDS - {"power_source"} if k in payload):
                raise SafeError("Los campos numéricos deben ser números JSON")
            if "power_source" in payload and payload["power_source"] != "electric_24v": raise SafeError("Energía no permitida")
        else: raise SafeError("Método HTTP no permitido")

    def request(self, method, path, payload=None, body=None, content_type=None, binary=False):
        self._validate(method, path, payload)
        if payload is not None: body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"Accept": "application/pdf" if binary else "application/json",
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
                if response.headers.get_content_type() != "application/pdf": raise SafeError("MIME descargado inválido")
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
    def download(self, sheet_id): return self.request("GET", f"/api/technical-sheets/{int(sheet_id)}/download", binary=True)
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
                value = audit.metric_number(row.get("source_value", ""), "m")
                if value: heights.append((Decimal(value), row))
        if not heights or max(v for v, _ in heights) != Decimal(str(product["working_height_m"])):
            raise SafeError(f"Evidencia de altura incompatible: {product['source_model']}")
        # Si la fuente distingue interior/exterior, ambas filas deben estar presentes.
        labels = [audit.normalized(r.get("source_label")) for _, r in heights]
        if any("interior" in x or "exterior" in x for x in labels) and not (any("interior" in x for x in labels) and any("exterior" in x for x in labels)):
            raise SafeError("Altura interior/exterior incompleta")
        caps = audit.capacity_evidence(specs, str(product["maximum_load_capacity_kg"]))
        if not caps: raise SafeError(f"Evidencia de capacidad incompatible: {product['source_model']}")
        weights = []
        allowed_weight = re.compile(r"^(?:peso de la maquina|peso total de la maquina|machine weight|overall machine weight)(?: \(ce/ansi\)| \(ce\))?$")
        for row in specs:
            if allowed_weight.fullmatch(audit.normalized(row.get("source_label"))):
                value = audit.metric_number(row.get("source_value", ""), "kg")
                if value: weights.append((Decimal(value), row))
        if {v for v, _ in weights} != {Decimal(product["machine_weight_kg"])}:
            raise SafeError(f"Evidencia de peso incompatible: {product['source_model']}")
        power = [r for r in specs if re.search(r"(?:24\s*v|24v)", str(r.get("source_value", "")), re.I)
            and audit.normalized(r.get("source_label")) in {"fuente de potencia", "fuente de alimentacion", "power source", "bateria de plomo-acido", "lead-acid battery"}]
        if not power: raise SafeError(f"Evidencia eléctrica 24 V ausente: {product['source_model']}")
        evidence_rows.append({"source_model": product["source_model"], "height_labels": " | ".join(r.get("source_label", "") for _, r in heights),
            "height_values": " | ".join(r.get("source_value", "") for _, r in heights),
            "capacity_labels": " | ".join(r.get("source_label", "") for r in caps),
            "capacity_values": " | ".join(r.get("source_value", "") for r in caps),
            "weight_labels": " | ".join(r.get("source_label", "") for _, r in weights),
            "weight_values": " | ".join(r.get("source_value", "") for _, r in weights)})
    return evidence_rows


def minimal_patch(detail, approved, sheet_id):
    expected = {"working_height_m": approved["working_height_m"],
        "maximum_load_capacity_kg": approved["maximum_load_capacity_kg"],
        "machine_weight_kg": approved["machine_weight_kg"], "power_source": approved["power_source"],
        "technical_sheet": sheet_id}
    payload = {}
    for key, value in expected.items():
        current = detail.get(key)
        current_id = current.get("id") if key == "technical_sheet" and isinstance(current, dict) else current
        if current_id in (None, ""): payload[key] = value
        elif (key in {"working_height_m", "maximum_load_capacity_kg", "machine_weight_kg"} and _number(current_id) == Decimal(str(value))) or current_id == value: pass
        else: raise SafeError(f"Conflicto no vacío en {key}")
    return payload


def resolve_sheet(client, sheets, approved, datasheet, media_root):
    name = approved["datasheet_name"]; filename = datasheet["file_name"]
    candidates = [s for s in sheets if s.get("name") == name]
    foreign = [s for s in sheets if s.get("name") != name and (s.get("original_file_name") == filename or
        (s.get("size_bytes") == datasheet["size_bytes"] and s.get("mime_type") == "application/pdf"))]
    if len(candidates) > 1 or foreign: raise SafeError("Colisión o ficha duplicada")
    if candidates:
        sheet = candidates[0]
        if sheet.get("original_file_name") != filename or sheet.get("mime_type") != "application/pdf" or int(sheet.get("size_bytes", -1)) != datasheet["size_bytes"]:
            raise SafeError("Metadatos de ficha existente incompatibles")
        if hashlib.sha256(client.download(sheet["id"])).hexdigest() != datasheet["sha256"]: raise SafeError("Contenido de ficha existente incompatible")
        return sheet, True
    path = Path(media_root).joinpath(*datasheet["relative_path"].split("/")); data = path.read_bytes()
    return client.post_datasheet(name, filename, data), False


def snapshot(client, catalog):
    state = {"categories": extract_list(client.get_json("/api/categories?include_inactive=true"), "categorías"),
        "brands": extract_list(client.get_json("/api/brands?include_inactive=true"), "marcas"),
        "products": extract_list(client.get_json("/api/products?include_unpublished=true"), "productos"),
        "images": extract_list(client.get_json("/api/product-images"), "imágenes"),
        "specs": extract_list(client.get_json("/api/product-specs"), "especificaciones"),
        "sheets": extract_list(client.get_json("/api/technical-sheets"), "fichas")}
    state["details"] = {p["id"]: client.get_json(f"/api/products/{p['id']}") for p in state["products"]
        if p.get("model") in {x["target_model"] for x in catalog}}
    return state


def preflight(state, catalog, datasheets):
    brands = [b for b in state["brands"] if b.get("name") == "LGMG" and b.get("is_active") is not False]
    cats = [c for c in state["categories"] if c.get("name") == "Elevadores tipo tijera eléctricos" and c.get("is_active") is not False]
    roots = [c for c in state["categories"] if c.get("name") == "Maquinaria" and c.get("is_active") is not False]
    if len(brands) != 1 or len(cats) != 1 or len(roots) != 1: raise SafeError("Marca/categoría activa ausente o ambigua")
    result = []
    for approved, datasheet in zip(catalog, datasheets):
        matches = [p for p in state["products"] if p.get("model") == approved["target_model"] and p.get("name") == approved["target_name"]]
        if len(matches) != 1: raise SafeError("Producto ausente o ambiguo")
        summary = matches[0]; detail = state["details"].get(summary["id"])
        if not detail: raise SafeError("Detalle de producto ausente")
        brand = detail.get("brand"); category = detail.get("category") or detail.get("subcategory")
        if (brand.get("id") if isinstance(brand, dict) else brand) != brands[0].get("id"): raise SafeError("Marca incorrecta")
        if (category.get("id") if isinstance(category, dict) else category) != cats[0].get("id"): raise SafeError("Subcategoría incorrecta")
        if detail.get("is_published") is not False or detail.get("is_featured") is not False: raise SafeError("Producto publicado o destacado")
        if any(detail.get(k) not in (None, "") for k in ("terrain_type", "year", "hours_meter")): raise SafeError("Campo preservado no vacío")
        images = [x for x in state["images"] if (x.get("product", {}).get("id") if isinstance(x.get("product"), dict) else x.get("product")) == summary["id"]]
        if len(images) != 1 or sum(x.get("is_main") is True for x in images) != 1: raise SafeError("Imagen principal única incumplida")
        # Valida ahora todos los campos salvo una ficha todavía inexistente.
        minimal_patch(detail, approved, None)
        result.append({"approved": approved, "datasheet": datasheet, "summary": summary, "detail": detail})
    return result


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
        write_csv(staging / OUTPUT_NAMES[0], ["source_model", "target_model", "product_id", "status", "working_height_m", "maximum_load_capacity_kg", "machine_weight_kg", "power_source"], products)
        write_csv(staging / OUTPUT_NAMES[1], ["source_model", "datasheet_name", "file_name", "sha256", "size_bytes", "sheet_id", "status"], sheets)
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


def run(plan_input, media_input, base_url, output, apply=False, confirmed=False, token="", client_factory=LocalApiClient, platform=None):
    if apply != confirmed: raise SafeError("Aplicación requiere ambas confirmaciones")
    if (platform or sys.platform) != "win32": raise SafeError("Esta herramienta solo puede ejecutarse en Windows")
    audit = _audit_module(); plan_root, media_root = Path(plan_input), Path(media_input)
    audit.safe_paths(plan_root, media_root, Path(output)); plan, media = audit.validate_inputs(plan_root, media_root)
    catalog = approved_catalog(); selected = audit.select_products(plan["rows"]["import-products.csv"], catalog)
    datasheets = audit.validate_datasheets(selected, plan, media, media_root)
    if len(datasheets) != 21 or len({x["sha256"] for x in datasheets}) != 21 or any(x["size_bytes"] >= MAX_DATASHEET_BYTES for x in datasheets):
        raise SafeError("Se requieren 21 PDF físicos únicos menores al máximo")
    validate_evidence(selected, plan["rows"]["import-specifications.csv"])
    read_rate_limit(Path(__file__).resolve().parents[2]); client = client_factory(normalize_origin(base_url), token, apply=apply)
    before = snapshot(client, catalog); work = preflight(before, catalog, datasheets)
    result = {"mode": "apply" if apply else "dry-run", "verdict": "DRY_RUN_APPROVED", "products_examined": 21,
        "pending": 0, "updated": 0, "already_enriched": 0, "datasheets_pending": 0, "datasheets_uploaded": 0,
        "datasheets_reused": 0, "conflicts": 0, "updated_product_ids": [], "created_datasheet_ids": [],
        "failed_product": None, "retry_after_seconds": None, "final_verification": False,
        "input_hashes": {"plan": plan["manifest"].get("combined_fingerprint_sha256"), "media": media["manifest"].get("combined_fingerprint_sha256")},
        "products": [], "datasheets": [], "actions": [], "errors": []}
    if not apply:
        result["pending"] = sum(bool(minimal_patch(x["detail"], x["approved"], None)) for x in work)
        result["datasheets_pending"] = sum(not any(s.get("name") == x["approved"]["datasheet_name"] for s in before["sheets"]) for x in work)
        result["http_methods_and_paths"] = client.calls; write_outputs(output, result); return 0
    sheets = list(before["sheets"]); uploads = 0
    try:
        for index, item in enumerate(work, 1):
            approved, datasheet, detail = item["approved"], item["datasheet"], item["detail"]
            existing = any(s.get("name") == approved["datasheet_name"] for s in sheets)
            if not existing and uploads >= UPLOAD_LIMIT: raise RatePause("PAUSED_UPLOAD_WINDOW", UPLOAD_WINDOW_SECONDS)
            sheet, reused = resolve_sheet(client, sheets, approved, datasheet, media_root)
            if reused: result["datasheets_reused"] += 1
            else:
                uploads += 1; result["datasheets_uploaded"] += 1; result["created_datasheet_ids"].append(sheet["id"]); sheets.append(sheet)
            payload = minimal_patch(detail, approved, sheet["id"])
            if payload:
                client.patch_product(item["summary"]["id"], payload); result["updated"] += 1; result["updated_product_ids"].append(item["summary"]["id"])
            else: result["already_enriched"] += 1
            verified = client.get_json(f"/api/products/{item['summary']['id']}")
            if minimal_patch(verified, approved, sheet["id"]): raise SafeError("Verificación inmediata incompleta")
            result["actions"].append({"order": index, "method": "PATCH" if payload else "GET", "path": f"/api/products/{item['summary']['id']}", "product_id": item["summary"]["id"], "sheet_id": sheet["id"], "result": "verified"})
        after = snapshot(client, catalog)
        if len(after["products"]) != len(before["products"]): raise SafeError("El conteo total de productos cambió")
        # Los snapshots inmutables deben conservar imágenes y ProductSpecs exactamente.
        if after["images"] != before["images"] or after["specs"] != before["specs"]: raise SafeError("Datos fuera de alcance cambiaron")
        result["final_verification"] = True; result["verdict"] = "APPLY_VERIFIED" if result["updated"] else "IDEMPOTENT_VERIFIED"
        result["http_methods_and_paths"] = client.calls; write_outputs(output, result); return 0
    except RatePause as pause:
        result["verdict"] = pause.verdict; result["retry_after_seconds"] = pause.retry_after
        result["failed_product"] = approved["target_model"] if 'approved' in locals() else None
        result["http_methods_and_paths"] = client.calls; write_outputs(output, result); return 2
    except Exception as exc:
        result["verdict"] = "CONFLICT"; result["conflicts"] += 1
        result["failed_product"] = approved["target_model"] if 'approved' in locals() else None
        result["errors"].append({"product": result["failed_product"], "error": type(exc).__name__})
        result["http_methods_and_paths"] = client.calls; write_outputs(output, result); return 1


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
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
