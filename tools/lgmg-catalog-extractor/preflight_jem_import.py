#!/usr/bin/env python3
"""Read-only, local-only preflight for the approved LGMG import plan."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

TOOL_NAME = "lgmg-jem-local-import-preflight"
TOOL_VERSION = "1.0.0"
PLAN_TOOL = "lgmg-jem-import-plan-generator"
MEDIA_TOOL = "lgmg-jem-review-media-downloader"
TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
TOKEN_MAX = 8192
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
IMAGE_MAX = 5 * 1024 * 1024
PDF_MAX = 10 * 1024 * 1024
LOCAL_ORIGINS = {"http://localhost:5000", "http://127.0.0.1:5000"}
ALLOWED_REQUESTS = {
    ("/api/health", ""), ("/api/auth/me", ""),
    ("/api/categories", "include_inactive=true"),
    ("/api/brands", "include_inactive=true"),
    ("/api/products", "include_unpublished=true&ordering=name"),
    ("/api/technical-sheets", ""),
}
COMMERCIAL_REQUESTS = (
    ("/api/categories", {"include_inactive": "true"}),
    ("/api/brands", {"include_inactive": "true"}),
    ("/api/products", {"include_unpublished": "true", "ordering": "name"}),
    ("/api/technical-sheets", None),
)
OUTPUTS = (
    "preflight-categories.csv", "preflight-brand.csv", "preflight-products.csv",
    "preflight-specifications.csv", "preflight-media.csv", "preflight-warnings.csv",
    "preflight-actions.csv", "preflight-snapshot.json", "preflight-summary.json",
    "preflight-summary.txt", "README-preflight.txt", "preflight-manifest.json",
)
PLAN_FILES = (
    "import-products.csv", "import-specifications.csv", "import-images.csv",
    "import-datasheets.csv", "import-categories.csv", "import-brand.csv",
    "import-warnings.csv", "manual-actions.csv", "import-plan.json",
    "import-summary.json", "import-summary.txt", "README-import-plan.txt",
)
MEDIA_REPORTS = ("media-files.csv", "downloaded-images.csv", "downloaded-datasheets.csv", "media-failures.csv", "media-summary.json")
TARGETS = (
    "Elevadores tipo tijera eléctricos", "Elevadores tipo tijera todoterreno",
    "Elevadores tipo brazo articulado", "Elevadores tipo brazo telescópico",
    "Elevadores tipo mástil vertical", "Elevadores tipo tijera sobre orugas",
    "Manipuladores telescópicos",
)
ALIAS = "Elevador tipo tijera electrico"
PRODUCT_FIELDS = {
    "source_key", "proposed_name", "metric_model", "imperial_model",
    "target_power_source", "maximum_load_capacity_kg", "product_type",
    "condition", "stock_status", "price", "currency", "show_price",
    "is_published", "is_featured", "ready_for_import",
    "target_root_category", "target_subcategory", "target_brand",
}
MISSING_DATASHEET_MODELS = {"AR24JE", "T38JE"}


class PreflightError(ValueError):
    """Sanitized input, local API, or report error."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PreflightError("La API local respondió con una redirección rechazada")


def normalize_origin(value: str) -> str:
    candidate = (value or "").rstrip("/")
    parsed = urllib.parse.urlsplit(candidate)
    if candidate not in LOCAL_ORIGINS or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise PreflightError("El origen debe ser exactamente localhost o 127.0.0.1 por HTTP en el puerto 5000")
    return candidate


def access_token(environ=None) -> str:
    value = (environ if environ is not None else os.environ).get(TOKEN_ENV)
    if value is None or not value.strip():
        raise PreflightError(f"Falta {TOKEN_ENV} o está vacío")
    if len(value) > TOKEN_MAX or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", value):
        raise PreflightError("El access token no tiene una estructura JWT admitida")
    return value


class LocalJsonClient:
    """Fail-closed JSON reader; deliberately exposes no arbitrary HTTP method."""

    def __init__(self, base_url, token, opener=None, timeout=TIMEOUT_SECONDS, max_body=MAX_RESPONSE_BYTES):
        self.base_url = normalize_origin(base_url)
        self.__token = token
        self._opener = opener or urllib.request.build_opener(NoRedirect())
        self.timeout = timeout
        self.max_body = max_body
        self.request_count = 0
        self.endpoints = []

    def get_json(self, path, query=None, authenticated=True):
        if not isinstance(path, str) or not path.startswith("/") or "?" in path or "#" in path:
            raise PreflightError("Ruta GET no admitida")
        encoded = urllib.parse.urlencode(query or {})
        if (path, encoded) not in ALLOWED_REQUESTS:
            raise PreflightError("Endpoint GET fuera de la allowlist")
        url = self.base_url + path + (("?" + encoded) if encoded else "")
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + self.__token
        request = urllib.request.Request(url, headers=headers, method="GET")
        self.request_count += 1
        self.endpoints.append("GET " + path + (("?" + encoded) if encoded else ""))
        try:
            response = self._opener.open(request, timeout=self.timeout)
            status = getattr(response, "status", response.getcode())
            final = response.geturl()
            if final != url or urllib.parse.urlsplit(final).netloc != urllib.parse.urlsplit(self.base_url).netloc:
                raise PreflightError("Respuesta redirigida o fuera del origen local")
            if status < 200 or status >= 300:
                raise PreflightError(f"La API local respondió HTTP {status}")
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise PreflightError("La API local no devolvió application/json")
            body = response.read(self.max_body + 1)
            if len(body) > self.max_body:
                raise PreflightError("La respuesta JSON supera el límite")
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PreflightError("La API local devolvió JSON inválido") from exc
        except urllib.error.HTTPError as exc:
            raise PreflightError(f"La API local respondió HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PreflightError("No fue posible leer la API local") from exc


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


def slugify(value):
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    output = []
    separator = False
    for char in text:
        if unicodedata.category(char) == "Mn": continue
        if char.isalpha() or char.isdigit(): output.append(char); separator = False
        elif char.isspace() or char in "-_/":
            if output and not separator: output.append("-"); separator = True
    return "".join(output).strip("-")


def safe_relative(value):
    if not isinstance(value, str) or "\\" in value or not value or any(ord(c) < 32 for c in value):
        raise PreflightError("Ruta relativa inválida")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in path.parts) or path.as_posix() != value:
        raise PreflightError("Ruta relativa no canónica o traversal")
    return value


def csv_rows(data, name):
    try: return list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
    except (UnicodeDecodeError, csv.Error) as exc: raise PreflightError(f"CSV inválido: {name}") from exc


def json_value(data, name):
    try: return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise PreflightError(f"JSON inválido: {name}") from exc


def safe_paths(plan, media, output):
    for item in (plan, media):
        if item.is_symlink() or not item.is_dir(): raise PreflightError("Las entradas deben ser carpetas físicas seguras")
    resolved = (plan.resolve(), media.resolve(), output.resolve(strict=False))
    if len(set(resolved)) != 3: raise PreflightError("Entradas y salida deben ser distintas")
    if len(resolved[2].parts) < 3 or resolved[2] in (Path(resolved[2].anchor), Path.home().resolve()):
        raise PreflightError("Salida demasiado amplia")
    if any(a in b.parents or b in a.parents for a in resolved[:2] for b in (resolved[2],)):
        raise PreflightError("Entradas y salida no pueden contenerse")
    current = resolved[2]
    while not current.exists() and current != current.parent: current = current.parent
    if current.is_symlink() or (output.exists() and output.is_symlink()): raise PreflightError("Salida mediante symlink")
    if output.exists() and (not output.is_dir() or any(output.iterdir())): raise PreflightError("La salida debe ser nueva o vacía")


def read_closed_package(root, required, manifest_name):
    raw = {}
    for name in (*required, manifest_name):
        item = root / name
        if not item.is_file() or item.is_symlink(): raise PreflightError(f"Archivo obligatorio ausente o inseguro: {name}")
        raw[name] = item.read_bytes()
    return raw


def validate_inputs(plan_root, media_root):
    plan_raw = read_closed_package(plan_root, PLAN_FILES, "import-manifest.json")
    pm = json_value(plan_raw["import-manifest.json"], "import-manifest.json")
    if pm.get("tool") != PLAN_TOOL or pm.get("version") != "1.0.0": raise PreflightError("Manifest de plan no admitido")
    declared = {x.get("name"): x for x in pm.get("generated_files", []) if isinstance(x, dict)}
    for name in PLAN_FILES:
        if name not in declared or declared[name].get("size") != len(plan_raw[name]) or declared[name].get("sha256") != sha(plan_raw[name]):
            raise PreflightError(f"Hash o tamaño del plan inconsistente: {name}")
    if any(pm.get(k) != v for k, v in {"ready_for_import":False,"content_published":False,"network_used":False}.items()):
        raise PreflightError("Estado conservador del plan incumplido")
    rows = {name: csv_rows(plan_raw[name], name) for name in PLAN_FILES if name.endswith(".csv")}
    expected = {"import-products.csv":57,"import-specifications.csv":1635,"import-images.csv":127,"import-datasheets.csv":57,
                "import-categories.csv":7,"import-brand.csv":1,"import-warnings.csv":44,"manual-actions.csv":7}
    if any(len(rows[name]) != count for name,count in expected.items()): raise PreflightError("Conteos aprobados del plan incumplidos")
    products = rows["import-products.csv"]
    if not products or not PRODUCT_FIELDS.issubset(products[0]):
        raise PreflightError("Esquema canónico de productos incompleto")
    if sum(r.get("target_power_source") == "electric_24v" for r in products) != 13 or sum(r.get("target_power_source") == "electric_lithium" for r in products) != 2:
        raise PreflightError("Conteos de energía del plan incumplidos")
    if sum(not r.get("target_power_source") for r in products) != 42 or sum(bool(r.get("maximum_load_capacity_kg")) for r in products) != 57:
        raise PreflightError("Fuentes o capacidades aprobadas incumplidas")
    if any(r.get("ready_for_import", "").casefold() != "false" or r.get("is_published", "").casefold() != "false" or
           r.get("is_featured", "").casefold() != "false" or r.get("show_price", "").casefold() != "false" or
           r.get("price") or r.get("currency") for r in products):
        raise PreflightError("Estado comercial conservador del producto incumplido")
    datasheets = rows["import-datasheets.csv"]
    available = [r for r in datasheets if r.get("datasheet_status") == "available_at_source"]
    missing = [r for r in datasheets if r.get("datasheet_status") == "missing_at_source"]
    if len(available) != 55 or len(missing) != 2 or {r.get("metric_model") for r in missing} != MISSING_DATASHEET_MODELS:
        raise PreflightError("Conteos o ausencias de fichas técnicas incumplidos")
    if any(r.get("local_file") or r.get("sha256") or r.get("size_bytes") or r.get("mime_type") for r in missing):
        raise PreflightError("Una ficha ausente contiene referencias físicas")
    if len({r.get("local_file") for r in available}) != 53:
        raise PreflightError("Conteo de PDF físicos únicos incumplido")
    media_raw = read_closed_package(media_root, MEDIA_REPORTS, "media-manifest.json")
    mm = json_value(media_raw["media-manifest.json"], "media-manifest.json")
    if mm.get("tool") != MEDIA_TOOL or mm.get("version") != "1.0.0": raise PreflightError("Manifest de medios no admitido")
    if any(mm.get(k) != v for k,v in {"jem_nexus_called":False,"products_imported":0,"content_published":False,"all_products_ready_for_import":False,"package_complete":True}.items()):
        raise PreflightError("Estado conservador del paquete de medios incumplido")
    if pm.get("media_fingerprint_sha256") != sha(media_raw["media-manifest.json"]): raise PreflightError("Fingerprint cruzado de medios incorrecto")
    files = {safe_relative(x.get("name", "")):x for x in mm.get("files", []) if isinstance(x,dict)}
    actual = set()
    for item in media_root.rglob("*"):
        if item.is_symlink(): raise PreflightError("Symlink detectado en medios")
        if item.is_file(): actual.add(item.relative_to(media_root).as_posix())
    if actual != set(files) | {"media-manifest.json"}: raise PreflightError("Conjunto cerrado de medios inconsistente")
    for name,item in files.items():
        data=(media_root / name).read_bytes()
        if item.get("size") != len(data) or item.get("sha256") != sha(data): raise PreflightError("Hash físico de medio inconsistente")
    return {"manifest":pm,"rows":rows,"fingerprint":pm.get("combined_fingerprint_sha256")}, {"manifest":mm,"rows":{n:csv_rows(media_raw[n],n) for n in MEDIA_REPORTS if n.endswith('.csv')},"fingerprint":sha(media_raw["media-manifest.json"])}


def extract_list(value, label):
    if isinstance(value, dict) and isinstance(value.get("results"), list): value=value["results"]
    if not isinstance(value, list) or not all(isinstance(x,dict) for x in value): raise PreflightError(f"Respuesta inválida para {label}")
    return value


def commercial_snapshot(client):
    values = [extract_list(client.get_json(p,q),p) for p,q in COMMERCIAL_REQUESTS]
    snap = dict(zip(("categories","brands","products","technical_sheets"), values))
    for category in snap["categories"]:
        if not all(k in category for k in ("id","name","parent","product_type","is_active")): raise PreflightError("Categoría local incompleta")
    for brand in snap["brands"]:
        if not all(k in brand for k in ("id","name","slug","is_active")): raise PreflightError("Marca local incompleta")
    for product in snap["products"]:
        if not all(k in product for k in ("id","name","slug","model","brand","category","is_published")): raise PreflightError("Producto local incompleto")
    for sheet in snap["technical_sheets"]:
        if not all(k in sheet for k in ("id","name","original_file_name","content_type","size_bytes")): raise PreflightError("Ficha local incompleta")
    return snap, sha(canonical_json(snap))


def resolve_categories(categories):
    roots=[c for c in categories if normalized(c.get("name"))==normalized("Maquinarias")]
    valid=[c for c in roots if c.get("parent") is None and c.get("product_type")=="machinery" and c.get("is_active") is True]
    rows=[]; blockers=[]
    if len(roots)!=1 or len(valid)!=1: blockers.append("invalid_machinery_root")
    root=valid[0] if len(valid)==1 else None
    for target in TARGETS:
        exact=[c for c in categories if root and c.get("parent")==root["id"] and normalized(c.get("name"))==normalized(target)]
        aliases=[c for c in categories if target==TARGETS[0] and root and c.get("parent")==root["id"] and normalized(c.get("name"))==normalized(ALIAS)]
        matches=exact+aliases
        if len(matches)>1: action="conflict_requires_review"; block=True
        elif matches:
            c=matches[0]; action="reuse_exact" if exact else "rename_and_reuse"; block=c.get("product_type")!="machinery"
            if c.get("is_active") is not True: action="reactivation_required"
        else: c={}; action="create_required"; block=False
        if block: blockers.append("category_conflict:"+target)
        rows.append({"source_category":target,"target_name":target,"local_id":c.get("id",""),"parent_id":c.get("parent",""),
            "product_type":c.get("product_type","machinery"),"is_active":c.get("is_active",""),"exact_match":bool(exact),
            "normalized_match":bool(matches),"known_alias":bool(aliases),"proposed_action":action,"human_review":action!="reuse_exact","blocking":block})
    return rows, blockers, root


def resolve_brand(brands):
    matches=[b for b in brands if normalized(b.get("name"))=="lgmg" or normalized(b.get("slug"))=="lgmg"]
    if not matches: return [{"name":"LGMG","local_id":"","slug":"","is_active":"","proposed_action":"create_required","blocking":False}],[]
    if len(matches)>1: action="conflict_requires_review"; block=True; b={}
    else: b=matches[0]; action="reuse_exact" if b.get("is_active") is True else "reactivation_required"; block=False
    return [{"name":"LGMG","local_id":b.get("id",""),"slug":b.get("slug",""),"is_active":b.get("is_active",""),"proposed_action":action,"blocking":block}], (["brand_conflict"] if block else [])


def nested_name(value):
    return value.get("name","") if isinstance(value,dict) else ""


def resolve_products(plan_products, local_products):
    rows=[]; blockers=[]; proposed={}
    for p in plan_products:
        proposed_name=p.get("proposed_name", "")
        model=normalized(p.get("metric_model")); imperial=normalized(p.get("imperial_model")); name=normalized(proposed_name); proposed_slug=slugify(proposed_name)
        if not name or not proposed_slug:
            blockers.append("empty_proposed_name_or_slug:"+p.get("source_key", ""))
        proposed.setdefault(proposed_slug,[]).append(p.get("source_key"))
        model_hits=[x for x in local_products if normalized(x.get("model")) in {model,imperial}-{''}]
        lgmg=[x for x in model_hits if normalized(nested_name(x.get("brand")))=="lgmg"]
        name_hits=[x for x in local_products if normalized(x.get("name"))==name]
        slug_hits=[x for x in local_products if normalized(x.get("slug"))==normalized(proposed_slug)]
        candidates={x.get("id"):x for x in model_hits+name_hits+slug_hits}
        if len(candidates)>1: status="multiple_matches"; block=True
        elif lgmg: status="existing_lgmg_model"; block=False
        elif model_hits: status="model_other_brand_collision"; block=True
        elif name_hits: status="name_collision"; block=True
        elif slug_hits: status="slug_collision"; block=True
        else: status="new_candidate"; block=False
        if block: blockers.append(status+":"+p.get("source_key",""))
        hit=next(iter(candidates.values()),{})
        rows.append({"source_key":p.get("source_key"),"metric_model":p.get("metric_model"),"imperial_model":p.get("imperial_model"),
            "proposed_name":proposed_name,"proposed_slug":proposed_slug,"classification":status,"local_id":hit.get("id",""),
            "local_brand":nested_name(hit.get("brand")),"local_category":nested_name(hit.get("category")),"local_published":hit.get("is_published",""),"blocking":block})
    for slug,keys in proposed.items():
        if slug and len(keys)>1: blockers.append("planned_slug_collision:"+slug)
    return rows,blockers


def jlg_candidates(products):
    allowed={normalized(TARGETS[0]),normalized(ALIAS)}; found=[]
    for p in products:
        if normalized(nested_name(p.get("brand")))=="jlg" and normalized(nested_name(p.get("category"))) in allowed:
            found.append({"action":"review_example_product_removal","candidate_count":0,"id":p.get("id"),"name":p.get("name"),"slug":p.get("slug"),
                "model":p.get("model"),"category":nested_name(p.get("category")),"brand":nested_name(p.get("brand")),"published":p.get("is_published"),
                "reason":"Marca JLG exacta y categoría controlada de tijera"})
    for row in found: row["candidate_count"]=len(found)
    return found, (["multiple_jlg_candidates"] if len(found)>1 else [])


def validate_contracts(plan, media, media_root, local_sheets):
    blockers=[]; spec_rows=[]; media_rows=[]
    products={p["source_key"]:p for p in plan["rows"]["import-products.csv"]}
    for p in products.values():
        valid=(PRODUCT_FIELDS.issubset(p) and 0<len(p.get("proposed_name", ""))<=220 and bool(slugify(p.get("proposed_name"))) and
               len(p.get("metric_model",""))<=120 and p.get("product_type")=="machinery" and p.get("condition")=="new" and
               p.get("stock_status")=="on_request" and p.get("target_power_source") in ("","diesel","electric_24v","electric_lithium") and
               p.get("price")=="" and p.get("currency")=="" and p.get("target_root_category")=="Maquinarias" and
               p.get("target_subcategory") in TARGETS and p.get("target_brand")=="LGMG" and
               all(p.get(field,"").casefold()=="false" for field in ("is_featured","is_published","show_price","ready_for_import")) and
               float(p.get("maximum_load_capacity_kg") or 0)>0)
        if not valid: blockers.append("product_contract:"+p["source_key"])
    seen=set()
    for row in plan["rows"]["import-specifications.csv"]:
        key=(row.get("source_key"),row.get("normalized_label") or row.get("source_label"),row.get("specification_order"))
        valid=(row.get("source_key") in products and 0<len(row.get("source_label", ""))<=120 and len(row.get("normalized_label",""))<=120 and
               0<len(row.get("source_value", ""))<=220 and len(row.get("unit",""))<=40 and key not in seen)
        seen.add(key)
        if not valid: blockers.append("specification_contract:"+str(row.get("source_key")))
        spec_rows.append({**row,"compatible":valid,"blocking":not valid,"value_length":len(row.get("source_value",""))})
    file_map={r["local_file"]:r for r in media["rows"]["media-files.csv"]}
    for kind,name in (("image","import-images.csv"),("datasheet","import-datasheets.csv")):
        primary={}
        for row in plan["rows"][name]:
            if kind=="datasheet" and row.get("datasheet_status")=="missing_at_source":
                media_rows.append({"media_type":kind,"source_key":row.get("source_key"),"order":"","local_file":"","sha256":"",
                    "size_bytes":"","mime_type":"","compatible":True,"reuse_status":"missing_at_source","blocking":False})
                continue
            rel=safe_relative(row.get("local_file","")); physical=file_map.get(rel,{}); data=(media_root/rel).read_bytes()
            ext=Path(rel).suffix.casefold(); mime=row.get("mime_type",""); size=len(data)
            signature=((ext in (".jpg",".jpeg") and data[:3]==b"\xff\xd8\xff") or (ext==".png" and data[:8]==b"\x89PNG\r\n\x1a\n") or
                       (ext==".webp" and data[:4]==b"RIFF" and data[8:12]==b"WEBP") or (ext==".pdf" and data[:5]==b"%PDF-"))
            if kind=="image": valid=ext in (".jpg",".jpeg",".png",".webp") and mime in ("image/jpeg","image/png","image/webp") and size<=IMAGE_MAX
            else: valid=ext==".pdf" and mime=="application/pdf" and size<=PDF_MAX
            valid=valid and signature and row.get("sha256")==sha(data) and str(row.get("size_bytes"))==str(size) and physical.get("sha256")==sha(data)
            if kind=="image" and str(row.get("primary_candidate","")).casefold()=="true": primary[row["source_key"]]=primary.get(row["source_key"],0)+1
            reuse=""
            if kind=="datasheet":
                reuse="reuse_candidate" if any(normalized(s.get("name"))==normalized(Path(rel).stem) and s.get("size_bytes")==size and s.get("content_type")==mime for s in local_sheets) else "create_candidate"
            if not valid: blockers.append(kind+"_contract:"+row.get("source_key",""))
            media_rows.append({"media_type":kind,"source_key":row.get("source_key"),"order":row.get("image_order") or row.get("datasheet_order"),
                "local_file":rel,"sha256":row.get("sha256"),"size_bytes":size,"mime_type":mime,"compatible":valid,"reuse_status":reuse,"blocking":not valid})
        if kind=="image" and any(v!=1 for v in primary.values()): blockers.append("image_primary_count")
    return spec_rows,media_rows,blockers


def verdict(blockers, actions):
    if blockers: return "NO_GO"
    return "CONDITIONAL_GO" if actions else "GO"


def write_csv(path, rows):
    fields=list(rows[0]) if rows else ["status"]
    with path.open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fields,extrasaction="ignore",lineterminator="\r\n"); writer.writeheader(); writer.writerows(rows)


def write_reports(output, result):
    output.mkdir(parents=True,exist_ok=True); staging=output/".staging"
    try:
        staging.mkdir()
        mappings={"preflight-categories.csv":result["categories"],"preflight-brand.csv":result["brand"],"preflight-products.csv":result["products"],
            "preflight-specifications.csv":result["specifications"],"preflight-media.csv":result["media"],"preflight-warnings.csv":result["warnings"],"preflight-actions.csv":result["actions"]}
        for name,rows in mappings.items(): write_csv(staging/name,rows)
        snapshot={"initial_sha256":result["initial_hash"],"final_sha256":result["final_hash"],"commercial_snapshot_unchanged":result["unchanged"],
            "concurrent_change_detected":not result["unchanged"],"counts":{k:len(v) for k,v in result["snapshot"].items()}}
        summary={"verdict":result["verdict"],"blockers":result["blockers"],"counts":result["counts"],"ready_for_import":False,"content_published":False,"apply_performed":False}
        (staging/"preflight-snapshot.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (staging/"preflight-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (staging/"preflight-summary.txt").write_text(f"Veredicto: {result['verdict']}\nBloqueos: {len(result['blockers'])}\nready_for_import: false\ncontent_published: false\napply_performed: false\n",encoding="utf-8")
        (staging/"README-preflight.txt").write_text("PREFLIGHT LOCAL LGMG\n\nInforme declarativo de solo lectura. No importa, modifica, elimina, sube ni publica contenido. Las acciones requieren revisión humana.\n",encoding="utf-8")
        generated=[]
        for name in OUTPUTS[:-1]:
            data=(staging/name).read_bytes(); generated.append({"name":name,"size":len(data),"sha256":sha(data)})
        manifest={"tool":TOOL_NAME,"version":TOOL_VERSION,"created_at_utc":datetime.now(timezone.utc).isoformat(),"plan_fingerprint_sha256":result["plan_fp"],
            "media_fingerprint_sha256":result["media_fp"],"local_api_origin":result["origin"],"get_endpoints_consulted":result["endpoints"],
            "read_request_count":result["request_count"],"http_methods_used":["GET"],"commercial_snapshot_initial_sha256":result["initial_hash"],
            "commercial_snapshot_final_sha256":result["final_hash"],"commercial_snapshot_unchanged":result["unchanged"],"verdict":result["verdict"],
            "counts":result["counts"],"generated_files":generated,"local_api_called":True,"external_network_used":False,"api_write_requests":0,
            "login_called":False,"refresh_called":False,"logout_called":False,"database_changed_by_tool":False,"categories_changed":False,
            "brands_changed":False,"products_created":0,"products_updated":0,"products_deleted":0,"images_uploaded":0,"datasheets_uploaded":0,
            "content_published":False,"apply_performed":False,"ready_for_import":False,"credentials_persisted":False}
        (staging/"preflight-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        for item in staging.iterdir(): os.replace(item,output/item.name)
        staging.rmdir()
    except Exception:
        if staging.exists(): shutil.rmtree(staging)
        if output.exists() and not any(output.iterdir()): output.rmdir()
        raise


def run(plan_root,media_root,base_url,output,token,client_factory=LocalJsonClient):
    safe_paths(plan_root,media_root,output); plan,media=validate_inputs(plan_root,media_root); origin=normalize_origin(base_url)
    client=client_factory(origin,token); client.get_json("/api/health",authenticated=False); me=client.get_json("/api/auth/me")
    if not isinstance(me,dict) or not me.get("id"): raise PreflightError("Sesión local no válida")
    snapshot,initial=commercial_snapshot(client); categories,blocks,root=resolve_categories(snapshot["categories"]); brand,b=resolve_brand(snapshot["brands"]); blocks+=b
    products,b=resolve_products(plan["rows"]["import-products.csv"],snapshot["products"]); blocks+=b
    jlg,b=jlg_candidates(snapshot["products"]); blocks+=b
    specs,media_rows,b=validate_contracts(plan,media,media_root,snapshot["technical_sheets"]); blocks+=b
    actions=[{"action":r["proposed_action"],"subject":r["target_name"],"human_review":True} for r in categories if r["proposed_action"]!="reuse_exact"]
    actions += [{"action":brand[0]["proposed_action"],"subject":"LGMG","human_review":True}] if brand[0]["proposed_action"]!="reuse_exact" else []
    actions += jlg or [{"action":"review_example_product_removal","candidate_count":0,"reason":"No se encontró candidato exacto; revisar manualmente"}]
    counts={"categories_to_create":sum(r["proposed_action"]=="create_required" for r in categories),"categories_to_rename":sum(r["proposed_action"]=="rename_and_reuse" for r in categories),
        "products_to_create":sum(r["classification"]=="new_candidate" for r in products),"specifications_to_create":len(specs),"image_associations":127,
        "datasheet_rows_total":57,"datasheet_associations":55,"physical_datasheet_files":53,"missing_datasheets":2,
        "unique_datasheets_to_create":len({r["sha256"] for r in media_rows if r["media_type"]=="datasheet" and r["reuse_status"]=="create_candidate"}),
        "products_existing_or_review":sum(r["classification"]!="new_candidate" for r in products)}
    if counts["specifications_to_create"]>60 or counts["image_associations"]>20:
        actions.append({"action":"batching_and_resume_required","subject":"future_importer","human_review":True,"description":"Requiere throttling, checkpoints e idempotencia"})
    final_snapshot,final=commercial_snapshot(client); unchanged=initial==final
    if not unchanged: blocks.append("concurrent_commercial_change"); actions=[]
    result={"categories":categories,"brand":brand,"products":products,"specifications":specs,"media":media_rows,
        "warnings":[{"warning":"missing_at_source","source_key":p["source_key"],"model":p["metric_model"],"blocking":False} for p in plan["rows"]["import-products.csv"] if p.get("metric_model") in ("AR24JE","T38JE")],
        "actions":actions,"blockers":blocks,"counts":counts,"snapshot":snapshot,"initial_hash":initial,"final_hash":final,"unchanged":unchanged,
        "plan_fp":plan["fingerprint"],"media_fp":media["fingerprint"],"origin":origin,"endpoints":client.endpoints,"request_count":client.request_count}
    result["verdict"]=verdict(blocks,actions); write_reports(output,result); return result["verdict"]


def build_parser():
    parser=argparse.ArgumentParser(description="Preflight local y de solo lectura para LGMG")
    parser.add_argument("--plan-input",required=True); parser.add_argument("--media-input",required=True)
    parser.add_argument("--api-base-url",required=True); parser.add_argument("--output-dir",required=True)
    return parser


def main(argv=None):
    try:
        args=build_parser().parse_args(argv); token=access_token()
        result=run(Path(args.plan_input),Path(args.media_input),args.api_base_url,Path(args.output_dir),token)
        return 3 if result=="NO_GO" else 0
    except (PreflightError,OSError) as exc:
        print("Error: "+str(exc).splitlines()[0][:240],file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
