#!/usr/bin/env python3
"""Download only authorised LGMG media named by a validated review package."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import email.utils
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zipfile

TOOL_NAME = "lgmg-jem-review-media-downloader"
TOOL_VERSION = "1.0.0"
SOURCE_TOOL = "lgmg-jem-review-preparer"
HOST = "www.lgmglifts.com"
ORIGIN = "https://www.lgmglifts.com"
ROBOTS_URL = ORIGIN + "/robots.txt"
DEFAULT_USER_AGENT = "JemNexusCatalogResearch/1.0 (+https://jem-nexus.cl/contacto)"
REQUIRED = ("review-products.csv", "review-images.csv", "review-datasheets.csv",
            "review-missing-datasheets.csv", "review-manifest.json", "jem-review-drafts.json")
MAX_MEMBERS = 10_000
MAX_SELECTED_FILE = 64 * 1024 * 1024
MAX_SELECTED_TOTAL = 128 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024
MAX_PDF = 50 * 1024 * 1024
MAX_IMAGE_TOTAL = 1024 * 1024 * 1024
MAX_PDF_TOTAL = 2 * 1024 * 1024 * 1024
MAX_TOTAL = 3 * 1024 * 1024 * 1024
MAX_IMAGE_URLS = 500
MAX_PDF_URLS = 200
MAX_REDIRECTS = 5
MAX_ROBOTS = 512 * 1024
ROMANS = str.maketrans({"Ⅰ":"I", "Ⅱ":"II", "Ⅲ":"III", "Ⅳ":"IV", "Ⅴ":"V", "Ⅵ":"VI",
                        "Ⅶ":"VII", "Ⅷ":"VIII", "Ⅸ":"IX", "Ⅹ":"X", "Ⅺ":"XI", "Ⅻ":"XII"})


class MediaError(ValueError):
    """Invalid local input or a fail-closed security decision."""


class RemoteError(Exception):
    """Controlled remote failure."""

    def __init__(self, message, status="", retryable=False, stage="download"):
        super().__init__(message); self.status = status; self.retryable = retryable; self.stage = stage


def _safe_member(name: str) -> str:
    if not name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise MediaError("ZIP con nombre vacío o caracteres de control")
    value = name.replace("\\", "/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise MediaError("ZIP con ruta absoluta o letra de unidad")
    trailing = value.endswith("/"); parts = value[:-1].split("/") if trailing else value.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise MediaError("ZIP con traversal o segmentos anómalos")
    return "/".join(parts) + ("/" if trailing else "")


def _zip_type(info: zipfile.ZipInfo) -> None:
    if info.flag_bits & 1: raise MediaError("ZIP cifrado no admitido")
    mode = info.external_attr >> 16; kind = stat.S_IFMT(mode)
    if kind and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise MediaError("ZIP con enlace o tipo especial no admitido")


def _read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS: raise MediaError("ZIP excede el límite de miembros")
        normalized = {}; roots = set()
        for info in infos:
            name = _safe_member(info.filename); _zip_type(info)
            if name in normalized: raise MediaError("ZIP contiene miembros duplicados tras normalizar")
            normalized[name] = info
            parts = PurePosixPath(name.rstrip("/")).parts
            for i, part in enumerate(parts):
                if part == "review-package": roots.add("/".join(parts[:i + 1]))
        if len(roots) != 1: raise MediaError("Se exige exactamente un directorio review-package")
        root = next(iter(roots)); chosen = {}
        for leaf in REQUIRED:
            info = normalized.get(f"{root}/{leaf}")
            if info is None or info.is_dir(): raise MediaError(f"Archivo obligatorio ausente: {leaf}")
            if info.file_size > MAX_SELECTED_FILE: raise MediaError(f"Archivo obligatorio demasiado grande: {leaf}")
            chosen[leaf] = info
        if sum(i.file_size for i in chosen.values()) > MAX_SELECTED_TOTAL:
            raise MediaError("Archivos seleccionados exceden el límite combinado")
        return {name: archive.read(info) for name, info in chosen.items()}


def _read_folder(path: Path) -> dict[str, bytes]:
    roots = [path] if path.name == "review-package" else [p for p in path.iterdir()
        if p.name == "review-package" and p.is_dir() and not p.is_symlink()]
    if len(roots) != 1 or roots[0].is_symlink(): raise MediaError("Se exige exactamente un review-package seguro")
    raw, total = {}, 0
    for leaf in REQUIRED:
        item = roots[0] / leaf
        if not item.is_file() or item.is_symlink(): raise MediaError(f"Archivo obligatorio ausente o inseguro: {leaf}")
        size = item.stat().st_size
        if size > MAX_SELECTED_FILE: raise MediaError(f"Archivo obligatorio demasiado grande: {leaf}")
        total += size
        if total > MAX_SELECTED_TOTAL: raise MediaError("Archivos seleccionados exceden el límite combinado")
        raw[leaf] = item.read_bytes()
    return raw


def read_input(path: Path):
    if path.is_symlink(): raise MediaError("La entrada no puede ser un enlace")
    if path.is_file() and path.suffix.casefold() == ".zip": return _read_zip(path), "zip"
    if path.is_dir(): return _read_folder(path), "folder"
    raise MediaError("La entrada debe ser carpeta o ZIP")


def _csv(data, name):
    try: rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except (UnicodeDecodeError, csv.Error) as exc: raise MediaError(f"CSV inválido: {name}") from exc
    return [r for r in rows if any((v or "").strip() for v in r.values())]


def _json(data, name):
    try: return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise MediaError(f"JSON inválido: {name}") from exc


def package_fingerprint(raw):
    digest = hashlib.sha256()
    for name in REQUIRED: digest.update(name.encode()); digest.update(b"\0"); digest.update(raw[name])
    return digest.hexdigest()


def validate_url(url: str, media_type: str) -> str:
    if not isinstance(url, str) or not url or "\\" in url or any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise MediaError("URL de medio inválida")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.username or parsed.password:
        raise MediaError("URL fuera del origen HTTPS autorizado")
    try: port = parsed.port
    except ValueError as exc: raise MediaError("Puerto inválido") from exc
    if port not in (None, 443) or parsed.query or parsed.fragment: raise MediaError("Puerto, query o fragmento no permitido")
    decoded_path = urllib.parse.unquote(parsed.path)
    if "\\" in decoded_path or any(p in ("", ".", "..") for p in decoded_path.split("/")[1:]):
        raise MediaError("Traversal o segmento de URL inválido")
    lower = parsed.path.casefold()
    if media_type == "image":
        if not lower.startswith("/es/upload/images/") or not lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
            raise MediaError("Ruta o extensión de imagen no permitida")
    elif media_type == "datasheet":
        if not lower.startswith("/es/upload/file/") or not lower.endswith(".pdf"):
            raise MediaError("Ruta o extensión de ficha no permitida")
    else: raise MediaError("Tipo de medio inválido")
    return urllib.parse.urlunsplit(parsed)


def _false(value): return str(value).strip().casefold() == "false"


def validate_package(raw):
    manifest = _json(raw["review-manifest.json"], "review-manifest.json")
    drafts = _json(raw["jem-review-drafts.json"], "jem-review-drafts.json")
    if not isinstance(manifest, dict) or manifest.get("tool") != SOURCE_TOOL or manifest.get("version") != "1.0.0":
        raise MediaError("Manifest de revisión no reconocido")
    origin_fp = manifest.get("input_fingerprint_sha256")
    if not isinstance(origin_fp, str) or not re.fullmatch(r"[0-9a-f]{64}", origin_fp): raise MediaError("Fingerprint inválido")
    generated = {x.get("name"): x for x in manifest.get("generated_files", []) if isinstance(x, dict)}
    for name in REQUIRED:
        if name == "review-manifest.json": continue
        item = generated.get(name)
        if not item or item.get("size") != len(raw[name]) or item.get("sha256") != hashlib.sha256(raw[name]).hexdigest():
            raise MediaError(f"Hash o tamaño inconsistente: {name}")
    products = _csv(raw["review-products.csv"], "review-products.csv")
    images = _csv(raw["review-images.csv"], "review-images.csv")
    sheets = _csv(raw["review-datasheets.csv"], "review-datasheets.csv")
    missing = _csv(raw["review-missing-datasheets.csv"], "review-missing-datasheets.csv")
    if not isinstance(drafts, list) or len(drafts) != len(products): raise MediaError("Borradores inconsistentes")
    keys = set()
    for row in products:
        key = row.get("source_key", "")
        if not re.fullmatch(r"lgmg-[0-9a-f]{16}", key) or key in keys: raise MediaError("source_key inválida o duplicada")
        keys.add(key)
        if not _false(row.get("ready_for_import")) or not _false(row.get("published")): raise MediaError("Producto aprobado o publicado")
        if row.get("selection") or row.get("approved_name") or row.get("approved_category"): raise MediaError("Decisión humana inventada")
    draft_keys = set()
    for draft in drafts:
        if not isinstance(draft, dict) or draft.get("source_key") not in keys or draft.get("ready_for_import") is not False:
            raise MediaError("Borrador inválido")
        if (draft.get("product_draft") or {}).get("published") is not False: raise MediaError("Borrador publicado")
        draft_keys.add(draft["source_key"])
    if draft_keys != keys: raise MediaError("Claves de borradores inconsistentes")
    for rows, kind in ((images, "image"), (sheets, "datasheet")):
        for row in rows:
            if row.get("source_key") not in keys: raise MediaError("Medio de producto no confirmado")
            validate_url(row.get("source_url", ""), kind)
            if row.get("local_file") or row.get("download_status") != "not_downloaded" or row.get("rights_status") != "pending_confirmation":
                raise MediaError("Medio ya decidido o con ruta local")
            if row.get("review_decision"): raise MediaError("Decisión de medio inventada")
    if {r.get("source_key") for r in missing} - keys: raise MediaError("Ficha faltante de producto desconocido")
    counts = manifest.get("counts", {})
    expected = (("products_in_review", len(products)), ("image_references", len(images)),
                ("datasheet_references", len(sheets)), ("products_without_datasheets", len(missing)))
    if any(counts.get(k) != n for k, n in expected): raise MediaError("Conteos del manifest inconsistentes")
    image_urls = list(dict.fromkeys(r["source_url"] for r in images)); sheet_urls = list(dict.fromkeys(r["source_url"] for r in sheets))
    if len(image_urls) > MAX_IMAGE_URLS or len(sheet_urls) > MAX_PDF_URLS: raise MediaError("Inventario excede límite de URLs")
    return {"manifest": manifest, "products": products, "images": images, "datasheets": sheets,
            "missing": missing, "drafts": drafts, "fingerprint": package_fingerprint(raw)}


class StrictRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self): super().__init__(); self.count = 0
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > MAX_REDIRECTS: raise MediaError("Demasiados redirects")
        kind = "datasheet" if urllib.parse.urlsplit(newurl).path.casefold().endswith(".pdf") else "image"
        validate_url(newurl, kind)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, user_agent, timeout): self.user_agent=user_agent; self.timeout=timeout
    def open(self, url):
        handler = StrictRedirect(); opener = urllib.request.build_opener(handler)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        return opener.open(request, timeout=self.timeout)


def _header(response, name):
    headers = getattr(response, "headers", {})
    return headers.get(name, "") if hasattr(headers, "get") else ""


def validate_robots(fetcher, user_agent):
    try:
        with fetcher.open(ROBOTS_URL) as response:
            length = _header(response, "Content-Length")
            if length and (not length.isdigit() or int(length) > MAX_ROBOTS): raise MediaError("robots.txt demasiado grande")
            data = response.read(MAX_ROBOTS + 1)
            if len(data) > MAX_ROBOTS: raise MediaError("robots.txt demasiado grande")
    except Exception as exc:
        if isinstance(exc, MediaError): raise
        raise MediaError("No fue posible consultar robots.txt") from exc
    try: text = data.decode("utf-8"); parser = urllib.robotparser.RobotFileParser(); parser.set_url(ROBOTS_URL); parser.parse(text.splitlines())
    except (UnicodeDecodeError, ValueError) as exc: raise MediaError("robots.txt inválido") from exc
    if not text.strip() or not any(line.partition(":")[0].strip().casefold() == "user-agent" for line in text.splitlines()):
        raise MediaError("robots.txt no interpretable")
    for path in ("/es/upload/images/example.jpg", "/es/upload/file/example.pdf"):
        if not parser.can_fetch(user_agent, ORIGIN + path): raise MediaError("robots.txt prohíbe medios")
    return True


def detect_content(head: bytes, content_type: str, url: str, kind: str):
    mime = content_type.partition(";")[0].strip().casefold()
    if head.startswith(b"\xff\xd8\xff"): detected, ext = "image/jpeg", ".jpg"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"): detected, ext = "image/png", ".png"
    elif len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP": detected, ext = "image/webp", ".webp"
    elif head.startswith(b"%PDF-"): detected, ext = "application/pdf", ".pdf"
    else: raise RemoteError("Firma magic inválida")
    allowed = {"image": {"image/jpeg": (".jpg", ".jpeg"), "image/png": (".png",), "image/webp": (".webp",)},
               "datasheet": {"application/pdf": (".pdf",)}}[kind]
    url_ext = Path(urllib.parse.urlsplit(url).path).suffix.casefold()
    if detected not in allowed or url_ext not in allowed[detected]: raise RemoteError("Firma incompatible con extensión")
    if mime not in (detected, "application/octet-stream"): raise RemoteError("Content-Type incompatible")
    return detected, ext


def slug(value, fallback):
    value = unicodedata.normalize("NFKD", str(value).translate(ROMANS)).encode("ascii", "ignore").decode().casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-"); value = re.sub("-+", "-", value)[:64].strip("-")
    if not value:
        value = re.sub(r"[^a-z0-9]+", "-", fallback.casefold()).strip("-")[:64]
    if not value: raise MediaError("Modelo y source_key no producen nombre seguro")
    return value


def local_name(row, kind, url, extension):
    model = slug(row.get("metric_model", ""), row.get("source_key", "")); short = hashlib.sha256(url.encode()).hexdigest()[:10]
    if kind == "image": return f"media/images/lgmg-{model}-{int(row['image_order']):02d}-{short}{extension}"
    return f"media/datasheets/lgmg-{model}-ficha-tecnica-{short}{extension}"


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_name(path.name + ".part")
    try:
        with temporary.open("wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def atomic_json(path, value): atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _sanitize(exc):
    text = str(exc).splitlines()[0]; text = re.sub(r"https?://\S+", "URL", text)
    return re.sub(r"[^\w .,:;()áéíóúñÁÉÍÓÚÑ-]", "?", text)[:200] or "Fallo remoto"


def stream_download(fetcher, url, kind, destination, total_so_far):
    maximum = MAX_IMAGE if kind == "image" else MAX_PDF; part = destination.with_name(destination.name + ".part")
    try:
        with fetcher.open(url) as response:
            length = _header(response, "Content-Length")
            if length:
                if not length.isdigit(): raise RemoteError("Content-Length inválido")
                if int(length) > maximum: raise RemoteError("Content-Length excede límite")
            digest=hashlib.sha256(); size=0; head=b""
            with part.open("wb") as output:
                while True:
                    chunk=response.read(min(64 * 1024, maximum + 1 - size))
                    if not chunk: break
                    size += len(chunk)
                    if size > maximum: raise RemoteError("Medio excede límite individual")
                    if len(head) < 16: head=(head+chunk)[:16]
                    digest.update(chunk); output.write(chunk)
                output.flush(); os.fsync(output.fileno())
            if not size: raise RemoteError("Respuesta vacía")
            mime, ext = detect_content(head, _header(response, "Content-Type"), url, kind)
            limit = MAX_IMAGE_TOTAL if kind == "image" else MAX_PDF_TOTAL
            if total_so_far + size > limit: raise RemoteError("Total por tipo excedido")
            os.replace(part, destination)
            return {"sha256":digest.hexdigest(), "size_bytes":size, "mime_type":mime, "extension":ext}
    finally:
        if part.exists(): part.unlink()


def fetch_with_retries(fetcher, url, kind, destination, total, sleep=time.sleep):
    attempts=0
    while attempts < 3:
        attempts += 1
        try: return stream_download(fetcher, url, kind, destination, total), attempts
        except urllib.error.HTTPError as exc:
            retryable=exc.code in (429,500,502,503,504)
            if not retryable or attempts == 3: raise RemoteError(f"HTTP {exc.code}", str(exc.code), retryable) from exc
            retry = exc.headers.get("Retry-After", "") if exc.headers else ""
            sleep(min(30, int(retry) if retry.isdigit() else attempts))
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempts == 3: raise RemoteError("Error de conexión o timeout", retryable=True) from exc
            sleep(min(30, attempts))
        except RemoteError: raise


def _safe_output(input_path, output, resume):
    resolved_in=input_path.resolve(); resolved=output.resolve(strict=False); home=Path.home().resolve()
    if resolved in (Path(resolved.anchor), home) or len(resolved.parts)<3: raise MediaError("Salida demasiado amplia")
    if resolved == resolved_in or (input_path.is_dir() and resolved_in in resolved.parents): raise MediaError("Salida coincide o está dentro de entrada")
    parent=resolved
    while not parent.exists() and parent != parent.parent: parent=parent.parent
    if parent.is_symlink() or (output.exists() and output.is_symlink()): raise MediaError("Salida mediante symlink")
    if output.exists() and (not output.is_dir() or (not resume and any(output.iterdir()))): raise MediaError("Salida no está vacía")


def _new_state(validated):
    items=[]
    for kind, rows in (("image",validated["images"]),("datasheet",validated["datasheets"])):
        for url in dict.fromkeys(r["source_url"] for r in rows):
            items.append({"url":url,"media_type":kind,"status":"pending","attempts":0,"local_file":"",
                "size_bytes":0,"sha256":"","mime_type":"","error":"","completed":False})
    return {"tool":TOOL_NAME,"version":TOOL_VERSION,"input_fingerprint_sha256":validated["fingerprint"],
        "operator_confirmed_media_rights":True,"confirmed_at_utc":datetime.now(timezone.utc).isoformat(),"items":items}


def load_state(output, validated, resume):
    path=output/"media-download-state.json"
    if not resume: return _new_state(validated)
    if not path.is_file() or path.is_symlink(): raise MediaError("Estado de reanudación ausente")
    state=_json(path.read_bytes(), path.name)
    if state.get("tool")!=TOOL_NAME or state.get("version")!=TOOL_VERSION or state.get("input_fingerprint_sha256")!=validated["fingerprint"]:
        raise MediaError("Estado incompatible o fingerprint distinto")
    expected={(x["media_type"],x["url"]) for x in _new_state(validated)["items"]}
    if {(x.get("media_type"),x.get("url")) for x in state.get("items",[])} != expected: raise MediaError("Inventario de reanudación distinto")
    for item in state["items"]:
        if item.get("completed"):
            rel=item.get("local_file","")
            if not rel or PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts: raise MediaError("Ruta local insegura en estado")
            path=output.joinpath(*PurePosixPath(rel).parts)
            if not path.is_file() or path.stat().st_size != item.get("size_bytes") or hashlib.sha256(path.read_bytes()).hexdigest()!=item.get("sha256"):
                raise MediaError("Archivo completado manipulado")
    state["operator_confirmed_media_rights"]=True; state["confirmed_at_utc"]=datetime.now(timezone.utc).isoformat()
    return state


def _excel(value):
    text="" if value is None else (str(value).lower() if isinstance(value,bool) else str(value))
    return "'"+text if text.lstrip().startswith(("=","+","-","@")) else text


def write_csv(path, fields, rows):
    out=io.StringIO(newline=""); writer=csv.DictWriter(out,fields,extrasaction="ignore",lineterminator="\r\n")
    writer.writeheader(); writer.writerows({k:_excel(row.get(k)) for k in fields} for row in rows)
    atomic_write(path, b"\xef\xbb\xbf"+out.getvalue().encode("utf-8"))


def build_reports(output, validated, state, failures, input_type, args, robots_allowed):
    results={x["url"]:x for x in state["items"]}; url_counts={}
    for kind, rows in (("image",validated["images"]),("datasheet",validated["datasheets"])):
        for row in rows: url_counts[(kind,row["source_url"])]=url_counts.get((kind,row["source_url"]),0)+1
    hash_urls={}; hash_assocs={}
    for item in state["items"]:
        if item.get("completed"):
            key=(item["media_type"],item["sha256"]); hash_urls.setdefault(key,set()).add(item["url"])
            hash_assocs[key]=hash_assocs.get(key,0)+url_counts[(item["media_type"],item["url"])]
    association_outputs=[]
    for kind, rows in (("image",validated["images"]),("datasheet",validated["datasheets"])):
        built=[]; seen=set()
        for row in rows:
            item=results[row["source_url"]]; complete=item.get("completed",False); key=(kind,item.get("sha256",""))
            built.append({**row,"local_file":item.get("local_file","") if complete else "","sha256":item.get("sha256","") if complete else "",
                "size_bytes":item.get("size_bytes",0) if complete else "","mime_type":item.get("mime_type","") if complete else "",
                "rights_status":"operator_confirmed_for_local_download","download_status":"downloaded" if complete else "failed",
                "deduplicated_by_url":str(row["source_url"] in seen).lower(),
                "deduplicated_by_content":str(complete and len(hash_urls.get(key,set()))>1).lower(),"review_decision":""})
            seen.add(row["source_url"])
        association_outputs.append(built)
    image_fields="source_key metric_model image_order source_url local_file sha256 size_bytes mime_type primary_candidate rights_status download_status deduplicated_by_url deduplicated_by_content review_decision".split()
    sheet_fields="source_key metric_model datasheet_order source_url local_file sha256 size_bytes mime_type rights_status download_status deduplicated_by_url deduplicated_by_content review_decision".split()
    write_csv(output/"downloaded-images.csv",image_fields,association_outputs[0]); write_csv(output/"downloaded-datasheets.csv",sheet_fields,association_outputs[1])
    file_rows=[]
    for key, urls in sorted(hash_urls.items()):
        kind,digest=key; item=next(x for x in state["items"] if x.get("sha256")==digest and x["media_type"]==kind)
        associations=validated["images"] if kind=="image" else validated["datasheets"]
        first=next(r for r in associations if r["source_url"] in urls)
        file_rows.append({"media_type":kind,"local_file":item["local_file"],"sha256":digest,"size_bytes":item["size_bytes"],
            "mime_type":item["mime_type"],"source_url_count":len(urls),"association_count":hash_assocs[key],
            "first_source_key":first["source_key"],"first_metric_model":first["metric_model"]})
    write_csv(output/"media-files.csv","media_type local_file sha256 size_bytes mime_type source_url_count association_count first_source_key first_metric_model".split(),file_rows)
    write_csv(output/"media-failures.csv","media_type source_url stage http_status attempts message".split(),failures)
    unique_images=len({r["source_url"] for r in validated["images"]}); unique_sheets=len({r["source_url"] for r in validated["datasheets"]})
    complete=not failures and all(x.get("completed") for x in state["items"])
    summary={"products":len(validated["products"]),"image_associations":len(validated["images"]),"unique_image_urls":unique_images,
        "physical_image_files":sum(r["media_type"]=="image" for r in file_rows),"datasheet_associations":len(validated["datasheets"]),
        "unique_datasheet_urls":unique_sheets,"physical_datasheet_files":sum(r["media_type"]=="datasheet" for r in file_rows),
        "url_duplicates":len(validated["images"])+len(validated["datasheets"])-unique_images-unique_sheets,
        "content_duplicates":sum(max(0,len(v)-1) for v in hash_urls.values()),
        "image_bytes":sum(r["size_bytes"] for r in file_rows if r["media_type"]=="image"),
        "datasheet_bytes":sum(r["size_bytes"] for r in file_rows if r["media_type"]=="datasheet"),"failures":len(failures),
        "products_without_datasheet":len(validated["missing"]),"missing_datasheet_models":[r.get("metric_model","") for r in validated["missing"]],
        "operator_confirmed_media_rights":True,"package_complete":complete,"jem_nexus_calls":0,"products_imported":0,"content_published":False}
    atomic_json(output/"media-summary.json",summary)
    atomic_write(output/"media-summary.txt",("\n".join(f"{k}: {str(v).lower() if isinstance(v,bool) else v}" for k,v in summary.items())+"\n").encode())
    readme=("MEDIOS LGMG PARA REVISIÓN LOCAL\n\nOrigen: URLs oficiales incluidas en el paquete de revisión validado. "
        "El operador confirmó autorización para la descarga local; esta constancia no sustituye la documentación comercial o contractual.\n"
        "Los medios no se subieron. Ningún producto fue importado, ninguna imagen fue aprobada como principal y ninguna ficha fue asociada. "
        "Los modelos sin PDF permanecen pendientes y los nueve productos inciertos no forman parte del paquete.\n"
        "downloaded-images.csv y downloaded-datasheets.csv conservan asociaciones; media-files.csv inventaría archivos físicos; media-failures.csv registra fallos.\n"
        "Para reanudar, repita el comando con --resume y --confirm-media-rights. Revise visualmente todos los archivos antes de importar. "
        "Imágenes y PDF mantienen exactamente sus bytes originales.\n")
    atomic_write(output/"README-media.txt",readme.encode("utf-8"))
    report_names=["downloaded-images.csv","downloaded-datasheets.csv","media-files.csv","media-failures.csv","media-summary.json","media-summary.txt","media-download-state.json","README-media.txt"]
    files=[]
    for name in report_names:
        data=(output/name).read_bytes(); files.append({"name":name,"size":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    for row in file_rows: files.append({"name":row["local_file"],"size":row["size_bytes"],"sha256":row["sha256"]})
    manifest={"tool":TOOL_NAME,"version":TOOL_VERSION,"created_at_utc":datetime.now(timezone.utc).isoformat(),
        "input_fingerprint_sha256":validated["fingerprint"],"input_type":input_type,"authorized_host":HOST,
        "operator_confirmed_media_rights":True,"robots_allowed":robots_allowed,"user_agent":args.user_agent,
        "delay_seconds":args.delay_seconds,"timeout_seconds":args.timeout_seconds,
        "limits":{"image_bytes":MAX_IMAGE,"pdf_bytes":MAX_PDF,"image_total_bytes":MAX_IMAGE_TOTAL,"pdf_total_bytes":MAX_PDF_TOTAL,
            "combined_total_bytes":MAX_TOTAL,"image_urls":MAX_IMAGE_URLS,"pdf_urls":MAX_PDF_URLS,"redirects":MAX_REDIRECTS},
        "counts":summary,"files":files,"network_used":True,"jem_nexus_called":False,"products_imported":0,
        "content_published":False,"all_products_ready_for_import":False,"package_complete":complete}
    atomic_json(output/"media-manifest.json",manifest); return complete


def run(args, fetcher=None, sleep=time.sleep):
    if not args.confirm_media_rights: raise MediaError("Se requiere --confirm-media-rights")
    input_path=Path(args.input); output=Path(args.output_dir); _safe_output(input_path,output,args.resume)
    raw,input_type=read_input(input_path); validated=validate_package(raw)
    output.mkdir(parents=True,exist_ok=True); (output/"media/images").mkdir(parents=True,exist_ok=True); (output/"media/datasheets").mkdir(parents=True,exist_ok=True)
    state=load_state(output,validated,args.resume); atomic_json(output/"media-download-state.json",state)
    fetcher=fetcher or Fetcher(args.user_agent,args.timeout_seconds); robots=validate_robots(fetcher,args.user_agent)
    failures=[]; totals={"image":0,"datasheet":0}; content={}
    for item in state["items"]:
        if item.get("completed"):
            totals[item["media_type"]]+=item["size_bytes"]; content[(item["media_type"],item["sha256"])]=item["local_file"]; continue
        rows=validated["images"] if item["media_type"]=="image" else validated["datasheets"]
        row=next(r for r in rows if r["source_url"]==item["url"]); provisional=local_name(row,item["media_type"],item["url"],Path(urllib.parse.urlsplit(item["url"]).path).suffix.casefold())
        destination=output.joinpath(*PurePosixPath(provisional).parts)
        try:
            result,attempts=fetch_with_retries(fetcher,item["url"],item["media_type"],destination,totals[item["media_type"]],sleep)
            final_rel=local_name(row,item["media_type"],item["url"],result.pop("extension")); final=output.joinpath(*PurePosixPath(final_rel).parts)
            if destination != final: os.replace(destination,final)
            duplicate=content.get((item["media_type"],result["sha256"]))
            if duplicate:
                final.unlink(); final_rel=duplicate
            else: content[(item["media_type"],result["sha256"])]=final_rel
            totals[item["media_type"]]+=result["size_bytes"]
            if totals["image"]+totals["datasheet"]>MAX_TOTAL: raise RemoteError("Total combinado excedido")
            item.update(result,attempts=attempts,status="completed",completed=True,local_file=final_rel,error="")
        except (RemoteError,MediaError,OSError) as exc:
            item.update(status="failed",completed=False,attempts=getattr(exc,"attempts",item.get("attempts",0)),error=_sanitize(exc))
            failures.append({"media_type":item["media_type"],"source_url":item["url"],"stage":getattr(exc,"stage","download"),
                "http_status":getattr(exc,"status",""),"attempts":item["attempts"],"message":item["error"]})
        atomic_json(output/"media-download-state.json",state); sleep(args.delay_seconds)
    return 0 if build_reports(output,validated,state,failures,input_type,args,robots) else 3


def build_parser():
    parser=argparse.ArgumentParser(description="Descarga autorizada de medios LGMG para revisión local")
    parser.add_argument("--input",required=True); parser.add_argument("--output-dir",required=True)
    parser.add_argument("--confirm-media-rights",action="store_true"); parser.add_argument("--delay-seconds",type=float,default=1.0)
    parser.add_argument("--timeout-seconds",type=float,default=30.0); parser.add_argument("--resume",action="store_true")
    parser.add_argument("--user-agent",default=DEFAULT_USER_AGENT); return parser


def main(argv=None):
    try:
        args=build_parser().parse_args(argv)
        if args.delay_seconds<1.0 or not (0<args.timeout_seconds<=300) or "\n" in args.user_agent or "\r" in args.user_agent or not args.user_agent.strip():
            raise MediaError("Delay, timeout o user-agent inválido")
        return run(args)
    except (MediaError,OSError,zipfile.BadZipFile) as exc:
        print("Error: "+_sanitize(exc),file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
