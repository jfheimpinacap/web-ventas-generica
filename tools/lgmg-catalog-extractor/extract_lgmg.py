#!/usr/bin/env python3
"""Extract a small, reviewable LGMG catalogue sample using only the stdlib."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.robotparser
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

TOOL_VERSION = "1.1.1"
ALLOWED_HOST = "www.lgmglifts.com"
DEFAULT_UA = "JemNexusCatalogResearch/1.0 (+https://jem-nexus.cl/contacto)"
MAX_PRODUCTS = 25
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_ASSET_BYTES = 15 * 1024 * 1024
DETAIL_RE = re.compile(r"^/es/product/pro-detail-[0-9A-Za-z_-]+\.htm$")
LIST_RE = re.compile(r"^/es/product/pro-list-[0-9A-Za-z_-]+\.htm$")
MODEL_TOKEN = r"[A-Z]{1,5}[0-9][A-Z0-9\-ⅠⅡⅢⅣ]*"
MODEL_RE = re.compile(rf"(?<![A-Z0-9])({MODEL_TOKEN})(?![A-Z0-9])")
PAIR_RE = re.compile(rf"(?<![A-Z0-9])({MODEL_TOKEN})\s*\(\s*({MODEL_TOKEN})\s*\)")
INVALID_MODEL_WORDS = ("ELEVADOR", "ELEVADORES", "PRODUCTOS", "LGMG")

SPEC_KEYS = {
    "altura máxima de trabajo": "maximum_working_height", "maximum working height": "maximum_working_height",
    "altura de plataforma": "platform_height", "platform height": "platform_height",
    "capacidad de plataforma": "platform_capacity", "platform capacity": "platform_capacity",
    "ancho total": "overall_width", "overall width": "overall_width",
    "longitud total": "overall_length", "overall length": "overall_length",
    "peso de la máquina": "machine_weight", "machine weight": "machine_weight",
    "fuente de potencia": "power_source", "power source": "power_source",
    "dimensiones de plataforma": "platform_dimensions", "platform dimensions": "platform_dimensions",
    "pendiente superable": "gradeability", "gradeability": "gradeability",
    "radio de giro": "turning_radius", "turning radius": "turning_radius",
    "ocupantes": "occupants", "occupants": "occupants",
}


def clean_text(value: str) -> str:
    return " ".join(html.unescape(value).replace("\ufffd", "�").split())


def strip_accents(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn")


def canonical_url(url: str, *, page: bool = True) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() != "https" or (parts.hostname or "").lower() != ALLOWED_HOST or parts.port not in (None, 443):
        raise ValueError("URL rechazada: se exige HTTPS y el host oficial exacto")
    path = re.sub(r"/{2,}", "/", parts.path)
    if page and not (DETAIL_RE.fullmatch(path) or LIST_RE.fullmatch(path)):
        raise ValueError("URL rechazada: no es una página permitida bajo /es/product/")
    return urlunsplit(("https", ALLOWED_HOST, path, "", ""))


def safe_filename(value: str, limit: int = 80) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"[-_.]{2,}", "-", value).strip("-._")
    return (value[:limit].rstrip("-._") or "asset")


def validate_output_dir(raw: str, repo_root: Path | None = None) -> Path:
    path = Path(raw).expanduser().resolve(strict=False)
    forbidden = {Path("/").resolve(), Path.home().resolve(), Path(tempfile.gettempdir()).resolve()}
    if repo_root:
        forbidden.add(repo_root.resolve())
    if path in forbidden or len(path.parts) < 3:
        raise ValueError("Directorio de salida demasiado amplio o peligroso")
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink() or (path.exists() and path.is_symlink()):
        raise ValueError("El directorio de salida no puede ser un enlace simbólico")
    return path


class Node:
    def __init__(self, tag="document", attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or ()), parent
        self.children, self.contents = [], []

    @property
    def classes(self): return set(self.attrs.get("class", "").split())
    @property
    def text(self):
        return clean_text(self._text_content())

    def _text_content(self):
        return "".join(item._text_content() if isinstance(item, Node) else item for item in self.contents)

    def descendants(self, tag=None):
        for child in self.children:
            if tag is None or child.tag == tag: yield child
            yield from child.descendants(tag)

    def has_ancestor(self, classes):
        node = self.parent
        while node:
            if classes <= node.classes: return True
            node = node.parent
        return False


class CatalogueParser(HTMLParser):
    """Context-aware, minimal DOM parser built solely on HTMLParser."""
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.root = Node(); self.stack = [self.root]
        self.links, self.images, self.datasheets, self.rows = [], [], [], []
        self.source_page_title = self.source_product_title = self.canonical = ""
        self.breadcrumb_span = self.source_category = ""

    def handle_starttag(self, tag, attrs):
        attrs = [(key.lower(), value or "") for key, value in attrs]
        node = Node(tag.lower(), attrs, self.stack[-1])
        self.stack[-1].children.append(node); self.stack[-1].contents.append(node)
        if tag.lower() not in ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag.lower(): self.stack = self.stack[:index]; break

    def handle_data(self, data):
        self.stack[-1].contents.append(data)

    def feed(self, data):
        super().feed(data); self._extract()

    def _extract(self):
        nodes = list(self.root.descendants())
        title = next((n for n in nodes if n.tag == "title"), None)
        self.source_page_title = title.text if title else ""
        canonical = next((n for n in nodes if n.tag == "link" and "canonical" in n.attrs.get("rel", "").lower()), None)
        if canonical: self.canonical = urljoin(self.base_url, canonical.attrs.get("href", ""))
        crumbs = next((n for n in nodes if "crumbs" in n.classes), None)
        if crumbs:
            spans = list(crumbs.descendants("span")); self.breadcrumb_span = spans[-1].text if spans else ""
            categories = [a.text for a in crumbs.descendants("a") if LIST_RE.fullmatch(urlsplit(urljoin(self.base_url, a.attrs.get("href", ""))).path) and a.text.casefold() != "productos"]
            self.source_category = categories[-1] if categories else ""
        candidates = [n for n in nodes if "tit" in n.classes and n.has_ancestor({"infor"}) and n.has_ancestor({"pro_detail01"})]
        self.source_product_title = candidates[0].text if candidates else ""
        for table in (n for n in nodes if n.tag == "table" and "datalist" in n.classes and n.has_ancestor({"pro_detail"})):
            for tr in table.descendants("tr"):
                cells = [cell.text for cell in tr.children if cell.tag in ("th", "td")]
                if any(cells): self.rows.append(cells)
        listing = next((n for n in nodes if n.tag == "section" and {"channel_content", "pro_list"} <= n.classes), None)
        if listing:
            for anchor in listing.descendants("a"):
                target = urljoin(self.base_url, anchor.attrs.get("href", ""))
                if DETAIL_RE.fullmatch(urlsplit(target).path): self.links.append(target)
        allowed_ext = {"jpg", "jpeg", "png", "gif", "webp"}
        for img in (n for n in nodes if n.tag == "img"):
            gallery = (img.has_ancestor({"ul_box"}) and img.has_ancestor({"right_r"}) and img.has_ancestor({"pro_detail01"})) or (img.has_ancestor({"right_b", "imgZoom"}) and img.has_ancestor({"pro_detail02"}))
            if not gallery: continue
            src = next((img.attrs.get(k) for k in ("bigsrc", "data-original", "data-src", "src") if img.attrs.get(k)), "")
            try: target = canonical_url(urljoin(self.base_url, src), page=False)
            except ValueError: continue
            ext = Path(urlsplit(target).path).suffix.lower().lstrip(".")
            if ext in allowed_ext: self.images.append({"url": target, "order": len(self.images) + 1, "alt_original": clean_text(img.attrs.get("alt", "")), "extension": ext})
        for box in (n for n in nodes if "new_box" in n.classes):
            heading = next((n.text for n in box.children if "tit" in n.classes), "")
            normalized = re.sub(r"[^a-z ]", "", strip_accents(heading).casefold()).strip()
            if normalized != "ficha tecnica": continue
            for anchor in box.descendants("a"):
                target = urljoin(self.base_url, anchor.attrs.get("href", "")); path = urlsplit(target).path
                if not path.lower().endswith(".pdf"): continue
                try: target = canonical_url(target, page=False)
                except ValueError: continue
                language = next((span.text for span in anchor.descendants("span") if span.text), None)
                self.datasheets.append({"url": target, "name": Path(path).name, "format": "pdf", "language": language,
                                        "provenance": "Ficha técnica", "needs_review": not bool(language)})


def dedupe(items, key=lambda item: item):
    seen = set(); result = []
    for item in items:
        marker = key(item)
        if marker not in seen: seen.add(marker); result.append(item)
    return result


def _models(value: str):
    pair = PAIR_RE.search(value.upper())
    values = pair.groups() if pair else ((MODEL_RE.search(value.upper()).group(1), None) if MODEL_RE.search(value.upper()) else (None, None))
    if any(word in (token or "") for token in values for word in INVALID_MODEL_WORDS): return None, None
    return values


def _model_row_evidence(row: list[str]):
    if len(row) < 2:
        return None
    label = clean_text(strip_accents(row[0]).casefold()).rstrip(":").strip()
    labels = {"modelo", "modelos", "model", "models", "modele", "modelo metrico (imperial)"}
    if label not in labels:
        return None
    values = [value for value in row[1:] if clean_text(value)]
    if not values:
        return None
    metric, imperial = _models(values[0])
    if imperial or len(values) == 1:
        return metric, imperial
    second_metric, second_imperial = _models(values[1])
    return metric, second_metric or second_imperial


def _model_evidence_conflicts(reference, candidate):
    return any(left and right and left != right for left, right in zip(reference, candidate))


def normalize_models(product_title: str, rows: list[list[str]], breadcrumb: str = "") -> dict:
    parsed = [("source_product_title", _models(product_title))]
    table_pair = next((pair for row in rows if (pair := _model_row_evidence(row)) is not None), None)
    if table_pair is not None: parsed.append(("technical_table", table_pair))
    if breadcrumb: parsed.append(("breadcrumb_span", _models(breadcrumb)))
    chosen = next(((name, pair) for name, pair in parsed if pair[0]), (None, (None, None)))
    conflicts = [(name, pair) for name, pair in parsed if pair[0] and _model_evidence_conflicts(chosen[1], pair)]
    warnings = []
    if conflicts: warnings.append("Conflicto entre fuentes estructuradas para el modelo")
    if not chosen[1][0]: warnings.append("No se pudo identificar un modelo válido sin usar el ID de la URL")
    weak = chosen[0] == "breadcrumb_span"
    if weak: warnings.append("Se utilizó el breadcrumb como fallback débil para el modelo")
    metric, imperial = chosen[1]
    return {"manufacturer": "LGMG", "metric_model": metric, "imperial_model": imperial,
            "model_aliases": [imperial] if imperial else [], "model_pair_source": f"{metric}({imperial})" if imperial else metric,
            "model_evidence": [{"source": name, "metric_model": pair[0], "imperial_model": pair[1]} for name, pair in parsed],
            "needs_review": not metric or bool(conflicts) or weak, "warnings": warnings}


def parse_specs(rows: list[list[str]]) -> list[dict]:
    result = []
    for row in rows:
        if len(row) < 2: continue
        name, values = row[0], [v for v in row[1:] if v]
        if not name or not values: continue
        key = SPEC_KEYS.get(name.casefold().rstrip(":"))
        result.append({"name_original": name, "value_metric": values[0],
                       "value_imperial": values[1] if len(values) > 1 else None,
                       "normalized_key": key, "evidence": list(row), "needs_review": len(values) > 2})
    return result


def classify_electric(category: str | None, specs: list[dict], title: str = "") -> tuple[bool | None, list[str]]:
    evidence = []
    for spec in specs:
        combined = f"{spec['name_original']}: {spec['value_metric']}"
        if spec["normalized_key"] == "power_source" or re.search(r"\b(bater[ií]a|battery|electric(?:al)?|eléctric[oa]|\d+\s*v)\b", combined, re.I):
            evidence.append(combined)
    if re.search(r"\b(electric(?:al)?|eléctric[oa])\b", " ".join((category or "", title)), re.I):
        evidence.insert(0, f"Categoría/título: {clean_text(' '.join((category or '', title)))}")
    return (True, dedupe(evidence)) if evidence else (None, [])


NAME_TEMPLATES = {
    "elevadores de tijera": "Elevador de tijera {electric}LGMG {model}",
    "elevador electrico rt de tijera": "Elevador de tijera {electric}para terreno irregular LGMG {model}",
    "elevadores de brazo articulado": "Elevador de brazo articulado {electric}LGMG {model}",
    "elevadores de brazo telescopico": "Elevador de brazo telescópico {electric}LGMG {model}",
    "elevador mastil vertical": "Elevador de mástil vertical {electric}LGMG {model}",
    "elevador de tijera sobre orugas": "Elevador de tijera sobre orugas {electric}LGMG {model}",
    "manipuladores telescopicos": "Manipulador telescópico LGMG {model}",
}


def parse_product(document: str, source_url: str) -> dict:
    parser = CatalogueParser(source_url); parser.feed(document)
    models = normalize_models(parser.source_product_title, parser.rows, parser.breadcrumb_span)
    specs = parse_specs(parser.rows)
    category = parser.source_category or None
    electric, evidence = classify_electric(category, specs, parser.source_product_title)
    warnings = list(models.pop("warnings"))
    missing_fields = [key for key, value in (("metric_model", models["metric_model"]), ("source_category", category)) if not value]
    if not category: warnings.append("Falta la categoría fuente estructurada en crumbs")
    if electric is None: warnings.append("Evidencia eléctrica insuficiente; clasificación pendiente")
    model = models["metric_model"] or models["imperial_model"] or "modelo por revisar"
    category_key = strip_accents(category or "").casefold()
    template = NAME_TEMPLATES.get(category_key)
    if template: name = template.format(electric="eléctrico " if electric else "", model=model)
    else: name = f"Equipo LGMG {model}"; warnings.append("Categoría sin mapeo conocido para nombre sugerido")
    images = dedupe(parser.images, lambda x: x["url"])
    for order, image in enumerate(images, 1): image["order"] = order; image["alt_suggested"] = name
    datasheets = dedupe(parser.datasheets, lambda x: x["url"])
    needs_review = models["needs_review"] or electric is None or not category or not template or any(a.get("needs_review", False) for a in images + datasheets)
    return {"source_url": source_url, "canonical_url": parser.canonical or source_url,
            "source_page_title": parser.source_page_title, "source_product_title": parser.source_product_title,
            "source_category": category, **models, "specifications": specs, "images": images,
            "datasheets": datasheets, "is_electric": electric,
            "electric_evidence": evidence, "warnings": warnings, "translation_issues": [],
            "missing_fields": missing_fields, "needs_review": needs_review, "display_name_suggestion": name,
            "jem_nexus_draft": {"name": name, "brand": "LGMG", "model": model,
                "product_type": "machinery", "condition": "new", "stock_status": "on_request",
                "show_price": False, "published": False, "featured": False, "price": None}}


class SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self): super().__init__(); self.count = 0
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 3: raise HTTPError(newurl, code, "Demasiadas redirecciones", headers, fp)
        canonical_url(newurl, page=False)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, cache_dir: Path, delay: float, timeout: float, user_agent: str, refresh=False):
        self.cache_dir, self.delay, self.timeout = cache_dir, delay, timeout
        self.user_agent, self.refresh, self.last_request = user_agent, refresh, 0.0

    def fetch(self, url: str, *, page=True, max_bytes=MAX_HTML_BYTES, allow_404=False) -> bytes:
        url = canonical_url(url, page=page)
        cache = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".bin")
        if cache.exists() and not self.refresh: return cache.read_bytes()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        error = None
        for attempt in range(3):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            handler = SafeRedirectHandler(); opener = build_opener(handler)
            try:
                req = Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,*/*;q=0.1"}, method="GET")
                self.last_request = time.monotonic()
                with opener.open(req, timeout=self.timeout) as response:
                    final = canonical_url(response.url, page=page)
                    content = response.read(max_bytes + 1)
                    if len(content) > max_bytes: raise ValueError("Documento excede el tamaño máximo")
                    atomic_write(cache, content)
                    return content
            except HTTPError as exc:
                if exc.code == 404 and allow_404: return b""
                error = exc
                if exc.code in (401, 403) or (exc.code == 429 and attempt == 2): break
                if exc.code not in (429, 500, 502, 503, 504): break
                retry = exc.headers.get("Retry-After")
                wait = min(30.0, 2.0 ** attempt)
                if retry:
                    try: wait = min(30.0, float(retry))
                    except ValueError:
                        try: wait = min(30.0, max(0, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()))
                        except (TypeError, ValueError): pass
                time.sleep(wait)
            except URLError as exc: error = exc; time.sleep(min(4.0, 2.0 ** attempt))
        raise RuntimeError(f"Solicitud fallida para {url}: {error}")


def atomic_write(path: Path, data: bytes):
    if path.exists() and path.is_symlink(): raise ValueError(f"No se escribe sobre symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".lgmg-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
        raise


def write_json(path: Path, value): atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def write_csv(path: Path, columns: list[str], rows: list[dict]):
    from io import StringIO
    output = StringIO(newline=""); writer = csv.DictWriter(output, fieldnames=columns); writer.writeheader()
    for row in rows: writer.writerow({key: row.get(key) for key in columns})
    atomic_write(path, output.getvalue().encode("utf-8-sig"))


def validate_download_flags(args):
    if (args.download_images or args.download_datasheets) and not args.confirm_image_rights:
        raise ValueError("Las descargas requieren --confirm-image-rights además de la opción de descarga")
    if args.confirm_image_rights and not (args.download_images or args.download_datasheets):
        raise ValueError("--confirm-image-rights solo es válido junto con una opción de descarga")


def build_parser():
    parser = argparse.ArgumentParser(description="Extractor seguro y revisable del catálogo público LGMG")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--start-url"); source.add_argument("--seed-file")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-products", type=int, default=5)
    parser.add_argument("--electric-only", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    parser.add_argument("--timeout-seconds", type=float, default=20)
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--download-datasheets", action="store_true")
    parser.add_argument("--confirm-image-rights", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    return parser


def main(argv=None):
    parser = build_parser(); args = parser.parse_args(argv)
    try:
        if not 1 <= args.max_products <= MAX_PRODUCTS: raise ValueError(f"--max-products debe estar entre 1 y {MAX_PRODUCTS}")
        if args.delay_seconds < 1.0: raise ValueError("--delay-seconds no puede ser inferior a 1.0")
        if not 5 <= args.timeout_seconds <= 60: raise ValueError("--timeout-seconds debe estar entre 5 y 60")
        validate_download_flags(args)
        repo_root = Path(__file__).resolve().parents[2]
        output = validate_output_dir(args.output_dir, repo_root); output.mkdir(parents=True, exist_ok=True)
        (output / "cache").mkdir(exist_ok=True); (output / "images").mkdir(exist_ok=True)
        fetcher = Fetcher(output / "cache", args.delay_seconds, args.timeout_seconds, args.user_agent, args.refresh_cache)
        errors = []; skipped = 0
        robots_url = "https://www.lgmglifts.com/robots.txt"
        try:
            robots_data = fetcher.fetch(robots_url, page=False, max_bytes=512 * 1024, allow_404=True).decode("utf-8", "replace")
            if not robots_data:
                robots_status = "404_not_published"
            policy = urllib.robotparser.RobotFileParser(); policy.set_url(robots_url); policy.parse(robots_data.splitlines())
            probe = args.start_url or "https://www.lgmglifts.com/es/product/pro-detail-1.htm"
            if not policy.can_fetch(args.user_agent, probe):
                raise ValueError("robots.txt no permite acceder a /es/product/ con este User-Agent")
            if robots_data: robots_status = "fetched_and_allowed"
        except RuntimeError as exc:
            raise ValueError(f"No fue posible verificar robots.txt; ejecución de red detenida: {exc}") from exc
        discovery_status = "seed_file"
        if args.start_url:
            start = canonical_url(args.start_url)
            index = fetcher.fetch(start).decode("utf-8", "replace")
            discovery = CatalogueParser(start); discovery.feed(index)
            urls = dedupe([canonical_url(url) for url in discovery.links])
            discovery_status = "static_listing" if urls else "dynamic_listing_requires_seed"
            if not urls: errors.append({"stage": "discovery", "url": start, "message": "El listado es dinámico y no contiene productos estáticos confiables. Use --seed-file."})
        else:
            start = None; seed = Path(args.seed_file).resolve(strict=True)
            urls = dedupe([canonical_url(line.strip()) for line in seed.read_text(encoding="utf-8-sig").splitlines() if line.strip() and not line.lstrip().startswith("#")])
        discovered = len(urls); urls = urls[:args.max_products]; products = []
        for url in urls:
            try:
                product = parse_product(fetcher.fetch(url).decode("utf-8", "replace"), url)
                if args.electric_only and product["is_electric"] is not True: skipped += 1; continue
                products.append(product)
            except (RuntimeError, ValueError) as exc: errors.append({"stage": "detail", "url": url, "message": str(exc)})
        # Asset download is deliberately explicit; datasheets remain metadata-only in v1.
        hashes = []; downloaded = 0
        if args.download_datasheets: errors.append({"stage": "datasheets", "message": "Descarga de fichas aún deshabilitada; se conservaron metadatos"})
        if args.download_images:
            for product in products:
                model = safe_filename(product["metric_model"] or product["imperial_model"] or "unknown")
                seen_hashes = set()
                for image in product["images"]:
                    try:
                        data = fetcher.fetch(image["url"], page=False, max_bytes=MAX_ASSET_BYTES)
                        digest = hashlib.sha256(data).hexdigest()
                        if digest in seen_hashes: continue
                        seen_hashes.add(digest)
                        # Verify signatures, never trust an HTML extension/content response.
                        signatures = [(b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg"), (b"GIF8", "gif"), (b"RIFF", "webp")]
                        ext = next((e for sig, e in signatures if data.startswith(sig)), None)
                        if not ext or data.lstrip().lower().startswith((b"<html", b"<!doctype")): raise ValueError("Contenido no reconocido como imagen")
                        target = output / "images" / model / f"lgmg-{model}-{downloaded + 1:02d}.{ext}"
                        if target.exists(): raise ValueError("El archivo de imagen ya existe")
                        atomic_write(target, data); downloaded += 1; hashes.append({"path": str(target.relative_to(output)), "sha256": digest})
                    except (RuntimeError, ValueError) as exc: errors.append({"stage": "image", "url": image["url"], "message": str(exc)})
        write_json(output / "catalog.json", products); write_json(output / "errors.json", errors)
        flat = []
        for p in products:
            sm = {s["normalized_key"]: s["value_metric"] for s in p["specifications"] if s["normalized_key"]}
            flat.append({"source_url": p["source_url"], "source_category": p["source_category"], "manufacturer": "LGMG",
                "metric_model": p["metric_model"], "imperial_model": p["imperial_model"], "display_name_suggestion": p["display_name_suggestion"],
                "is_electric": p["is_electric"], **{k: sm.get(k) for k in ("maximum_working_height", "platform_capacity", "overall_width", "overall_length", "machine_weight", "power_source")},
                "image_count": len(p["images"]), "datasheet_count": len(p["datasheets"]), "needs_review": p["needs_review"], "warning_count": len(p["warnings"])})
        catalog_cols = "source_url source_category manufacturer metric_model imperial_model display_name_suggestion is_electric maximum_working_height platform_capacity overall_width overall_length machine_weight power_source image_count datasheet_count needs_review warning_count".split()
        write_csv(output / "catalog.csv", catalog_cols, flat)
        review = [{"metric_model": p["metric_model"], "imperial_model": p["imperial_model"], "source_url": p["source_url"], "needs_review": p["needs_review"],
                   "warnings": " | ".join(p["warnings"]), "missing_fields": " | ".join(k for k in ("metric_model", "source_category") if not p.get(k)),
                   "translation_issues": " | ".join(p["translation_issues"]), "suggested_action": "Revisar evidencia oficial antes de importar"} for p in products]
        write_csv(output / "review.csv", "metric_model imperial_model source_url needs_review warnings missing_fields translation_issues suggested_action".split(), review)
        manifest = {"tool": "lgmg-catalog-extractor", "version": TOOL_VERSION, "start_url": start, "discovery_status": discovery_status, "user_agent": args.user_agent,
            "extracted_at_utc": datetime.now(timezone.utc).isoformat(), "requested_count": args.max_products, "discovered_count": discovered,
            "processed_count": len(products), "skipped_count": skipped, "failed_pages": [e for e in errors if e.get("stage") == "detail"],
            "robots_status": robots_status, "delay_seconds": args.delay_seconds, "timeout_seconds": args.timeout_seconds,
            "images_downloaded": downloaded, "hashes": hashes, "jem_nexus_called": False, "content_published": False}
        write_json(output / "manifest.json", manifest)
        print(f"Procesados: {len(products)}; omitidos: {skipped}; errores: {len(errors)}; salida: {output}")
        return 2 if discovery_status == "dynamic_listing_requires_seed" else 0
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    try: raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrumpido limpiamente; los archivos completos existentes se conservaron.", file=sys.stderr)
        raise SystemExit(130)
