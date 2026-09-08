#!/usr/bin/env python3
"""Transferencia cerrada y reanudable del catálogo local LGMG a producción.

La validación del paquete ocurre antes de toda consulta.  Dry-run y verify sólo usan
GET; los POST requieren un checkpoint aprobado y la confirmación literal.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

TOOL_NAME = "transfer_lgmg_catalog_to_production"
TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PROFILE = "lgmg_local_catalog_57"
PACKAGE_NAME = "JEM-LGMG-Transferencia-20260908-000450.zip"
PACKAGE_SIZE = 57_713_145
PACKAGE_SHA256 = "6f986eb3784b7840ae35dfe1f2bd690a8f13cd1815dacc0c2b3342974efc8e2f"
ENTRY_COUNT = 112
JSON_NAME = "JEM-LGMG-Transferencia-Local-20260908.json"
JSON_SIZE = 193_674
JSON_SHA256 = "b94ff6c681b95a362cc01909f9aa9442999852465ef0e9fcbb6d59457f17690e"
MANIFEST_FINGERPRINT = "36e0e5d6f6ad27c82780c6e148116f00e7bf946e0016f4febbcd09cc1528f10e"
API_BASE = "https://api.jem-nexus.cl"
TOKEN_ENV = "JEM_NEXUS_ACCESS_TOKEN"
APPLY_CONFIRMATION = "IMPORTAR_57_LGMG_NO_PUBLICADOS"
STATES = {"production_transfer_dry_run_ready", "production_transfer_in_progress",
          "production_transfer_partial", "production_transfer_complete", "production_transfer_verified"}
MODELS = tuple("""A09JE A09JE-2 A13JE A14JE A14JE-2 AR16JE-2 AR20JE AR20JE-2 AR24JE H625E M0407TE M0810JE S0607 S0607E S0607E-2 S0808 S0808E S0808E-2 S0812 S0812E S0812E-2 S1012 S1012E S1012E-2 S1212 S1212E S1212E-2 S1413 S1413E S1413E-2 SC0407E SC0610E SR0818E SR0818E-2 SR1018E SR1018E-2 SR1218E SR1218E-2 SR1418E SR1623E SS0407ER SS0507E SS0607E T14JE-2 T16JE-2 T18JE-2 T20JE T20JE-2 T22JE T26JE T26JE-2 T28JE T28JE-2 T34JE-2 T38JE T38JE-2 T42JE-2""".split())
WITHOUT_SHEET = ("AR24JE", "H625E", "T38JE")
ALIASES = {x + "-II": x for x in ("S0607", "S0808", "S0812", "S1012", "S1212", "S1413",
                                                "S0607E", "S0808E", "S0812E", "S1012E", "S1212E", "S1413E")}
CATEGORIES = (
    ("Elevadores tipo brazo articulado", "elevadores-tipo-brazo-articulado"),
    ("Elevadores tipo brazo telescópico", "elevadores-tipo-brazo-telescopico"),
    ("Elevadores tipo mástil vertical", "elevadores-tipo-mastil-vertical"),
    ("Elevadores tipo tijera eléctricos", "elevador-electrico"),
    ("Elevadores tipo tijera sobre orugas", "elevadores-tipo-tijera-sobre-orugas"),
    ("Elevadores tipo tijera todoterreno", "elevadores-tipo-tijera-todoterreno"),
    ("Manipuladores telescópicos", "manipuladores-telescopicos"),
)
TILDE_FILES = {
 "Ficha-técnica-LGMG-SR0818E-2.pdf": ("Ficha-tecnica-LGMG-SR0818E-2.pdf", 416611, "68909ba6c87126d9e1cd651320970a9cce1abda5fb35d7f3b5f347cde22d1d0f"),
 "Ficha-técnica-LGMG-SR1218E-2.pdf": ("Ficha-tecnica-LGMG-SR1218E-2.pdf", 406080, "fbfb3916b94d600e19df841560bf11bdf6dee9d7dd26500da44f5894cafde409"),
}
S1212E = (1064335, "53f6cac35264b2b261e511dfd0d15cacd4d4ae95f4b5d878e7e38b9938c839e7")
SECRET = re.compile(r"(?i)(authorization|bearer\s+|password|cookie|secret|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")

class TransferError(ValueError): pass
class ConflictError(TransferError): pass
class AmbiguousMutation(TransferError): pass

def sha256(data): return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def normalize_entry(name):
    if not isinstance(name, str) or not name or "\x00" in name: raise ConflictError("empty_or_invalid_zip_name")
    name = name.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", name) or name.startswith("/") or name.startswith("//"): raise ConflictError("absolute_zip_path")
    p = PurePosixPath(name)
    if any(x in ("", ".", "..") for x in p.parts): raise ConflictError("zip_path_traversal")
    return p.as_posix()

def manifest_fingerprint(entries):
    lines = [f"{name}|{size}|{digest}" for name, size, digest in sorted(entries)]
    return sha256(("\n".join(lines) + "\n").encode())

def _image_size(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return "png", struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        pos = 2
        while pos + 9 < len(data):
            if data[pos] != 0xff: pos += 1; continue
            marker = data[pos + 1]; pos += 2
            if marker in (0xd8, 0xd9) or 0xd0 <= marker <= 0xd7: continue
            if pos + 2 > len(data): break
            length = int.from_bytes(data[pos:pos+2], "big")
            if marker in range(0xc0, 0xc4) and length >= 7:
                return "jpeg", (int.from_bytes(data[pos+5:pos+7], "big"), int.from_bytes(data[pos+3:pos+5], "big"))
            pos += length
    raise ConflictError("unreadable_image")

def validate_image(name, data, model):
    kind, (width, height) = _image_size(data)
    ext = PurePosixPath(name).suffix.lower()
    if (kind == "png") != (ext == ".png") or ext not in (".jpg", ".jpeg", ".png"): raise ConflictError("image_signature_extension")
    if (kind == "png") != (model == "M0810JE"): raise ConflictError("unexpected_png_model")
    if not (450 <= width <= 601 and 600 <= height <= 800): raise ConflictError("image_dimensions")

def validate_pdf(name, data, model):
    if not data or not data.startswith(b"%PDF") or b"%%EOF" not in data[-2048:]: raise ConflictError("invalid_pdf")
    if re.search(br"/Encrypt\b", data): raise ConflictError("encrypted_pdf")
    base = PurePosixPath(name).name
    if "técnica" in base and base not in TILDE_FILES: raise ConflictError("unapproved_accented_prefix")
    if base in TILDE_FILES:
        _, size, digest = TILDE_FILES[base]
        if len(data) != size or sha256(data) != digest: raise ConflictError("accented_pdf_contract")
    if model == "S1212E" and (len(data), sha256(data)) != S1212E: raise ConflictError("s1212e_binary_contract")

def canonical_model(physical):
    if physical in MODELS: return physical
    if physical in ALIASES: return ALIASES[physical]
    raise ConflictError("unapproved_model_alias")

def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if k.casefold() not in {"authorization", "cookie", "token", "access_token", "password"}}
    if isinstance(value, list): return [sanitize(x) for x in value]
    if isinstance(value, str) and SECRET.search(value): return "[REDACTED]"
    return value

def validate_api_base(value):
    p = urllib.parse.urlsplit(value)
    if value != API_BASE or p.scheme != "https" or p.hostname != "api.jem-nexus.cl" or p.port not in (None, 443) or p.username or p.password or p.query or p.fragment or p.path: raise ConflictError("unapproved_api_base")
    return value

def access_token(environ=os.environ):
    token = environ.get(TOKEN_ENV, "")
    if not token or SECRET.search("Bearer " + token) is None: raise ConflictError("missing_access_token")
    return token

def extract_list(value, label):
    if isinstance(value, list): return value
    if isinstance(value, dict):
        for key in ("results", "items", "data"):
            if isinstance(value.get(key), list): return value[key]
    raise ConflictError("invalid_list_response:" + label)

class ApiClient:
    READ_PATHS = ("/api/categories?include_inactive=true", "/api/brands?include_inactive=true",
      "/api/products?include_unpublished=true", "/api/product-images", "/api/product-specs", "/api/technical-sheets")
    def __init__(self, base, token, opener=None, sleep=time.sleep):
        self.base, self.token, self.opener, self.sleep = validate_api_base(base), token, opener or urllib.request.build_opener(), sleep
        self.methods=[]; self.rate_events=[]
    def request(self, method, path, body=None, content_type="application/json"):
        if method not in {"GET", "POST"} or not path.startswith("/api/"): raise ConflictError("method_or_path_not_allowed")
        url=self.base+path; headers={"Accept":"application/json", "Authorization":"Bearer "+self.token}
        if body is not None: headers["Content-Type"]=content_type
        for attempt in range(3):
            try:
                response=self.opener.open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=60)
                final=urllib.parse.urlsplit(response.geturl())
                if final.scheme+"://"+final.netloc != self.base: raise ConflictError("cross_origin_redirect")
                raw=response.read(8*1024*1024+1)
                if len(raw)>8*1024*1024: raise ConflictError("response_too_large")
                self.methods.append(method)
                return json.loads(raw.decode()) if raw else {}
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 2:
                    delay=min(max(float(exc.headers.get("Retry-After", "1")), 0), 30); self.rate_events.append({"code":429,"delay":delay}); self.sleep(delay); continue
                if exc.code in (401,403): raise ConflictError("authentication_or_authorization_failed") from None
                raise ConflictError("http_error") from None
            except (TimeoutError, OSError) as exc:
                if method == "POST": raise AmbiguousMutation("ambiguous_post_result") from None
                raise ConflictError("network_error") from None
        raise ConflictError("rate_limit_exhausted")
    def get(self,path): return self.request("GET",path)
    def post_json(self,path,payload): return self.request("POST",path,canonical(payload))
    def post_file(self,path,fields,filename,data,mime,field_name="file"):
        boundary="----JemNexus"+uuid.uuid4().hex; chunks=[]
        for key,value in fields.items(): chunks += [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()]
        chunks += [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),data,f"\r\n--{boundary}--\r\n".encode()]
        return self.request("POST",path,b"".join(chunks),"multipart/form-data; boundary="+boundary)

def _rows(data, *names):
    for name in names:
        if isinstance(data.get(name), list): return data[name]
    raise ConflictError("missing_json_collection:"+names[0])

def nested_id(value): return value.get("id") if isinstance(value,dict) else value

def validate_capture(data):
    exact={"tool":"JEM-LGMG-transferencia-local","version":"1.0","captured_at":"2026-09-08T03:01:43.619Z","source":"http://localhost:5000","intended_destination":API_BASE}
    if any(data.get(k)!=v for k,v in exact.items()): raise ConflictError("capture_header_contract")
    policy={"force_is_published_false":True,"force_is_featured_false":True,"force_price_visible_false":True}
    counts={"products":57,"images":57,"products_with_sheet":54,"products_without_sheet":3,"categories":7,"brands":1,"specifications":58,"published_local":57,"visible_prices":0,"get_requests":61,"mutating_requests":0}
    if data.get("production_policy") != policy or data.get("counts") != counts or data.get("expected_without_sheet") != list(WITHOUT_SHEET): raise ConflictError("capture_counts_or_policy")
    requests=_rows(data,"requests")
    if len(requests)!=61: raise ConflictError("request_count")
    if SECRET.search(json.dumps(requests,ensure_ascii=False)) or any(r.get("method")!="GET" or not (200<=int(r.get("status",0))<300) for r in requests): raise ConflictError("unsafe_source_requests")
    products=_rows(data,"products"); images=_rows(data,"images","product_images"); specs=_rows(data,"specifications","product_specs")
    cats=_rows(data,"categories"); brands=_rows(data,"brands"); sheets=_rows(data,"technical_sheets","datasheets")
    if len(products)!=57 or len(images)!=57 or len(specs)!=58 or len(cats)!=7 or len(brands)!=1 or len(sheets)!=54: raise ConflictError("collection_counts")
    models=[p.get("model") for p in products]
    if len(set(models))!=57 or set(models)!=set(MODELS): raise ConflictError("product_models")
    ids=[p.get("id") for p in products]; slugs=[p.get("slug") for p in products]
    if len(set(ids))!=57 or None in ids or len(set(slugs))!=57 or any(not x for x in slugs): raise ConflictError("product_identity")
    category_ids={c.get("id") for c in cats}
    if {(c.get("name"),c.get("slug")) for c in cats} != set(CATEGORIES): raise ConflictError("category_contract")
    if brands[0].get("name")!="LGMG" or brands[0].get("slug")!="lgmg": raise ConflictError("brand_contract")
    brand_id=brands[0].get("id")
    by_product={p["id"]:p for p in products}
    for p in products:
        if not p.get("name") or p["model"] not in p["name"] or nested_id(p.get("category")) not in category_ids or nested_id(p.get("brand"))!=brand_id: raise ConflictError("product_taxonomy_relation")
        required=(p.get("product_type")=="machinery" and p.get("condition")=="new" and p.get("stock_status")=="on_request" and p.get("price") is None and p.get("price_visible") is False and p.get("is_featured") is False and p.get("is_published") is True)
        if not required: raise ConflictError("source_product_contract")
        own=[x for x in images if nested_id(x.get("product"))==p["id"]]
        if len(own)!=1 or own[0].get("is_main") is not True or type(own[0].get("order")) is not int or own[0]["order"]!=0 or p.get("main_image")!=own[0]: raise ConflictError("image_relation_contract")
    if any(nested_id(s.get("product")) not in by_product for s in specs): raise ConflictError("spec_relation")
    spec_models=[by_product[nested_id(s["product"])]["model"] for s in specs]
    if spec_models.count("SR0818E-2")!=29 or spec_models.count("SR1018E-2")!=29: raise ConflictError("specification_contract")
    return {"products":products,"images":images,"specifications":specs,"categories":cats,"brands":brands,"sheets":sheets}

def audit_package(path, expected=None):
    expected=expected or {"name":PACKAGE_NAME,"size":PACKAGE_SIZE,"sha":PACKAGE_SHA256,"entries":ENTRY_COUNT,"json_size":JSON_SIZE,"json_sha":JSON_SHA256,"manifest":MANIFEST_FINGERPRINT}
    raw=Path(path).read_bytes()
    if Path(path).name!=expected["name"] or len(raw)!=expected["size"] or sha256(raw)!=expected["sha"]: raise ConflictError("package_identity")
    entries=[]; blobs={}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            seen=set()
            for info in z.infolist():
                name=normalize_entry(info.filename)
                mode=info.external_attr>>16
                if name in seen: raise ConflictError("duplicate_zip_entry")
                seen.add(name)
                if stat.S_ISLNK(mode) or (mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))): raise ConflictError("special_zip_entry")
                if info.is_dir(): continue
                data=z.read(info)
                if not data: raise ConflictError("empty_zip_entry")
                ext=PurePosixPath(name).suffix.lower()
                if ext not in (".json",".pdf",".jpg",".jpeg",".png"): raise ConflictError("unexpected_extension")
                blobs[name]=data; entries.append((name,len(data),sha256(data)))
    except zipfile.BadZipFile as exc: raise ConflictError("invalid_zip") from exc
    if len(entries)!=expected["entries"] or manifest_fingerprint(entries)!=expected["manifest"]: raise ConflictError("manifest_contract")
    json_hits=[n for n in blobs if PurePosixPath(n).name==JSON_NAME]
    pdfs=[n for n in blobs if n.startswith("Fichas tecnicas LGMG/") and n.lower().endswith(".pdf")]
    imgs=[n for n in blobs if n.startswith("Maquinas LGMG/") and PurePosixPath(n).suffix.lower() in (".jpg",".jpeg",".png")]
    if len(json_hits)!=1 or len(pdfs)!=54 or len(imgs)!=57: raise ConflictError("media_counts")
    jr=blobs[json_hits[0]]
    if len(jr)!=expected["json_size"] or sha256(jr)!=expected["json_sha"]: raise ConflictError("json_identity")
    try: capture=json.loads(jr.decode("utf-8-sig"))
    except (UnicodeError,json.JSONDecodeError) as exc: raise ConflictError("invalid_json") from exc
    source=validate_capture(capture)
    image_files={}; sheet_files={}
    for name in imgs:
        model=canonical_model(PurePosixPath(name).stem)
        if model in image_files: raise ConflictError("duplicate_model_image")
        validate_image(name,blobs[name],model); image_files[model]={"path":name,"filename":PurePosixPath(name).name,"data":blobs[name],"content_type":"image/png" if name.lower().endswith(".png") else "image/jpeg"}
    for name in pdfs:
        base=PurePosixPath(name).name
        match=re.fullmatch(r"Ficha-t[eé]cnica-LGMG-(.+)\.pdf",base)
        if not match: raise ConflictError("invalid_datasheet_filename")
        physical=match.group(1); model=canonical_model(physical)
        if model in sheet_files or model in WITHOUT_SHEET: raise ConflictError("duplicate_or_unexpected_datasheet")
        validate_pdf(name,blobs[name],model)
        output_name=TILDE_FILES.get(base,(base,))[0]
        sheet_files[model]={"path":name,"filename":output_name,"data":blobs[name],"content_type":"application/pdf","physical_model":physical}
    if set(image_files)!=set(MODELS) or set(sheet_files)!=set(MODELS)-set(WITHOUT_SHEET): raise ConflictError("media_model_cohort")
    return {"entries":entries,"blobs":blobs,"capture":capture,"source":source,
            "image_files":image_files,"sheet_files":sheet_files,"package_sha256":sha256(raw),"json_sha256":sha256(jr),"manifest_fingerprint":manifest_fingerprint(entries)}

def product_payload(product, category_id, brand_id, sheet_id):
    allowed=("name","slug","product_type","condition","short_description","description","model","sku","working_height_m","terrain_type","year","hours_meter","maximum_load_capacity_kg","machine_weight_kg","power_source","includes_technical_review","includes_commercial_technical_advice","includes_coordinated_delivery","price_currency","price_tax_mode","stock_status")
    out={k:product.get(k) for k in allowed}; out.update(category=category_id,brand=brand_id,supplier=None,technical_sheet=sheet_id,price=None,price_visible=False,is_featured=False,is_published=False)
    return out

def operation(kind, identity, payload, dependencies=(), media=None):
    core={"type":kind,"identity":identity,"payload":payload,"dependencies":list(dependencies)}
    if media: core["media"]=media
    return {"operation_key":sha256(canonical(core)),**core}

def build_plan(source, media_index=None):
    plan=[]
    for name,slug in CATEGORIES: plan.append(operation("category",slug,{"name":name,"slug":slug,"parent":"$root:maquinarias","product_type":"machinery","description":"","is_active":True,"order":0},["root:maquinarias"]))
    plan.append(operation("brand","lgmg",{"name":"LGMG","slug":"lgmg","logo":None,"description":"","is_active":True}))
    sheets_by_model={}
    for model in MODELS:
        if model in WITHOUT_SHEET: continue
        physical=next((a for a,c in ALIASES.items() if c==model),model)
        filename=f"Ficha-tecnica-LGMG-{physical}.pdf"; sheets_by_model[model]=filename
        plan.append(operation("datasheet",model,{"name":f"Ficha técnica LGMG {physical}"},media={"filename":filename,"content_type":"application/pdf"}))
    products={p["model"]:p for p in source["products"]}; cats={c["id"]:c["slug"] for c in source["categories"]}
    for model in MODELS:
        p=products[model]; cat_slug=cats[nested_id(p["category"])]; payload=product_payload(p,"$category:"+cat_slug,"$brand:lgmg",None if model in WITHOUT_SHEET else "$datasheet:"+model)
        plan.append(operation("product",model,payload,["category:"+cat_slug,"brand:lgmg"]+([] if model in WITHOUT_SHEET else ["datasheet:"+model])))
    for model in MODELS:
        filename=media_index["image_files"][model]["filename"] if media_index else model+".jpg"
        plan.append(operation("image",model,{"product":"$product:"+model,"is_main":True,"order":0,"alt_text":""},["product:"+model],{"filename":filename}))
    byid={p["id"]:p["model"] for p in source["products"]}
    ordered=sorted(source["specifications"],key=lambda s:(byid[nested_id(s["product"])],s["order"],s["name"],s["value"]))
    for i,s in enumerate(ordered):
        model=byid[nested_id(s["product"])]; payload={k:s.get(k) for k in ("name","value","unit","order")}; payload["product"]="$product:"+model
        plan.append(operation("specification",f"{model}:{i:02d}",payload,["product:"+model]))
    if len(plan)!=234 or len({x["operation_key"] for x in plan})!=234: raise ConflictError("plan_contract")
    return plan

def snapshot(client):
    keys=("categories","brands","products","images","specifications","sheets")
    return {k:extract_list(client.get(p),k) for k,p in zip(keys,ApiClient.READ_PATHS)}

def preflight(state, completed=()):
    roots=[c for c in state["categories"] if c.get("name")=="Maquinarias" and c.get("slug")=="maquinarias" and c.get("product_type")=="machinery" and c.get("parent") is None and c.get("is_active") is True]
    if len(roots)!=1: raise ConflictError("maquinarias_root_contract")
    done_types={x["type"] for x in completed}
    if not completed:
        conflicts=[]
        conflicts += [x for x in state["categories"] if x.get("slug") in {s for _,s in CATEGORIES}]
        conflicts += [x for x in state["brands"] if str(x.get("name","")).casefold()=="lgmg" or x.get("slug")=="lgmg"]
        conflicts += state["products"]+state["images"]+state["specifications"]+state["sheets"]
        if conflicts: raise ConflictError("preexisting_catalog_resources")
    return {"root_id":roots[0]["id"],"counts":{k:len(v) for k,v in state.items()},"completed_types":sorted(done_types)}

def atomic_write(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); raw=canonical(sanitize(value))+b"\n"
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        dfd=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def validate_prefix(plan, completed):
    if len(completed)>len(plan): raise ConflictError("completed_prefix_length")
    for i,item in enumerate(completed):
        op=plan[i]
        if item.get("operation_key")!=op["operation_key"] or item.get("index")!=i or item.get("type")!=op["type"] or not isinstance(item.get("production_id"),int) or item["production_id"]<=0: raise ConflictError("completed_prefix_contract")

def reconcile(matches):
    if len(matches)==1 and isinstance(matches[0].get("id"),int) and matches[0]["id"]>0: return matches[0]
    if len(matches)==0: return None
    raise ConflictError("ambiguous_reconciliation")

def verify_remote(state):
    root=preflight({**state,"products":[],"images":[],"specifications":[],"sheets":[],"brands":[],"categories":state["categories"]})
    subs=[c for c in state["categories"] if c.get("slug") in {x[1] for x in CATEGORIES}]
    brands=[b for b in state["brands"] if b.get("slug")=="lgmg"]
    products=[p for p in state["products"] if p.get("model") in MODELS]
    if len(subs)!=7 or len(brands)!=1 or len(products)!=57 or {p["model"] for p in products}!=set(MODELS): raise ConflictError("verify_taxonomy_or_products")
    if any(p.get("is_published") is not False or p.get("is_featured") is not False or p.get("price_visible") is not False or p.get("price") is not None or p.get("stock_status")!="on_request" for p in products): raise ConflictError("verify_product_policy")
    ids={p["id"] for p in products}; images=[x for x in state["images"] if x.get("product") in ids]; specs=[x for x in state["specifications"] if x.get("product") in ids]
    if len(images)!=57 or any(sum(x.get("product")==p["id"] for x in images)!=1 for p in products) or any(x.get("is_main") is not True or type(x.get("order")) is not int or x["order"]!=0 for x in images) or len(specs)!=58 or len(state["sheets"])!=54: raise ConflictError("verify_relations")
    return {"root_id":root["root_id"],"counts":{"categories":7,"brands":1,"products":57,"images":57,"datasheets":54,"specifications":58}}

def parser():
    p=argparse.ArgumentParser(); p.add_argument("--package",required=True); p.add_argument("--api-base-url",required=True); p.add_argument("--checkpoint",required=True); p.add_argument("--output-dir",required=True)
    mode=p.add_mutually_exclusive_group(required=True); mode.add_argument("--dry-run",action="store_true"); mode.add_argument("--apply",action="store_true"); mode.add_argument("--verify",action="store_true")
    p.add_argument("--resume",action="store_true"); p.add_argument("--confirm-apply"); return p

def write_reports(out,audit,plan,cp,conflicts=()):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    follow=[{"code":"corrected_source_sheet_metadata","model":"S1212E","blocking":False}]+[{"code":"normalized_accented_sheet_prefix","model":m,"blocking":False} for m in ("SR0818E-2","SR1218E-2")]
    reports={"summary.json":{"state":cp["state"],"counts":{"planned":234,"categories":7,"brands":1,"datasheets":54,"products":57,"images":57,"specifications":58},"mutating_requests":0 if cp["state"]=="production_transfer_dry_run_ready" else len(cp.get("completed_operations",[])),"without_sheet":list(WITHOUT_SHEET)},"source-audit.json":{"package_sha256":audit["package_sha256"],"json_sha256":audit["json_sha256"],"manifest_fingerprint":audit["manifest_fingerprint"]},"package-manifest.json":audit["entries"],"planned-operations.json":plan,"nonblocking-followups.json":follow,"conflicts.json":list(conflicts),"checkpoint.json":cp}
    for name,value in reports.items(): atomic_write(out/name,value)

def run(argv=None, *, client_factory=ApiClient):
    args=parser().parse_args(argv); validate_api_base(args.api_base_url)
    if args.resume and not args.apply: raise ConflictError("resume_requires_apply")
    if args.apply and args.confirm_apply!=APPLY_CONFIRMATION: raise ConflictError("invalid_apply_confirmation")
    audit=audit_package(args.package); plan=build_plan(audit["source"],audit); token=access_token(); client=client_factory(API_BASE,token)
    cp_path=Path(args.checkpoint)
    if args.dry_run:
        if cp_path.exists(): raise ConflictError("checkpoint_exists")
        state=snapshot(client); pf=preflight(state)
        cp={"tool":TOOL_NAME,"version":TOOL_VERSION,"schema_version":SCHEMA_VERSION,"profile":PROFILE,"api_base":API_BASE,"state":"production_transfer_dry_run_ready","package_sha256":audit["package_sha256"],"json_sha256":audit["json_sha256"],"manifest_fingerprint":audit["manifest_fingerprint"],"plan":plan,"plan_fingerprint":sha256(canonical(plan)),"preflight":pf,"completed_operations":[],"next_operation":0}
        atomic_write(cp_path,cp); write_reports(args.output_dir,audit,plan,cp); print("PRODUCTION_TRANSFER_DRY_RUN_READY"); return cp
    if not cp_path.is_file(): raise ConflictError("checkpoint_required")
    cp=json.loads(cp_path.read_text("utf-8")); validate_prefix(plan,cp.get("completed_operations",[]))
    bindings={x["type"]+":"+x["identity"]:x["production_id"] for x in cp.get("completed_operations",[]) if x["type"] in {"category","brand","datasheet","product"}}
    if args.verify:
        result=verify_remote(snapshot(client)); cp={**cp,"state":"production_transfer_verified","verification":result}; write_reports(args.output_dir,audit,plan,cp); print("PRODUCTION_TRANSFER_VERIFIED"); return cp
    if cp.get("state")=="production_transfer_complete": raise ConflictError("transfer_already_complete")
    allowed={"production_transfer_partial","production_transfer_in_progress"} if args.resume else {"production_transfer_dry_run_ready"}
    if cp.get("state") not in allowed or cp.get("plan_fingerprint")!=sha256(canonical(plan)) or any(cp.get(k)!=v for k,v in (("package_sha256",audit["package_sha256"]),("json_sha256",audit["json_sha256"]),("manifest_fingerprint",audit["manifest_fingerprint"]),("version",TOOL_VERSION),("profile",PROFILE),("api_base",API_BASE))): raise ConflictError("checkpoint_contract")
    preflight(snapshot(client),cp.get("completed_operations",[]) if args.resume else ())
    cp["state"]="production_transfer_in_progress"; atomic_write(cp_path,cp)
    try:
        for i in range(len(cp["completed_operations"]),len(plan)):
            op=plan[i]; payload=json.loads(json.dumps(op["payload"]))
            def resolve(v):
                if isinstance(v,str) and v.startswith("$"): return bindings[v[1:]]
                return v
            payload={k:resolve(v) for k,v in payload.items()}; kind=op["type"]
            if kind=="category": payload["parent"]=cp["preflight"]["root_id"]
            paths={"category":"/api/categories","brand":"/api/brands","product":"/api/products","specification":"/api/product-specs"}
            if kind in paths: response=client.post_json(paths[kind],payload)
            elif kind=="datasheet":
                media=audit["sheet_files"][op["identity"]]; response=client.post_file("/api/technical-sheets",{"name":payload["name"]},media["filename"],media["data"],media["content_type"])
            elif kind=="image":
                media=audit["image_files"][op["identity"]]; response=client.post_file("/api/product-images",{"product":payload["product"],"is_main":"true","order":"0","alt_text":""},media["filename"],media["data"],media["content_type"],"image")
            else: raise ConflictError("unknown_operation_type")
            rid=response.get("id")
            if not isinstance(rid,int) or rid<=0: raise AmbiguousMutation("invalid_create_response")
            bindings[kind+":"+op["identity"]]=rid
            cp["completed_operations"].append({"operation_key":op["operation_key"],"index":i,"type":kind,"identity":op["identity"],"production_id":rid,"dependencies":op["dependencies"],"response":{"id":rid}}); cp["next_operation"]=i+1; atomic_write(cp_path,cp)
    except Exception:
        cp["state"]="production_transfer_partial"; atomic_write(cp_path,cp); write_reports(args.output_dir,audit,plan,cp); raise
    cp["state"]="production_transfer_complete"; atomic_write(cp_path,cp); write_reports(args.output_dir,audit,plan,cp); print("PRODUCTION_TRANSFER_COMPLETE"); return cp

def main():
    try: run()
    except TransferError as exc: print("ERROR: "+str(sanitize(str(exc))),file=os.sys.stderr); return 2
    return 0
if __name__=="__main__": raise SystemExit(main())
