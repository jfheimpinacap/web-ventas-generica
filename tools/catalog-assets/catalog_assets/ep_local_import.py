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
ENDPOINTS = ("/api/categories?include_inactive=true", "/api/brands?include_inactive=true",
             "/api/products?include_unpublished=true", "/api/product-images", "/api/technical-sheets/")


class EpLocalError(ValueError):
    pass


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.port is None or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise EpLocalError("base URL debe ser HTTP loopback, sin credenciales, ruta, query o fragment y con puerto explícito")
    return value.rstrip("/")


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"ep-{model}".lower()).strip("-")


def _items(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("results", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    raise EpLocalError("respuesta API incompatible")


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
    return all(product.get(k) == payload[k] for k in ("name", "slug", "model", "category_id", "brand_id"))


def build_plan(root: Path, base_url: str, transport, token: str) -> dict:
    assets, omitted = load_assets(root)  # all local validation precedes the first request
    observed = {endpoint: _items(transport.request("GET", endpoint, token)) for endpoint in ENDPOINTS}
    categories = [x for x in observed[ENDPOINTS[0]] if x.get("slug") == "maquinaria" and x.get("product_type") == "machinery" and x.get("is_active", True) and not x.get("parent_id")]
    if len(categories) != 1:
        raise EpLocalError("se requiere una única categoría raíz activa maquinaria/machinery")
    brands = [x for x in observed[ENDPOINTS[1]] if str(x.get("name", "")).casefold() == "ep" or str(x.get("slug", "")).casefold() == "ep"]
    if len(brands) > 1:
        raise EpLocalError("marca EP ambigua")
    brand = brands[0] if brands else None
    by_model = {m: {"image": None, "technical_sheet": None} for m in sorted({x["model"] for x in assets})}
    for asset in assets: by_model[asset["model"]][asset["type"]] = asset
    products, images, sheets = observed[ENDPOINTS[2]], observed[ENDPOINTS[3]], observed[ENDPOINTS[4]]
    operations, conflicts = [], []
    for model, pair in by_model.items():
        payload = product_payload(model, categories[0]["id"], brand["id"] if brand else "$EP_BRAND")
        candidates = [p for p in products if p.get("model") == model or p.get("slug") == payload["slug"]]
        exact = [p for p in candidates if brand and _identity(p, payload)]
        if candidates and len(exact) != 1:
            conflicts.append({"model": model, "reason": "PRODUCT_DIVERGENT_OR_AMBIGUOUS"})
        product = exact[0] if len(exact) == 1 else None
        current_images = [x for x in images if product and x.get("product_id") == product.get("id")]
        current_sheets = [x for x in sheets if product and (x.get("product_id") == product.get("id") or x.get("id") == product.get("technical_sheet"))]
        if len(current_images) > 1 or (current_images and current_images[0].get("sha256") not in (None, pair["image"]["sha256"])):
            conflicts.append({"model": model, "reason": "IMAGE_DIVERGENT"})
        if len(current_sheets) > 1 or (current_sheets and pair["technical_sheet"] and current_sheets[0].get("sha256") not in (None, pair["technical_sheet"]["sha256"])):
            conflicts.append({"model": model, "reason": "SHEET_DIVERGENT"})
        operations.append({"model": model, "payload": payload, "product_id": product.get("id") if product else None,
                           "create_product": product is None, "upload_image": not current_images,
                           "upload_sheet": bool(pair["technical_sheet"] and not current_sheets), **pair,
                           "sheet_status": "AVAILABLE" if pair["technical_sheet"] else "MISSING_SOURCE_ALLOWED"})
    canonical = {"format_version": 1, "root": str(root.resolve()), "base_url": base_url, "category": categories[0],
                 "brand": brand or {"operation": "create", "name": "EP", "slug": "ep"}, "operations": operations,
                 "conflicts": conflicts, "omitted_files": omitted,
                 "counts": {"models": 35, "images": 35, "technical_sheets": 30, "missing_sheets": 5,
                            "planned_mutations": (0 if conflicts else sum(o["create_product"] + o["upload_image"] + 2 * o["upload_sheet"] for o in operations) + (brand is None))},
                 "mutations_attempted": 0, "mutations_completed": 0, "lgmg_operations": 0, "jlg_operations": 0}
    canonical["fingerprint"] = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return canonical


def _write(path: Path, value, root: Path):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
    atomic_write(path, data, root)


def write_plan(root: Path, output: Path, plan: dict):
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "ep-local-import-plan.json", plan, root)
    report = {k: plan[k] for k in ("fingerprint", "counts", "conflicts", "omitted_files", "mutations_attempted", "mutations_completed", "lgmg_operations", "jlg_operations")}
    _write(output / "ep-local-import-report.json", report, root)
    text = f"EP local import dry-run\nfingerprint: {plan['fingerprint']}\nmodels: 35; images: 35; sheets: 30; missing: 5\nblockers: {len(plan['conflicts'])}\nmutations attempted: 0\n"
    _write(output / "ep-local-import-report.txt", text.encode(), root)


def _checkpoint(root, output, data):
    _write(output / "ep-local-import-checkpoint.json", data, root)


def apply_plan(root: Path, output: Path, base_url: str, fingerprint: str, transport, token: str):
    plan = json.loads((output / "ep-local-import-plan.json").read_text(encoding="utf-8"))
    if plan.get("fingerprint") != fingerprint or plan.get("root") != str(root.resolve()) or plan.get("base_url") != base_url:
        raise EpLocalError("fingerprint, root o target no coincide con el plan")
    assets, _ = load_assets(root)
    if {(x["path"], x["sha256"]) for x in assets} != {(a["path"], a["sha256"]) for o in plan["operations"] for a in (o["image"], o["technical_sheet"]) if a}:
        raise EpLocalError("los hashes locales cambiaron")
    if plan["conflicts"]:
        raise EpLocalError("el plan contiene blockers")
    cp_path = output / "ep-local-import-checkpoint.json"
    cp = json.loads(cp_path.read_text()) if cp_path.exists() else {"fingerprint": fingerprint, "completed": {}, "intent": None, "receipts": []}
    if cp.get("fingerprint") != fingerprint or cp.get("intent"):
        raise EpLocalError("checkpoint incompatible o resultado anterior ambiguo; reconciliar antes de reintentar")
    def mutate(key, method, endpoint, **kwargs):
        if key in cp["completed"]: return cp["completed"][key]
        cp["intent"] = {"key": key, "method": method, "endpoint": endpoint}; _checkpoint(root, output, cp)
        try: result = transport.request(method, endpoint, token, **kwargs)
        except Exception:
            _checkpoint(root, output, cp); raise
        cp["completed"][key] = result; cp["receipts"].append({"key": key, "id": result.get("id")}); cp["intent"] = None
        _checkpoint(root, output, cp); return result
    brand = plan["brand"]
    brand_id = brand.get("id")
    if not brand_id: brand_id = mutate("brand", "POST", "/api/brands", json_data={"name": "EP", "slug": "ep"})["id"]
    for op in plan["operations"]:
        model = op["model"]; payload = {**op["payload"], "brand_id": brand_id}
        product_id = op["product_id"] or mutate(f"{model}:product", "POST", "/api/products", json_data=payload)["id"]
        if op["upload_image"]:
            mutate(f"{model}:image", "POST", "/api/product-images", files={"file": root / op["image"]["path"]},
                   data={"product_id": product_id, "is_main": True, "order": 0, "alt_text": f"EP {model}"})
        if op["upload_sheet"]:
            sheet = mutate(f"{model}:sheet", "POST", "/api/technical-sheets/", files={"file": root / op["technical_sheet"]["path"]},
                           data={"name": f"Ficha técnica EP {model}"})
            mutate(f"{model}:associate", "PATCH", f"/api/products/{product_id}", json_data={"technical_sheet": sheet["id"]})
    return cp


def verify_plan(root: Path, output: Path, base_url: str, transport, token: str):
    plan = json.loads((output / "ep-local-import-plan.json").read_text(encoding="utf-8"))
    if plan["root"] != str(root.resolve()) or plan["base_url"] != base_url: raise EpLocalError("plan no corresponde al root/target")
    observed = {endpoint: _items(transport.request("GET", endpoint, token)) for endpoint in ENDPOINTS}
    products, images, sheets = observed[ENDPOINTS[2]], observed[ENDPOINTS[3]], observed[ENDPOINTS[4]]
    failures = []
    for op in plan["operations"]:
        matches = [p for p in products if p.get("model") == op["model"] and p.get("name") == f"EP {op['model']}"]
        if len(matches) != 1: failures.append({"model": op["model"], "reason": "PRODUCT_COUNT"}); continue
        p = matches[0]
        if p.get("condition") != "new" or p.get("is_published") is not False or p.get("price_visible") is not False or p.get("specs", []) != []:
            failures.append({"model": op["model"], "reason": "PRODUCT_FIELDS"})
        pics = [x for x in images if x.get("product_id") == p.get("id") and x.get("is_main")]
        if len(pics) != 1: failures.append({"model": op["model"], "reason": "MAIN_IMAGE_COUNT"})
        elif hashlib.sha256(transport.request("GET_BYTES", f"/api/product-images/{pics[0]['id']}/file", token)).hexdigest() != op["image"]["sha256"]:
            failures.append({"model": op["model"], "reason": "IMAGE_HASH"})
        if op["technical_sheet"]:
            match = next((x for x in sheets if x.get("id") == p.get("technical_sheet") or x.get("product_id") == p.get("id")), None)
            if not match or hashlib.sha256(transport.request("GET_BYTES", f"/api/technical-sheets/{match['id']}/file", token)).hexdigest() != op["technical_sheet"]["sha256"]:
                failures.append({"model": op["model"], "reason": "SHEET_HASH"})
        elif p.get("technical_sheet") is not None: failures.append({"model": op["model"], "reason": "UNEXPECTED_SHEET"})
    result = {"ok": not failures, "managed_products": 35, "failures": failures, "lgmg_operations": 0, "jlg_operations": 0}
    _write(output / "ep-local-verification.json", result, root)
    _write(output / "ep-local-verification.txt", ("PASS\n" if not failures else f"FAIL ({len(failures)})\n").encode(), root)
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
                chunks += [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{str(value).lower() if isinstance(value, bool) else value}\r\n".encode()]
            for key, path in files.items():
                chunks += [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{path.name}\"\r\nContent-Type: {mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}\r\n\r\n".encode(), path.read_bytes(), b"\r\n"]
            chunks += [f"--{boundary}--\r\n".encode()]; body = b"".join(chunks); headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif json_data is not None: body = json.dumps(json_data).encode(); headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + endpoint, data=body, headers=headers, method="GET" if method == "GET_BYTES" else method)
        try:
            with self.opener.open(req, timeout=30) as response:
                if response.geturl() != req.full_url: raise EpLocalError("redirect rechazado")
                raw = response.read()
                return raw if method == "GET_BYTES" else (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as error:
            if error.code == 429:
                retry = error.headers.get("Retry-After", "")
                raise EpLocalError("RATE_LIMITED" + (f" retry_after={int(retry)}" if retry.isdigit() else "")) from None
            raise EpLocalError(f"HTTP {error.code}") from None
