#!/usr/bin/env python3
"""Canoniza, de forma cerrada y local, 21 tijeras electricas LGMG."""

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
TOOL_VERSION = "1.0.0"
OUTPUT_NAMES = (
    "canonicalization-products.csv", "canonicalization-errors.csv",
    "canonicalization-summary.json", "canonicalization-summary.txt",
    "canonicalization-manifest.json", "README-canonicalization.txt",
)
SOURCE_TARGET_MODELS = (
    ("S0607E-2", "S0607E-2"), ("S0808E-2", "S0808E-2"),
    ("S0812E-2", "S0812E-2"), ("S1012E-2", "S1012E-2"),
    ("S1212E-2", "S1212E-2"), ("S1413E-2", "S1413E-2"),
    ("SS0407ER", "SS0407ER"), ("SS0507E", "SS0507E"),
    ("SS0607E", "SS0607E"), ("S0607EⅡ", "S0607E"),
    ("S0808EⅡ", "S0808E"), ("S0812EⅡ", "S0812E"),
    ("S1012EⅡ", "S1012E"), ("S1212EⅡ", "S1212E"),
    ("S1413EⅡ", "S1413E"), ("S0607Ⅱ", "S0607"),
    ("S0808Ⅱ", "S0808"), ("S0812Ⅱ", "S0812"),
    ("S1012Ⅱ", "S1012"), ("S1212Ⅱ", "S1212"),
    ("S1413Ⅱ", "S1413"),
)
CATALOG = tuple({
    "product_id": product_id, "source_model": source, "target_model": target,
    "source_name": f"Elevador de tijera eléctrico LGMG {source}",
    "target_name": f"Elevador tipo tijera eléctrico LGMG {target}",
} for product_id, (source, target) in enumerate(SOURCE_TARGET_MODELS, 2))


class SafeError(Exception):
    """Error controlado sin credenciales."""


class BlockingError(SafeError):
    """Precondicion que bloquea todas las escrituras."""


def normalize_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1") or
            parsed.port != 5000 or parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/") or parsed.netloc not in ("localhost:5000", "127.0.0.1:5000")):
        raise BlockingError("--api-base-url debe ser exactamente http://localhost:5000 o http://127.0.0.1:5000")
    return f"http://{parsed.hostname}:5000"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise SafeError("Redirect HTTP rechazado")


class LocalApiClient:
    GETS = frozenset({
        "/api/categories?include_inactive=true", "/api/brands?include_inactive=true",
        "/api/products?include_unpublished=true", "/api/product-images",
    })

    def __init__(self, origin, token, apply=False):
        self.origin, self._token, self.apply = origin, token, apply
        self.methods = []
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        if method == "GET":
            if path not in self.GETS:
                raise SafeError("Destino GET no permitido")
        elif method == "PATCH":
            if not self.apply or not path.startswith("/api/products/") or not path.removeprefix("/api/products/").isdigit():
                raise SafeError("Destino PATCH no permitido")
            if not isinstance(payload, dict) or set(payload) != {"name", "model"}:
                raise SafeError("Payload PATCH no permitido")
        else:
            raise SafeError(f"Metodo HTTP prohibido: {method}")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"Accept": "application/json", "Authorization": "Bearer " + self._token}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(self.origin + path, data=body, headers=headers, method=method)
        self.methods.append(method)
        try:
            response = self.opener.open(request, timeout=15)
            if response.geturl().split("/api/", 1)[0] != self.origin:
                raise SafeError("Cambio de origen API rechazado")
            if response.headers.get_content_type() != "application/json":
                raise SafeError("MIME JSON inesperado")
            return json.loads(response.read(8 * 1024 * 1024 + 1).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise SafeError(f"HTTP {exc.code} en {method} {path}") from None
        except (urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise SafeError(f"Respuesta local invalida: {type(exc).__name__}") from None

    def get_json(self, path):
        return self.request("GET", path)

    def patch_product(self, product_id, payload):
        return self.request("PATCH", f"/api/products/{product_id}", payload)


def extract_list(value, label):
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        value = value["results"]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SafeError(f"Respuesta invalida para {label}")
    return value


def snapshot(client):
    return {
        "categories": extract_list(client.get_json("/api/categories?include_inactive=true"), "categories"),
        "brands": extract_list(client.get_json("/api/brands?include_inactive=true"), "brands"),
        "products": extract_list(client.get_json("/api/products?include_unpublished=true"), "products"),
        "images": extract_list(client.get_json("/api/product-images"), "images"),
    }


def nested_id(value):
    return value.get("id") if isinstance(value, dict) else value


def classify(state):
    categories = [c for c in state["categories"] if c.get("name") == "Elevadores tipo tijera eléctricos"]
    brands = [b for b in state["brands"] if b.get("name") == "LGMG"]
    category_ids = {categories[0].get("id")} if len(categories) == 1 else set()
    brand_ids = {brands[0].get("id")} if len(brands) == 1 else set()
    by_id = {}
    for product in state["products"]:
        by_id.setdefault(product.get("id"), []).append(product)
    image_map = {}
    for image in state["images"]:
        image_map.setdefault(nested_id(image.get("product")) or image.get("product_id"), []).append(image)
    rows = []
    for approved in CATALOG:
        matches = by_id.get(approved["product_id"], [])
        row = {**approved, "original_slug": "", "action": "missing", "result": "blocked", "error": "Producto ausente"}
        if len(matches) == 1:
            product = matches[0]
            row["original_slug"] = product.get("slug", "")
            source = product.get("name") == approved["source_name"] and product.get("model") == approved["source_model"]
            target = product.get("name") == approved["target_name"] and product.get("model") == approved["target_model"]
            images = image_map.get(approved["product_id"], [])
            errors = []
            if nested_id(product.get("brand")) not in brand_ids: errors.append("marca no es LGMG")
            if nested_id(product.get("category")) not in category_ids: errors.append("subcategoria incorrecta")
            if product.get("is_published") is not False: errors.append("producto publicado")
            if product.get("is_featured") is not False: errors.append("producto destacado")
            if len(images) != 1 or images[0].get("is_main") is not True: errors.append("imagen principal no unica")
            if not source and not target: errors.append("nombre/modelo en estado intermedio o incompatible")
            if errors:
                row.update(action="conflict", error="; ".join(errors))
            elif target:
                row.update(action="already_canonical", result="unchanged", error="")
            else:
                row.update(action="rename", result="pending", error="")
        elif len(matches) > 1:
            row.update(action="conflict", error="ID ambiguo")
        rows.append(row)
    # Closed table itself must remain collision-free.
    if len({r["source_model"] for r in CATALOG}) != 21 or len({r["target_model"] for r in CATALOG}) != 21:
        raise BlockingError("Mapeo aprobado ambiguo")
    return rows


def stable_record(state, product_id):
    product = next((p for p in state["products"] if p.get("id") == product_id), None)
    images = [i for i in state["images"] if (nested_id(i.get("product")) or i.get("product_id")) == product_id]
    return json.loads(json.dumps({"product": product, "images": images}, sort_keys=True))


def verify_after(before, after):
    if {p.get("id") for p in before["products"]} != {p.get("id") for p in after["products"]}:
        raise SafeError("Verificacion: se creo o elimino un producto")
    if stable_record(before, 1) != stable_record(after, 1):
        raise SafeError("Verificacion: producto ID 1 cambio")
    rows = classify(after)
    if any(r["action"] != "already_canonical" for r in rows):
        raise SafeError("Verificacion: no existen exactamente 21 estados finales")
    before_by_id = {p["id"]: p for p in before["products"]}
    after_by_id = {p["id"]: p for p in after["products"]}
    for approved in CATALOG:
        product_id = approved["product_id"]
        for field in ("slug", "brand", "category", "is_published", "is_featured"):
            if before_by_id[product_id].get(field) != after_by_id[product_id].get(field):
                raise SafeError(f"Verificacion: {field} cambio en ID {product_id}")
        if "Ⅱ" in approved["target_model"]:
            raise SafeError("Verificacion: numero romano en modelo final")
        if stable_record(before, product_id)["images"] != stable_record(after, product_id)["images"]:
            raise SafeError(f"Verificacion: imagen cambio en ID {product_id}")


def write_outputs(output, result):
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and (output.is_symlink() or not output.is_dir() or any(output.iterdir())):
        raise SafeError("--output-dir debe ser nuevo o vacio y no symlink")
    output.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".canonicalization-", dir=output))
    try:
        fields = ["product_id", "source_model", "target_model", "source_name", "target_name", "original_slug", "action", "result", "error"]
        with (staging / OUTPUT_NAMES[0]).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fields, lineterminator="\r\n"); writer.writeheader(); writer.writerows(result["rows"])
        with (staging / OUTPUT_NAMES[1]).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, ["product_id", "error"], lineterminator="\r\n"); writer.writeheader()
            writer.writerows({"product_id": r["product_id"], "error": r["error"]} for r in result["rows"] if r["error"])
        counts = {
            "products_examined": sum(r["action"] != "missing" for r in result["rows"]),
            "products_pending": sum(r["action"] == "rename" and r["result"] != "updated" for r in result["rows"]),
            "products_updated": sum(r["result"] == "updated" for r in result["rows"]),
            "products_already_canonical": sum(r["action"] == "already_canonical" for r in result["rows"]),
            "conflicts": sum(r["action"] in ("conflict", "missing") for r in result["rows"]),
        }
        summary = {"verdict": result["verdict"], "mode": result["mode"], **counts, "updated_ids": result["updated_ids"], "failed_id": result["failed_id"]}
        (staging / OUTPUT_NAMES[2]).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[3]).write_text("\n".join(f"{k}: {v}" for k, v in summary.items()) + "\n", encoding="utf-8")
        manifest = {"tool": "canonicalize_lgmg_scissors_catalog", "version": TOOL_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(), "mode": result["mode"],
            "http_methods_used": sorted(set(result["methods"])), **counts,
            "confirmations_received": result["confirmations"], "content_published": False,
            "products_created": 0, "products_deleted": 0, "images_modified": 0,
            "slugs_modified": 0, "credentials_persisted": False}
        (staging / OUTPUT_NAMES[4]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[5]).write_text(
            "CANONIZACION CERRADA LGMG\n\nRevise CSV y resumen. No cambia slugs, imagenes, publicacion ni el producto ID 1.\n", encoding="utf-8")
        for name in OUTPUT_NAMES: os.replace(staging / name, output / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def run(base_url, output, apply, confirmed, token, client_factory=LocalApiClient):
    origin = normalize_origin(base_url)
    client = client_factory(origin, token, apply=apply and confirmed)
    before = snapshot(client)
    rows = classify(before)
    blocked = any(r["action"] in ("conflict", "missing") for r in rows)
    updated_ids, failed_id = [], None
    if apply and confirmed and not blocked:
        for row in rows:
            if row["action"] != "rename": continue
            try:
                client.patch_product(row["product_id"], {"name": row["target_name"], "model": row["target_model"]})
                row["result"] = "updated"; updated_ids.append(row["product_id"])
            except SafeError as exc:
                failed_id = row["product_id"]; row["result"] = "failed"; row["error"] = str(exc)[:240]
                break
        if failed_id is None:
            verify_after(before, snapshot(client))
    verdict = "NO_GO" if blocked else ("PARTIAL" if failed_id else "GO")
    result = {"rows": rows, "mode": "apply" if apply and confirmed else "dry_run", "methods": client.methods,
              "confirmations": {"apply": apply, "confirm_lgmg_scissors_canonicalization": confirmed},
              "updated_ids": updated_ids, "failed_id": failed_id, "verdict": verdict}
    write_outputs(output, result)
    return 3 if blocked else (2 if failed_id else 0)


def access_token(environ=os.environ):
    token = environ.get(TOKEN_ENV, "")
    if not token or "\r" in token or "\n" in token:
        raise BlockingError(f"Defina {TOKEN_ENV} con una sesion local valida")
    return token


def build_parser():
    parser = argparse.ArgumentParser(description="Canonizacion local cerrada de 21 tijeras LGMG")
    parser.add_argument("--api-base-url", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-lgmg-scissors-canonicalization", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.apply != args.confirm_lgmg_scissors_canonicalization:
        print("NO_GO: apply exige ambas confirmaciones explicitas", file=sys.stderr); return 3
    try:
        return run(args.api_base_url, Path(args.output_dir), args.apply,
                   args.confirm_lgmg_scissors_canonicalization, access_token())
    except BlockingError as exc:
        print("NO_GO: " + str(exc)[:240], file=sys.stderr); return 3
    except (SafeError, OSError) as exc:
        print("Error operativo: " + str(exc)[:240], file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
