from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .ep_download import RESULT_FIELDS
from .paths import atomic_write, safe_path
from .validation import detect_binary

SUCCESS = {"DOWNLOADED", "ALREADY_PRESENT", "MATERIALIZED_SHARED"}
MISSING_SHEETS = {"CBY 30II", "CQD15SD", "EFL1003-HV-6", "EFL703-HV-6", "EFS151"}
IMAGE_LIMIT, SHEET_LIMIT = 5 * 1024 * 1024, 10 * 1024 * 1024
FORMAT_VERSION = 2
ENDPOINTS = ("/api/categories?include_inactive=true", "/api/brands?include_inactive=true",
             "/api/products?include_unpublished=true", "/api/product-images",
             "/api/technical-sheets/", "/api/product-specs")


class EpLocalError(ValueError):
    pass


class DefinitiveRemoteError(EpLocalError):
    """A response proving that the requested mutation did not succeed."""


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.port is None or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise EpLocalError("base URL debe ser HTTP loopback, sin credenciales, ruta, query o fragment y con puerto explícito")
    return value.rstrip("/")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"ep-{model}".lower()).strip("-")


def _items(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("results", "items", "data"):
            if key in value and isinstance(value[key], list):
                return value[key]
    raise EpLocalError("respuesta API incompatible: se esperaba una lista")


def _typed(row, schema, collection):
    if not isinstance(row, dict):
        raise EpLocalError(f"contrato {collection} incompatible: fila no es objeto")
    for field, expected in schema.items():
        if field not in row or not isinstance(row[field], expected):
            names = "/".join(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__
            raise EpLocalError(f"contrato {collection} incompatible: {field} debe ser {names}")
    return row


SCHEMAS = {
    "categories": {"id": int, "slug": str, "parent": (int, type(None)), "product_type": str, "is_active": bool},
    "brands": {"id": int, "name": str, "slug": str, "is_active": bool},
    "products": {"id": int, "name": str, "slug": str, "category_id": int, "brand_id": (int, type(None)),
                 "technical_sheet_id": (int, type(None)), "model": str, "product_type": str, "condition": str,
                 "price_visible": bool, "stock_status": str, "is_featured": bool, "is_published": bool,
                 "includes_technical_review": bool, "includes_commercial_technical_advice": bool,
                 "includes_coordinated_delivery": bool},
    "images": {"id": int, "product": int, "image": str, "file_url": str, "alt_text": str,
               "is_main": bool, "order": int},
    "sheets": {"id": int, "name": str, "original_file_name": str, "content_type": str,
               "size_bytes": int, "file_url": str},
    "specs": {"id": int, "product": int, "name": str, "value": str, "order": int},
}


def _observe(transport, token):
    names = ("categories", "brands", "products", "images", "sheets", "specs")
    observed = {}
    for name, endpoint in zip(names, ENDPOINTS):
        observed[name] = [_typed(row, SCHEMAS[name], name) for row in _items(transport.request("GET", endpoint, token))]
    return observed


def load_assets(root: Path) -> tuple[list[dict], list[dict]]:
    report = safe_path(root, "_control/ep-download-results.csv")
    try:
        with report.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != RESULT_FIELDS:
                raise EpLocalError("contrato ep-download-results.csv incompatible")
            rows = list(reader)
    except OSError as error:
        raise EpLocalError(f"no se pudo leer ep-download-results.csv: {error}") from None
    accepted, omitted, seen = [], [], set()
    prefixes = {"image": "EP/Imagenes modelos EP/", "technical_sheet": "EP/fichas-tecnicas EP/"}
    for row in rows:
        reason = None
        if row.get("target_brand") != "EP" or row.get("state") not in SUCCESS or row.get("asset_type") not in prefixes:
            reason = "ROW_NOT_IMPORTABLE"
        rel = row.get("path", "").replace("\\", "/")
        if any(part.casefold() in {"lgmg", "jlg", "_pendientes"} for part in Path(rel).parts):
            reason = "FOREIGN_OR_PENDING_PATH"
        if not rel.startswith(prefixes.get(row.get("asset_type"), "!")) or rel.startswith("EP/Fichas tecnicas EP/"):
            reason = "PATH_NOT_ACCEPTED"
        if reason:
            omitted.append({"model": row.get("model", ""), "path": rel, "reason": reason})
            continue
        key = (row["model"], row["asset_type"])
        if key in seen:
            raise EpLocalError(f"activo duplicado para {row['model']} {row['asset_type']}")
        seen.add(key)
        path = safe_path(root, rel)
        if not path.is_file() or path.is_symlink():
            raise EpLocalError(f"archivo no regular o symlink: {rel}")
        digest = _digest(path)
        if not re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")) or digest != row["sha256"]:
            raise EpLocalError(f"SHA-256 no coincide: {rel}")
        info = detect_binary(path.read_bytes())
        if info.kind != row["asset_type"] or path.suffix.lower() != info.extension:
            raise EpLocalError(f"firma, tipo o extensión no coincide: {rel}")
        size = path.stat().st_size
        if info.kind == "image" and size > IMAGE_LIMIT:
            raise EpLocalError(f"imagen supera 5 MB: {rel}")
        if info.kind == "technical_sheet" and size > SHEET_LIMIT:
            omitted.append({"model": row["model"], "path": rel, "reason": "SHEET_TOO_LARGE"})
            continue
        accepted.append({"model": row["model"], "type": info.kind, "path": rel, "sha256": digest,
                         "mime": info.mime, "bytes": size})
    models = sorted({r["model"] for r in accepted if r["type"] == "image"})
    images = [r for r in accepted if r["type"] == "image"]
    sheets = [r for r in accepted if r["type"] == "technical_sheet"]
    missing = set(models) - {r["model"] for r in sheets}
    if (len(models), len(images), len(sheets), missing) != (35, 35, 30, MISSING_SHEETS):
        raise EpLocalError(f"escenario EP inesperado: modelos={len(models)} imágenes={len(images)} fichas={len(sheets)} faltantes={sorted(missing)}")
    return accepted, omitted


def product_payload(model: str, category_id, brand_id):
    return {"name": f"EP {model}", "slug": _slug(model), "model": model, "category_id": category_id,
            "brand_id": brand_id, "product_type": "machinery", "condition": "new", "stock_status": "on_request",
            "price_visible": False, "is_featured": False, "is_published": False,
            "includes_technical_review": False, "includes_commercial_technical_advice": False,
            "includes_coordinated_delivery": False}


def _identity(product, payload):
    return all(product[k] == payload[k] for k in payload)


def _binary(transport, token, kind, item, asset):
    endpoint = f"/api/product-images/{item['id']}/file" if kind == "image" else f"/api/technical-sheets/{item['id']}/file"
    raw = transport.request("GET_BYTES", endpoint, token)
    try:
        info = detect_binary(raw)
    except ValueError:
        return False
    if info.kind != kind or hashlib.sha256(raw).hexdigest() != asset["sha256"]:
        return False
    return kind != "technical_sheet" or item["size_bytes"] == len(raw)


def _canonical(plan):
    return {key: value for key, value in plan.items() if key != "fingerprint"}


def _fingerprint(plan):
    encoded = json.dumps(_canonical(plan), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_plan(root, output, base_url):
    try:
        plan = json.loads((output / "ep-local-import-plan.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EpLocalError(f"plan ilegible: {error}") from None
    if plan.get("format_version") != FORMAT_VERSION:
        raise EpLocalError("versión de plan incompatible; genere un dry-run nuevo")
    if plan.get("root") != str(root.resolve()) or plan.get("base_url") != base_url:
        raise EpLocalError("plan no corresponde al root/target")
    if not isinstance(plan.get("fingerprint"), str) or plan["fingerprint"] != _fingerprint(plan):
        raise EpLocalError("fingerprint almacenado no coincide con el contenido del plan")
    return plan


def build_plan(root: Path, base_url: str, transport, token: str) -> dict:
    assets, omitted = load_assets(root)
    state = _observe(transport, token)
    categories = [x for x in state["categories"] if x["slug"] == "maquinaria" and x["product_type"] == "machinery" and x["is_active"] and x["parent"] is None]
    if len(categories) != 1:
        raise EpLocalError("se requiere una única categoría raíz activa maquinaria/machinery")
    brands = [x for x in state["brands"] if x["name"].casefold() == "ep" or x["slug"].casefold() == "ep"]
    if len(brands) > 1:
        raise EpLocalError("marca EP ambigua")
    brand = brands[0] if brands else None
    pairs = {m: {"image": None, "technical_sheet": None} for m in sorted({x["model"] for x in assets})}
    for asset in assets:
        pairs[asset["model"]][asset["type"]] = asset
    operations, conflicts = [], []
    for model, pair in pairs.items():
        payload = product_payload(model, categories[0]["id"], brand["id"] if brand else "$EP_BRAND")
        candidates = [p for p in state["products"] if p["model"] == model or p["slug"] == payload["slug"]]
        exact = [p for p in candidates if brand and _identity(p, payload)]
        if candidates and len(exact) != 1:
            conflicts.append({"model": model, "reason": "PRODUCT_DIVERGENT_OR_AMBIGUOUS"})
        product = exact[0] if len(exact) == 1 else None
        pics = [x for x in state["images"] if product and x["product"] == product["id"]]
        sheet = next((x for x in state["sheets"] if product and x["id"] == product["technical_sheet_id"]), None)
        if product and any(x["product"] == product["id"] for x in state["specs"]):
            conflicts.append({"model": model, "reason": "SPEC_PRESENT"})
        if len(pics) > 1 or (pics and (not pics[0]["is_main"] or pics[0]["order"] != 0 or not _binary(transport, token, "image", pics[0], pair["image"]))):
            conflicts.append({"model": model, "reason": "IMAGE_DIVERGENT"})
        if product and product["technical_sheet_id"] is not None and not pair["technical_sheet"]:
            conflicts.append({"model": model, "reason": "UNEXPECTED_SHEET"})
        if product and product["technical_sheet_id"] is not None and pair["technical_sheet"] and (not sheet or not _binary(transport, token, "technical_sheet", sheet, pair["technical_sheet"])):
            conflicts.append({"model": model, "reason": "SHEET_DIVERGENT"})
        operations.append({"model": model, "payload": payload, "product_id": product["id"] if product else None,
                           "create_product": product is None, "upload_image": not pics,
                           "upload_sheet": bool(pair["technical_sheet"] and not sheet), **pair,
                           "sheet_status": "AVAILABLE" if pair["technical_sheet"] else "MISSING_SOURCE_ALLOWED"})
    snapshot = {name: rows for name, rows in state.items()}
    plan = {"format_version": FORMAT_VERSION, "root": str(root.resolve()), "base_url": base_url,
            "category": categories[0], "brand": brand or {"operation": "create", "name": "EP", "slug": "ep"},
            "remote_snapshot": snapshot, "operations": operations, "conflicts": conflicts, "omitted_files": omitted,
            "counts": {"models": 35, "images": 35, "technical_sheets": 30, "missing_sheets": 5,
                       "planned_mutations": (0 if conflicts else sum(o["create_product"] + o["upload_image"] + 2 * o["upload_sheet"] for o in operations) + (brand is None))},
            "mutations_attempted": 0, "mutations_completed": 0, "lgmg_operations": 0, "jlg_operations": 0}
    plan["fingerprint"] = _fingerprint(plan)
    return plan


def _write(path: Path, value, root: Path):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
    atomic_write(path, data, root)


def write_plan(root: Path, output: Path, plan: dict):
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "ep-local-import-plan.json", plan, root)
    report = {k: plan[k] for k in ("fingerprint", "counts", "conflicts", "omitted_files", "mutations_attempted", "mutations_completed", "lgmg_operations", "jlg_operations")}
    _write(output / "ep-local-import-report.json", report, root)
    _write(output / "ep-local-import-report.txt", f"EP local import dry-run\nfingerprint: {plan['fingerprint']}\nmodels: 35; images: 35; sheets: 30; missing: 5\nblockers: {len(plan['conflicts'])}\nmutations attempted: 0\n".encode(), root)


def _checkpoint(root, output, data):
    _write(output / "ep-local-import-checkpoint.json", data, root)


def apply_plan(root: Path, output: Path, base_url: str, fingerprint: str, transport, token: str):
    plan = _load_plan(root, output, base_url)
    if plan["fingerprint"] != fingerprint:
        raise EpLocalError("--confirm-plan-fingerprint no coincide")
    assets, _ = load_assets(root)
    if {(x["path"], x["sha256"]) for x in assets} != {(a["path"], a["sha256"]) for o in plan["operations"] for a in (o["image"], o["technical_sheet"]) if a}:
        raise EpLocalError("los hashes locales cambiaron")
    if plan["conflicts"]:
        raise EpLocalError("el plan contiene blockers")
    cp_path = output / "ep-local-import-checkpoint.json"
    cp = json.loads(cp_path.read_text()) if cp_path.exists() else {"fingerprint": fingerprint, "completed": {}, "intent": None, "receipts": [], "errors": []}
    if cp.get("fingerprint") != fingerprint or cp.get("intent"):
        raise EpLocalError("checkpoint incompatible o resultado anterior ambiguo; reconciliar por GET")
    current = _observe(transport, token)
    if not cp["completed"] and current != plan["remote_snapshot"]:
        raise EpLocalError("deriva remota detectada antes de mutar")

    def mutate(key, method, endpoint, **kwargs):
        if key in cp["completed"]:
            return cp["completed"][key]
        # Local file reads happen before recording an intent.
        for path in (kwargs.get("files") or {}).values():
            if not path.is_file():
                raise EpLocalError(f"archivo local ausente: {path.name}")
            path.read_bytes()
        cp["intent"] = {"key": key, "method": method, "endpoint": endpoint}
        _checkpoint(root, output, cp)
        try:
            result = transport.request(method, endpoint, token, **kwargs)
        except DefinitiveRemoteError as error:
            cp["intent"] = None
            cp["errors"].append({"key": key, "error": str(error)})
            _checkpoint(root, output, cp)
            raise
        except Exception:
            _checkpoint(root, output, cp)
            raise
        cp["completed"][key] = result
        cp["receipts"].append({"key": key, "id": result["id"]})
        cp["intent"] = None
        _checkpoint(root, output, cp)
        return result

    brand_id = plan["brand"].get("id")
    if not brand_id:
        brand_id = mutate("brand", "POST", "/api/brands", json_data={"name": "EP", "slug": "ep"})["id"]
    for op in plan["operations"]:
        model = op["model"]
        product_id = op["product_id"] or mutate(f"{model}:product", "POST", "/api/products", json_data={**op["payload"], "brand_id": brand_id})["id"]
        if op["upload_image"]:
            mutate(f"{model}:image", "POST", "/api/product-images", files={"image": root / op["image"]["path"]},
                   data={"product_id": product_id, "alt_text": f"EP {model}", "is_main": True, "order": 0})
        if op["upload_sheet"]:
            sheet = mutate(f"{model}:sheet", "POST", "/api/technical-sheets/", files={"file": root / op["technical_sheet"]["path"]},
                           data={"name": f"Ficha técnica EP {model}"})
            mutate(f"{model}:associate", "PATCH", f"/api/products/{product_id}", json_data={"technical_sheet": sheet["id"]})
    return cp


def verify_plan(root: Path, output: Path, base_url: str, transport, token: str):
    plan = _load_plan(root, output, base_url)
    load_assets(root)
    state = _observe(transport, token)
    failures = []
    for op in plan["operations"]:
        expected = {**op["payload"], "brand_id": plan["brand"].get("id", op["payload"]["brand_id"])}
        matches = [p for p in state["products"] if p["model"] == op["model"] and p["name"] == f"EP {op['model']}"]
        if len(matches) != 1:
            failures.append({"model": op["model"], "reason": "PRODUCT_COUNT"}); continue
        product = matches[0]
        expected["brand_id"] = product["brand_id"] if expected["brand_id"] == "$EP_BRAND" else expected["brand_id"]
        if not _identity(product, expected):
            failures.append({"model": op["model"], "reason": "PRODUCT_FIELDS"})
        if any(x["product"] == product["id"] for x in state["specs"]):
            failures.append({"model": op["model"], "reason": "SPEC_PRESENT"})
        pics = [x for x in state["images"] if x["product"] == product["id"]]
        if len(pics) != 1 or not pics[0]["is_main"] or pics[0]["order"] != 0:
            failures.append({"model": op["model"], "reason": "MAIN_IMAGE_COUNT"})
        elif not _binary(transport, token, "image", pics[0], op["image"]):
            failures.append({"model": op["model"], "reason": "IMAGE_HASH"})
        if op["technical_sheet"]:
            sheet = next((x for x in state["sheets"] if x["id"] == product["technical_sheet_id"]), None)
            if not sheet or not _binary(transport, token, "technical_sheet", sheet, op["technical_sheet"]):
                failures.append({"model": op["model"], "reason": "SHEET_HASH"})
        elif product["technical_sheet_id"] is not None:
            failures.append({"model": op["model"], "reason": "UNEXPECTED_SHEET"})
    result = {"ok": not failures and len([p for p in state["products"] if p["brand_id"] == (plan["brand"].get("id") or p["brand_id"]) and p["model"] in {o["model"] for o in plan["operations"]}]) == 35,
              "managed_products": 35, "failures": failures, "lgmg_operations": 0, "jlg_operations": 0}
    _write(output / "ep-local-verification.json", result, root)
    _write(output / "ep-local-verification.txt", ("PASS\n" if result["ok"] else f"FAIL ({len(failures)})\n").encode(), root)
    return result


class LocalTransport:
    def __init__(self, base_url):
        self.base_url = base_url
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise EpLocalError("redirect rechazado")
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)

    def request(self, method, endpoint, token, json_data=None, files=None, data=None):
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}; body = None
        if files:
            boundary = uuid.uuid4().hex; chunks = []
            for key, value in (data or {}).items():
                chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{str(value).lower() if isinstance(value, bool) else value}\r\n".encode())
            for key, path in files.items():
                chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{path.name}\"\r\nContent-Type: {mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}\r\n\r\n".encode(), path.read_bytes(), b"\r\n"])
            chunks.append(f"--{boundary}--\r\n".encode()); body = b"".join(chunks); headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif json_data is not None:
            body = json.dumps(json_data).encode(); headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + endpoint, data=body, headers=headers, method="GET" if method == "GET_BYTES" else method)
        try:
            with self.opener.open(req, timeout=30) as response:
                if response.geturl() != req.full_url:
                    raise EpLocalError("redirect rechazado")
                raw = response.read()
                return raw if method == "GET_BYTES" else (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as error:
            if error.code in {400, 401, 403, 404, 409, 422, 429}:
                retry = error.headers.get("Retry-After", "") if error.code == 429 else ""
                message = f"HTTP {error.code}" + (f" retry_after={int(retry)}" if retry.isdigit() else "")
                raise DefinitiveRemoteError(message) from None
            raise EpLocalError(f"HTTP {error.code}; resultado ambiguo") from None
