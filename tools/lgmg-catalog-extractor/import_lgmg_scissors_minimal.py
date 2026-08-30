#!/usr/bin/env python3
"""Importación local, mínima y cerrada de 21 tijeras eléctricas LGMG."""

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import shutil
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

TOOL_NAME = "import_lgmg_scissors_minimal"
TOOL_VERSION = "1.1.0"
TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
OUTPUT_NAMES = (
    "minimal-import-products.csv", "minimal-import-errors.csv",
    "minimal-import-summary.json", "minimal-import-summary.txt",
    "minimal-import-manifest.json", "README-minimal-import.txt",
)
MODEL_SOURCE_KEYS = (
    ("S0607E-2", "lgmg-ca47fb2f7b08a34e"),
    ("S0808E-2", "lgmg-b37e8e2aac77ee58"),
    ("S0812E-2", "lgmg-cedc32feeaa73a73"),
    ("S1012E-2", "lgmg-4a28e200893ad05d"),
    ("S1212E-2", "lgmg-de0aa4ab2b656a45"),
    ("S1413E-2", "lgmg-4de897eef0ac7a8b"),
    ("SS0407ER", "lgmg-94fcfbbce870720b"),
    ("SS0507E", "lgmg-156920aefbe03fd7"),
    ("SS0607E", "lgmg-c727e1d06982bc59"),
    ("S0607EⅡ", "lgmg-c7eb4374a0c40929"),
    ("S0808EⅡ", "lgmg-e81599e6857a2a86"),
    ("S0812EⅡ", "lgmg-031266dc31776efa"),
    ("S1012EⅡ", "lgmg-f4f1843b00843622"),
    ("S1212EⅡ", "lgmg-a13c377a9f62d48d"),
    ("S1413EⅡ", "lgmg-b972b70cf11a169f"),
    ("S0607Ⅱ", "lgmg-5674d5ee1fd7204a"),
    ("S0808Ⅱ", "lgmg-0044f27673d09419"),
    ("S0812Ⅱ", "lgmg-9b41d482ac7e5806"),
    ("S1012Ⅱ", "lgmg-9c85f65a2da4e021"),
    ("S1212Ⅱ", "lgmg-29aa5f082080a266"),
    ("S1413Ⅱ", "lgmg-18c29f8f44eaba7c"),
)
MODELS = tuple(model for model, _ in MODEL_SOURCE_KEYS)
SOURCE_TARGET_MODELS = dict((
    ("S0607E-2", "S0607E-2"), ("S0808E-2", "S0808E-2"), ("S0812E-2", "S0812E-2"),
    ("S1012E-2", "S1012E-2"), ("S1212E-2", "S1212E-2"), ("S1413E-2", "S1413E-2"),
    ("SS0407ER", "SS0407ER"), ("SS0507E", "SS0507E"), ("SS0607E", "SS0607E"),
    ("S0607EⅡ", "S0607E"), ("S0808EⅡ", "S0808E"), ("S0812EⅡ", "S0812E"),
    ("S1012EⅡ", "S1012E"), ("S1212EⅡ", "S1212E"), ("S1413EⅡ", "S1413E"),
    ("S0607Ⅱ", "S0607"), ("S0808Ⅱ", "S0808"), ("S0812Ⅱ", "S0812"),
    ("S1012Ⅱ", "S1012"), ("S1212Ⅱ", "S1212"), ("S1413Ⅱ", "S1413"),
))
TARGET_SUBCATEGORY_SLUGS = frozenset({
    "elevadores-tipo-tijera-electricos",
    "elevador-electrico",
})


class ImportErrorSafe(Exception):
    """Error controlado que nunca contiene credenciales."""


class BlockingError(ImportErrorSafe):
    """Precondición o conflicto anterior a cualquier escritura."""


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).casefold().split())


def slug_normalized(value):
    return "-".join(normalized(value).replace("_", " ").replace("-", " ").split())


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def csv_rows(path):
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    except (UnicodeError, csv.Error) as exc:
        raise ImportErrorSafe(f"CSV inválido: {path.name}") from exc


def validate_plan(plan_root):
    path = plan_root / "import-products.csv"
    if not path.is_file() or path.is_symlink():
        raise ImportErrorSafe("Falta import-products.csv regular en el plan")
    rows = csv_rows(path)
    actual = [(row.get("metric_model"), row.get("source_key")) for row in rows]
    if actual != list(MODEL_SOURCE_KEYS):
        raise BlockingError("import-products.csv debe contener exactamente los 21 modelos y source_key aprobados, en el orden cerrado")
    fixed = {
        "source_category": "Elevadores de Tijera",
        "target_subcategory": "Elevadores tipo tijera eléctricos",
        "target_brand": "LGMG", "product_type": "machinery",
        "condition": "new", "stock_status": "on_request",
    }
    for row in rows:
        if any(row.get(key) != value for key, value in fixed.items()):
            raise BlockingError(f"Fila fuera del alcance mínimo: {row.get('source_key', '')}")
        if not row.get("proposed_name") or len(row["proposed_name"]) > 220:
            raise BlockingError(f"proposed_name inválido: {row.get('source_key', '')}")
    for row in rows:
        row["source_model"] = row["metric_model"]
        row["target_model"] = SOURCE_TARGET_MODELS[row["metric_model"]]
        row["target_name"] = f"Elevador tipo tijera eléctrico LGMG {row['target_model']}"
    return rows, sha256(path.read_bytes())


def safe_media_file(media_root, relative):
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise BlockingError(f"Ruta de medio insegura: {relative}")
    root = media_root.resolve(strict=True)
    candidate = media_root.joinpath(*pure.parts)
    current = media_root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise BlockingError(f"Symlink prohibido en medio: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved == root or root not in resolved.parents or not resolved.is_file():
        raise BlockingError(f"Medio fuera de media-package: {relative}")
    return resolved


def validate_image(path, row):
    data = path.read_bytes()
    if not data or len(data) > MAX_IMAGE_BYTES or str(len(data)) != str(row.get("size_bytes", "")):
        raise BlockingError(f"Tamaño de imagen inválido: {row.get('source_key', '')}")
    if sha256(data) != row.get("sha256"):
        raise BlockingError(f"SHA-256 de imagen inválido: {row.get('source_key', '')}")
    mime = row.get("mime_type", "").casefold()
    suffix = path.suffix.casefold()
    valid = ((mime == "image/jpeg" and suffix in (".jpg", ".jpeg") and data[:3] == b"\xff\xd8\xff") or
             (mime == "image/png" and suffix == ".png" and data[:8] == b"\x89PNG\r\n\x1a\n") or
             (mime == "image/webp" and suffix == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
    if not valid:
        raise BlockingError(f"MIME, extensión o firma de imagen inválidos: {row.get('source_key', '')}")
    return data, mime


def validate_media(media_root):
    path = media_root / "import-images.csv"
    if not path.is_file() or path.is_symlink():
        raise ImportErrorSafe("Falta import-images.csv regular en media-package")
    selected = [r for r in csv_rows(path) if r.get("image_order") == "1" and r.get("primary_candidate", "").casefold() == "true"]
    by_key = {}
    for row in selected:
        by_key.setdefault(row.get("source_key"), []).append(row)
    expected_keys = [key for _, key in MODEL_SOURCE_KEYS]
    if list(by_key) != expected_keys or any(len(by_key[key]) != 1 for key in expected_keys):
        raise BlockingError("Deben existir exactamente 21 asociaciones principales, una por source_key y en orden")
    result = []
    for key in expected_keys:
        row = by_key[key][0]
        relative = row.get("local_file", "")
        file_path = safe_media_file(media_root, relative)
        data, mime = validate_image(file_path, row)
        result.append({**row, "path": file_path, "data": data, "mime_type": mime})
    if len({item["path"] for item in result}) != 20:
        raise BlockingError("Las 21 asociaciones deben referir exactamente 20 archivos físicos únicos")
    return result, sha256(path.read_bytes())


def normalize_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1") or
            parsed.port != 5000 or parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/") or parsed.netloc not in ("localhost:5000", "127.0.0.1:5000")):
        raise BlockingError("--api-base-url debe ser exactamente http://localhost:5000 o http://127.0.0.1:5000")
    return f"http://{parsed.hostname}:5000"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ImportErrorSafe("Redirect HTTP rechazado")


class LocalApiClient:
    def __init__(self, origin, token, apply=False):
        self.origin, self.token, self.apply = origin, token, apply
        self.methods = []
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None, content_type=None):
        allowed = {"GET", "POST"} if self.apply else {"GET"}
        if method not in allowed:
            raise ImportErrorSafe(f"Método HTTP prohibido en este modo: {method}")
        if method == "POST" and path not in ("/api/products", "/api/product-images"):
            raise ImportErrorSafe("Destino POST no permitido")
        allowed_gets = {
            "/api/categories?include_inactive=true",
            "/api/brands?include_inactive=true",
            "/api/products?include_unpublished=true",
            "/api/product-images",
        }
        if method == "GET" and path not in allowed_gets:
            raise ImportErrorSafe("Destino GET no permitido")
        if not path.startswith("/api/"):
            raise ImportErrorSafe("Ruta API no permitida")
        headers = {"Accept": "application/json", "Authorization": "Bearer " + self.token}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.origin + path, data=body, headers=headers, method=method)
        self.methods.append(method)
        try:
            response = self.opener.open(request, timeout=15)
            if response.geturl().split("/api/", 1)[0] != self.origin:
                raise ImportErrorSafe("Cambio de origen API rechazado")
            raw = response.read(MAX_JSON_BYTES + 1)
            if len(raw) > MAX_JSON_BYTES:
                raise ImportErrorSafe("Respuesta API excede el límite")
            mime = response.headers.get_content_type()
            if mime != "application/json":
                raise ImportErrorSafe(f"MIME JSON inesperado: {mime}")
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ImportErrorSafe(f"HTTP {exc.code} en {method} {path}") from None
        except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise ImportErrorSafe(f"Respuesta local inválida en {method} {path}: {type(exc).__name__}") from None

    def get_json(self, path):
        return self.request("GET", path)

    def post_json(self, path, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return self.request("POST", path, body, "application/json; charset=utf-8")

    def post_image(self, product_id, image):
        boundary = "----jem-minimal-" + uuid.uuid4().hex
        parts = []
        def field(name, value):
            parts.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()])
        field("product", product_id); field("alt_text", image.get("proposed_alt", "")); field("order", 0); field("is_main", "true")
        filename = image["path"].name.replace('"', "")
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
                      f"Content-Type: {image['mime_type']}\r\n\r\n").encode())
        parts.extend([image["data"], b"\r\n", f"--{boundary}--\r\n".encode()])
        return self.request("POST", "/api/product-images", b"".join(parts), "multipart/form-data; boundary=" + boundary)


def extract_list(value, label):
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        value = value["results"]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ImportErrorSafe(f"Respuesta inválida para {label}")
    return value


def snapshot(client):
    return {
        "categories": extract_list(client.get_json("/api/categories?include_inactive=true"), "categories"),
        "brands": extract_list(client.get_json("/api/brands?include_inactive=true"), "brands"),
        "products": extract_list(client.get_json("/api/products?include_unpublished=true"), "products"),
        "images": extract_list(client.get_json("/api/product-images"), "product-images"),
    }


def resolve_preconditions(categories, brands):
    roots = [c for c in categories if c.get("name") == "Maquinaria" and c.get("slug") == "maquinaria" and
             c.get("product_type") == "machinery" and c.get("is_active") is True and c.get("parent") is None]
    if len(roots) != 1:
        raise BlockingError("Corregir manualmente: debe existir una única raíz activa Maquinaria (slug maquinaria, machinery, sin padre)")
    root = roots[0]
    subs = [c for c in categories if c.get("name") == "Elevadores tipo tijera eléctricos" and
            slug_normalized(c.get("slug")) in TARGET_SUBCATEGORY_SLUGS and c.get("product_type") == "machinery" and
            c.get("is_active") is True and c.get("parent") == root.get("id")]
    if len(subs) != 1:
        raise BlockingError("Corregir manualmente: debe existir una única subcategoría activa Elevadores tipo tijera eléctricos bajo Maquinaria")
    matches = [b for b in brands if normalized(b.get("name")) == "lgmg" and b.get("is_active") is True]
    if len(matches) != 1:
        raise BlockingError("Corregir manualmente: debe existir una única marca activa con nombre LGMG")
    return root, subs[0], matches[0]


def nested_id(value):
    return value.get("id") if isinstance(value, dict) else value


def canonical_values(row):
    source = row.get("source_model", row["metric_model"])
    target = row.get("target_model", SOURCE_TARGET_MODELS[source])
    return source, target, row.get("target_name", f"Elevador tipo tijera eléctrico LGMG {target}")


def classify_products(rows, products, images, category_id, brand_id):
    image_counts = {}
    for image in images:
        image_counts[nested_id(image.get("product")) or image.get("product_id")] = image_counts.get(nested_id(image.get("product")) or image.get("product_id"), 0) + 1
    decisions = []
    for row in rows:
        source_model, target_model, target_name = canonical_values(row)
        hits = [p for p in products if normalized(p.get("model")) in
                {normalized(source_model), normalized(target_model)}]
        if not hits:
            decisions.append({"row": row, "action": "create_product", "product": None}); continue
        exact = [p for p in hits if p.get("name") == target_name and p.get("model") == target_model and nested_id(p.get("brand")) == brand_id and
                 nested_id(p.get("category")) == category_id and p.get("is_published") is False]
        legacy = [p for p in hits if p.get("name") == f"Elevador de tijera eléctrico LGMG {source_model}" and
                  p.get("model") == source_model and nested_id(p.get("brand")) == brand_id and
                  nested_id(p.get("category")) == category_id]
        if legacy:
            decisions.append({"row": row, "action": "conflict", "product": legacy[0],
                              "error": "Ejecute primero canonicalize_lgmg_scissors_catalog.py"}); continue
        if len(hits) != 1 or len(exact) != 1:
            decisions.append({"row": row, "action": "conflict", "product": hits[0] if len(hits) == 1 else None}); continue
        product = exact[0]
        embedded = product.get("images") if isinstance(product.get("images"), list) else []
        count = max(len(embedded), image_counts.get(product.get("id"), 0))
        decisions.append({"row": row, "action": "already_present" if count else "upload_image_only", "product": product})
    return decisions


def product_payload(row, category_id, brand_id):
    _, target_model, target_name = canonical_values(row)
    return {
        "name": target_name, "category": category_id, "brand": brand_id,
        "supplier": None, "technical_sheet": None, "product_type": "machinery",
        "condition": "new", "short_description": "", "description": "",
        "model": target_model, "sku": None, "working_height_m": None,
        "terrain_type": None, "year": None, "hours_meter": None,
        "maximum_load_capacity_kg": None, "machine_weight_kg": None,
        "power_source": None, "includes_technical_review": False,
        "includes_commercial_technical_advice": False, "includes_coordinated_delivery": False,
        "price": None, "price_currency": None, "price_tax_mode": None,
        "price_visible": False, "stock_status": "on_request", "is_featured": False,
        "is_published": False,
    }


def verify_after_apply(rows, products, images, category_id, brand_id):
    decisions = classify_products(rows, products, images, category_id, brand_id)
    bad = [d for d in decisions if d["action"] != "already_present"]
    if bad:
        raise ImportErrorSafe("Verificación posterior incompleta: los 21 productos deben seguir no publicados y tener imagen")


def fingerprint(plan_fp, media_fp):
    return sha256((plan_fp + ":" + media_fp).encode())


def write_outputs(output, result):
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and (output.is_symlink() or not output.is_dir() or any(output.iterdir())):
        raise ImportErrorSafe("--output-dir debe estar ausente o ser un directorio vacío sin symlink")
    output.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".minimal-import-staging-", dir=output))
    try:
        product_fields = ["source_key", "source_model", "target_model", "target_name", "proposed_name", "action", "product_id", "image_action"]
        with (staging / OUTPUT_NAMES[0]).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, product_fields, lineterminator="\r\n"); writer.writeheader(); writer.writerows(result["product_rows"])
        with (staging / OUTPUT_NAMES[1]).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, ["code", "message"], lineterminator="\r\n"); writer.writeheader(); writer.writerows(result["errors"])
        summary = {"verdict": result["verdict"], "mode": result["mode"], "counts": result["counts"], "errors": result["errors"]}
        (staging / OUTPUT_NAMES[2]).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[3]).write_text(f"Veredicto: {result['verdict']}\nModo: {result['mode']}\nErrores: {len(result['errors'])}\n", encoding="utf-8")
        manifest = {
            "tool": TOOL_NAME, "version": TOOL_VERSION, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": result["mode"], "local_api_origin": result["origin"], "input_fingerprint_sha256": result["fingerprint"],
            "source_models": list(MODELS), "target_models": list(SOURCE_TARGET_MODELS.values()), "products_planned": 21, **result["counts"], "errors": result["errors"],
            "http_methods_used": result["methods"], "categories_created": 0, "categories_updated": 0,
            "brands_created": 0, "brands_updated": 0, "products_deleted": 0,
            "specifications_created": 0, "datasheets_uploaded": 0, "content_published": False,
            "credentials_persisted": False,
        }
        (staging / OUTPUT_NAMES[4]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[5]).write_text("IMPORTACIÓN MÍNIMA LGMG\n\nNo publica, no crea categorías o marcas y no importa fichas ni especificaciones.\n", encoding="utf-8")
        for name in OUTPUT_NAMES:
            os.replace(staging / name, output / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def run(plan_root, media_root, base_url, output, apply, token, client_factory=LocalApiClient):
    origin = normalize_origin(base_url)
    rows, plan_fp = validate_plan(plan_root)
    media, media_fp = validate_media(media_root)
    client = client_factory(origin, token, apply=apply)
    state = snapshot(client)
    _, category, brand = resolve_preconditions(state["categories"], state["brands"])
    decisions = classify_products(rows, state["products"], state["images"], category["id"], brand["id"])
    if any(item["action"] == "conflict" for item in decisions):
        raise BlockingError("Conflicto de producto: corregir manualmente coincidencias ambiguas o incompatibles antes de aplicar")
    counts = {"products_created": 0, "products_already_present": 0, "images_uploaded": 0, "images_skipped_present": 0}
    product_rows, errors = [], []
    try:
        for decision, image in zip(decisions, media):
            row, action, product = decision["row"], decision["action"], decision["product"]
            product_id = product.get("id") if product else None
            image_action = "planned_upload" if action in ("create_product", "upload_image_only") else "skip_present"
            if apply:
                if action == "create_product":
                    product = client.post_json("/api/products", product_payload(row, category["id"], brand["id"]))
                    if not isinstance(product, dict) or not isinstance(product.get("id"), int):
                        raise ImportErrorSafe("Respuesta de creación de producto inválida")
                    product_id = product["id"]; counts["products_created"] += 1
                else:
                    counts["products_already_present"] += 1
                if action in ("create_product", "upload_image_only"):
                    client.post_image(product_id, image); counts["images_uploaded"] += 1; image_action = "uploaded"
                else:
                    counts["images_skipped_present"] += 1
            product_rows.append({"source_key": row["source_key"], "source_model": row["source_model"],
                                 "target_model": row["target_model"], "target_name": row["target_name"],
                                 "proposed_name": row["proposed_name"], "action": action, "product_id": product_id or "",
                                 "image_action": image_action})
        if apply:
            final = snapshot(client)
            verify_after_apply(rows, final["products"], final["images"], category["id"], brand["id"])
    except ImportErrorSafe as exc:
        errors.append({"code": "operational_error", "message": str(exc)[:240]})
    result = {"verdict": "GO" if not errors else "PARTIAL", "mode": "apply" if apply else "dry_run",
              "origin": origin, "fingerprint": fingerprint(plan_fp, media_fp), "methods": sorted(set(client.methods)),
              "counts": counts, "product_rows": product_rows, "errors": errors}
    write_outputs(output, result)
    return 2 if errors else 0


def access_token(environ=os.environ):
    token = environ.get(TOKEN_ENV, "")
    if not token or "\r" in token or "\n" in token:
        raise BlockingError(f"Defina manualmente {TOKEN_ENV} con una sesión local válida")
    return token


def build_parser():
    parser = argparse.ArgumentParser(description="Importador local mínimo de 21 tijeras eléctricas LGMG")
    parser.add_argument("--plan-input", required=True); parser.add_argument("--media-input", required=True)
    parser.add_argument("--api-base-url", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--apply", action="store_true"); parser.add_argument("--confirm-minimal-import", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.confirm_minimal_import and not args.apply:
        print("Error: --confirm-minimal-import solo es válido junto con --apply", file=sys.stderr); return 3
    if args.apply and not args.confirm_minimal_import:
        print("Error: --apply exige --confirm-minimal-import", file=sys.stderr); return 3
    try:
        return run(Path(args.plan_input), Path(args.media_input), args.api_base_url,
                   Path(args.output_dir), args.apply, access_token())
    except BlockingError as exc:
        print("NO_GO: " + str(exc)[:240], file=sys.stderr); return 3
    except (ImportErrorSafe, OSError) as exc:
        print("Error operativo: " + str(exc)[:240], file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
