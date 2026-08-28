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
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

TOOL_VERSION = "1.2.5"
ALLOWED_HOST = "www.lgmglifts.com"
DEFAULT_UA = "JemNexusCatalogResearch/1.0 (+https://jem-nexus.cl/contacto)"
MAX_PRODUCTS = 25
HARD_MAX_PRODUCTS = 250
HARD_MAX_PAGES = 50
SEAJ_CONFIG_URL = "https://www.lgmglifts.com/es/resources/web/seajs.config.js"
SEAJ_DOMAIN = "https://www.lgmglifts.com/es"
LISTING_ENDPOINT_URL = "https://www.lgmglifts.com/es/ext/ajax_proList.jsp"
EXPECTED_MODULE = "js/pro_list"
RESOURCE_PREFIX = "/es/resources/"
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
        self.scripts, self.families = [], []

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
        self.scripts = [n.text for n in nodes if n.tag == "script" and n.text]
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
            for node in listing.descendants():
                if "box" not in node.classes or not node.has_ancestor({"type_box"}):
                    continue
                family_id = node.attrs.get("data-id", "")
                if family_id and re.fullmatch(r"[0-9A-Za-z_-]+", family_id) and node.text:
                    marker = (family_id, node.text)
                    if marker not in {(f["id"], f["name"]) for f in self.families}:
                        self.families.append({"id": family_id, "name": node.text})
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


def _electric_evidence(specs: list[dict], title: str = "") -> tuple[list[str], list[str]]:
    """Return strong electrical and combustion evidence without model/family inference."""
    evidence, non_electric = [], []
    electric_terms = re.compile(
        r"\b(electric(?:al)?|electric[oa]|bateria|battery|litio|lithium|plomo[ -]acido|lead[ -]acid)\b",
        re.I,
    )
    combustion_terms = re.compile(r"\b(diesel|gasolina|petrol|combustible|combustion|kubota|deutz)\b", re.I)
    voltage = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)?\s*V\b", re.I)
    capacity = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)?\s*Ah\b", re.I)
    for spec in specs:
        combined = f"{spec['name_original']}: {spec['value_metric']}"
        normalized = strip_accents(combined).casefold()
        if electric_terms.search(normalized) or (voltage.search(combined) and capacity.search(combined)):
            evidence.append(combined)
        if spec["normalized_key"] == "power_source" and combustion_terms.search(normalized):
            non_electric.append(combined)
    normalized_title = strip_accents(title).casefold()
    if re.search(r"\b(electric(?:al)?|electric[oa])\b", normalized_title, re.I):
        evidence.insert(0, f"Título de ficha: {clean_text(title)}")
    return dedupe(evidence), dedupe(non_electric)


def classify_electric(category: str | None, specs: list[dict], title: str = "") -> tuple[bool | None, list[str]]:
    # category is provenance only; power_source is an evidence location, not a conclusion.
    evidence, non_electric = _electric_evidence(specs, title)
    if evidence and non_electric: return None, dedupe(evidence + non_electric)
    if evidence: return True, evidence
    if non_electric: return False, non_electric
    return None, []


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
    electric_evidence, combustion_evidence = _electric_evidence(specs, parser.source_product_title)
    electric, evidence = classify_electric(category, specs, parser.source_product_title)
    warnings = list(models.pop("warnings"))
    missing_fields = [key for key, value in (("metric_model", models["metric_model"]), ("source_category", category)) if not value]
    if not category: warnings.append("Falta la categoría fuente estructurada en crumbs")
    if electric_evidence and combustion_evidence:
        warnings.append("Conflicto entre evidencia eléctrica y de combustión; clasificación pendiente")
    elif electric is None:
        warnings.append("Evidencia eléctrica insuficiente; clasificación pendiente")
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


class DiscoveryError(ValueError):
    """A fail-closed dynamic inspection error safe to include in diagnostics."""


def _strict_url(url: str, kind: str) -> str:
    """Validate one narrowly scoped public LGMG resource."""
    parts = urlsplit(url)
    if (parts.scheme, (parts.hostname or "").lower(), parts.port) not in (("https", ALLOWED_HOST, None), ("https", ALLOWED_HOST, 443)):
        raise DiscoveryError(f"{kind}: se exige HTTPS, host exacto y puerto estándar")
    if parts.username or parts.password or parts.query or parts.fragment or ".." in parts.path.split("/"):
        raise DiscoveryError(f"{kind}: credenciales, query, fragment o traversal rechazado")
    rules = {
        "listing": lambda p: p == "/es/product/pro-list-377.htm",
        "config": lambda p: p == urlsplit(SEAJ_CONFIG_URL).path,
        "module": lambda p: p.startswith(RESOURCE_PREFIX) and p.endswith("/js/pro_list.js"),
        "detail": lambda p: bool(DETAIL_RE.fullmatch(p)),
        "endpoint": lambda p: p == urlsplit(LISTING_ENDPOINT_URL).path,
    }
    if kind not in rules or not rules[kind](parts.path):
        raise DiscoveryError(f"Ruta {kind} fuera del alcance permitido")
    return urlunsplit(("https", ALLOWED_HOST, parts.path, "", ""))


def detect_seajs_module(document: str) -> str:
    matches = re.findall(r"\bseajs\s*\.\s*use\s*\(\s*(['\"])([^'\"]+)\1\s*\)", document)
    modules = dedupe([value for _, value in matches])
    if modules != [EXPECTED_MODULE]:
        raise DiscoveryError("La declaración seajs.use es ausente, ambigua o no corresponde a js/pro_list")
    return modules[0]


def detect_seajs_config(document: str, listing_url: str) -> str:
    """Find and validate the single official SeaJS bootstrap element."""
    parser = CatalogueParser(listing_url)
    parser.feed(document)
    matches = [node for node in parser.root.descendants() if node.attrs.get("id") == "seajsConfig"]
    if len(matches) != 1 or matches[0].tag != "script":
        raise DiscoveryError("Se exige un único elemento script#seajsConfig")
    src = matches[0].attrs.get("src", "").strip()
    domain = matches[0].attrs.get("domain", "").strip()
    if not src or not domain:
        raise DiscoveryError("script#seajsConfig exige src y domain no vacíos")
    if domain != SEAJ_DOMAIN:
        raise DiscoveryError("script#seajsConfig contiene un domain no oficial")
    if ".." in urlsplit(src).path.split("/"):
        raise DiscoveryError("script#seajsConfig contiene traversal en src")
    return _strict_url(urljoin(listing_url, src), "config")


def validate_javascript(document: str, content_type: str = "application/javascript") -> None:
    if "javascript" not in content_type.casefold() and "text/plain" not in content_type.casefold():
        raise DiscoveryError("Content-Type incompatible con JavaScript")
    if document.lstrip().casefold().startswith(("<html", "<!doctype", "<body")):
        raise DiscoveryError("El supuesto JavaScript es una página HTML")


def _strip_javascript_comments(source: str) -> str:
    """Remove comments without changing quoted text or executing JavaScript."""
    output, state, index = [], "normal", 0
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "normal":
            if char == "`":
                raise DiscoveryError("Configuración SeaJS contiene un template literal")
            if char in "'\"":
                state = "single" if char == "'" else "double"
                output.append(char)
            elif char == "/" and following == "/":
                state = "line_comment"; index += 1
            elif char == "/" and following == "*":
                state = "block_comment"; index += 1
            else:
                output.append(char)
        elif state in ("single", "double"):
            output.append(char)
            if char == "\\" and following:
                output.append(following); index += 1
            elif (state == "single" and char == "'") or (state == "double" and char == '"'):
                state = "normal"
        elif state == "line_comment":
            if char in "\r\n":
                output.append(char); state = "normal"
        elif char == "*" and following == "/":
            state = "normal"; index += 1
        elif char in "\r\n":
            output.append(char)
        index += 1
    if state == "block_comment":
        raise DiscoveryError("Configuración SeaJS contiene un comentario de bloque sin cerrar")
    if state in ("single", "double"):
        raise DiscoveryError("Configuración SeaJS contiene una cadena sin cerrar")
    return "".join(output)


def _safe_root_suffix(suffix: str) -> str:
    parts = urlsplit(suffix)
    segments = parts.path.split("/")
    if (not suffix.startswith("/resources/") or parts.scheme or parts.netloc or parts.query or parts.fragment
            or "\\" in suffix or any(ord(char) < 32 or ord(char) == 127 for char in suffix)
            or "//" in suffix or any(segment in (".", "..") for segment in segments)):
        raise DiscoveryError("Sufijo de seajs.root fuera de /resources/ o no seguro")
    return suffix


def _static_seajs_value(raw: str, seajs_root: str, *, allow_root: bool) -> str:
    literal = re.fullmatch(r"\s*(['\"])([^'\"\\\x00-\x1f]*)\1\s*", raw)
    if literal:
        return literal.group(2)
    rooted = re.fullmatch(r"\s*seajs\s*\.\s*root\s*\+\s*(['\"])([^'\"\\\x00-\x1f]*)\1\s*", raw)
    if allow_root and rooted:
        return seajs_root.rstrip("/") + _safe_root_suffix(rooted.group(2))
    raise DiscoveryError("Configuración SeaJS contiene un valor dinámico no permitido")


def _literal_object(source: str, name: str, seajs_root: str = SEAJ_DOMAIN, *, allow_root: bool = False) -> dict[str, str]:
    match = re.search(rf"\b{name}\s*:\s*\{{([^{{}}]*)\}}", source, re.S)
    if not match:
        return {}
    body = match.group(1)
    whitespace = r"[ \t\r\n]*"
    identifier = r"[A-Za-z_$][A-Za-z0-9_$]*"
    module_key = r"[A-Za-z_$][A-Za-z0-9_$.-]*(?:/[A-Za-z_$][A-Za-z0-9_$.-]*)*"
    key_pair = re.compile(
        rf"{whitespace}(?:(?P<bare>{identifier})|'(?P<single>{module_key})'|\"(?P<double>{module_key})\")"
        rf"{whitespace}:{whitespace}"
    )
    result: dict[str, str] = {}
    position = 0
    if re.fullmatch(whitespace, body):
        return result
    while position < len(body):
        item = key_pair.match(body, position)
        if not item:
            raise DiscoveryError(f"Configuración SeaJS {name} no es completamente literal")
        key = item.group("bare") or item.group("single") or item.group("double")
        value_start = item.end(); position = value_start; quote = None
        while position < len(body):
            char = body[position]
            if quote:
                if char == "\\": position += 1
                elif char == quote: quote = None
            elif char in "'\"": quote = char
            elif char == ",": break
            position += 1
        result[key] = _static_seajs_value(body[value_start:position], seajs_root, allow_root=allow_root)
        if position == len(body):
            break
        if body[position] != ",":
            raise DiscoveryError(f"Configuración SeaJS {name} no es completamente literal")
        position += 1
        if re.fullmatch(whitespace, body[position:]):
            position = len(body)
            break
    return result


def resolve_seajs_module(config_source: str, module: str = EXPECTED_MODULE, seajs_root: str = SEAJ_DOMAIN) -> str:
    validate_javascript(config_source)
    source = _strip_javascript_comments(config_source)
    configs = list(re.finditer(r"\bseajs\s*\.\s*config\s*\(", source))
    if len(configs) != 1:
        raise DiscoveryError("La configuración SeaJS es ausente o ambigua")
    body = source[configs[0].end():]
    base_match = re.search(r"\bbase\s*:\s*(.*?)(?=,\s*(?:paths|alias)\s*:|\s*})", body, re.S)
    base = _static_seajs_value(base_match.group(1), seajs_root, allow_root=True) if base_match else RESOURCE_PREFIX
    paths = _literal_object(body, "paths", seajs_root, allow_root=True)
    alias = _literal_object(body, "alias", seajs_root, allow_root=False)
    resolved = alias.get(module, module)
    first, slash, rest = resolved.partition("/")
    if first in paths:
        resolved = paths[first].rstrip("/") + ("/" + rest if slash else "")
    if not resolved.endswith(".js"):
        resolved += ".js"
    absolute = urljoin(urljoin(seajs_root.rstrip("/") + "/", base.rstrip("/") + "/"), resolved)
    return _strict_url(absolute, "module")


def _split_balanced(source: str, separator: str = ",") -> list[str]:
    """Split a small JavaScript argument/object list without evaluating it."""
    parts, start, stack, quote, escaped = [], 0, [], None, False
    pairs = {")": "(", "}": "{", "]": "["}
    for index, char in enumerate(source):
        if quote:
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == quote: quote = None
            continue
        if char in "'\"": quote = char
        elif char in "({[": stack.append(char)
        elif char in ")} ]".replace(" ", ""):
            if not stack or stack.pop() != pairs[char]: raise DiscoveryError("Expresión JavaScript desbalanceada")
        elif char == separator and not stack:
            parts.append(source[start:index].strip()); start = index + 1
    if quote or stack: raise DiscoveryError("Expresión JavaScript incompleta")
    parts.append(source[start:].strip())
    return parts


def _literal_initializers(source: str) -> dict[str, object]:
    values = {}
    for declaration in re.finditer(r"\bvar\s+([^;]+);", source, re.S):
        for item in _split_balanced(declaration.group(1)):
            pair = item.split("=", 1)
            if len(pair) != 2 or not re.fullmatch(r"[A-Za-z_$][\w$]*", pair[0].strip()): continue
            name, raw = pair[0].strip(), pair[1].strip()
            literal = re.fullmatch(r"(['\"])([^'\"\\]*)\1|(-?\d+)", raw)
            if literal and name not in values:
                values[name] = literal.group(2) if literal.group(1) else int(literal.group(3))
    return values


def _parse_data_object(body: str, initializers: dict[str, object]) -> tuple[dict[str, object], dict[str, str]]:
    values, references = {}, {}
    for item in _split_balanced(body):
        pair = item.split(":", 1)
        if len(pair) != 2: raise DiscoveryError("Parámetros de solicitud ambiguos")
        key, raw = pair[0].strip().strip("'\""), pair[1].strip()
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", key) or key in values:
            raise DiscoveryError("Clave de parámetro repetida o no permitida")
        literal = re.fullmatch(r"(['\"])([^'\"\\]*)\1|(-?\d+)", raw)
        if literal: values[key] = literal.group(2) if literal.group(1) else int(literal.group(3))
        elif re.fullmatch(r"[A-Za-z_$][\w$]*", raw) and raw in initializers:
            values[key], references[key] = initializers[raw], raw
        else: raise DiscoveryError("Variable sin inicialización literal controlada")
    return values, references


def _ajax_objects(source: str) -> list[str]:
    results = []
    for match in re.finditer(r"(?:\$\s*\.\s*ajax|\bajax)\s*\(\s*\{", source):
        start = match.end() - 1; depth = 0; quote = None; escaped = False
        for index in range(start, len(source)):
            char = source[index]
            if quote:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == quote: quote = None
                continue
            if char in "'\"": quote = char
            elif char == "{": depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    if not re.match(r"\s*\)", source[index + 1:]):
                        raise DiscoveryError("Cierre AJAX ambiguo")
                    results.append(source[start + 1:index]); break
        else: raise DiscoveryError("Objeto AJAX incompleto")
    return results


def _post_calls(source: str) -> list[tuple[str, str, str]]:
    results = []
    for match in re.finditer(r"\$\s*\.\s*post\s*\(", source):
        start, depth, quote, escaped = match.end(), 1, None, False
        for index in range(start, len(source)):
            char = source[index]
            if quote:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == quote: quote = None
                continue
            if char in "'\"": quote = char
            elif char == "(": depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    args = _split_balanced(source[start:index])
                    if len(args) != 3: raise DiscoveryError("$.post exige exactamente URL, datos y callback")
                    callback = args[2].strip()
                    if not re.fullmatch(r"function\s*\([^)]*\)\s*\{[\s\S]*\}", callback):
                        raise DiscoveryError("Callback $.post incompleto o ambiguo")
                    results.append((args[0], args[1], callback)); break
        else: raise DiscoveryError("Llamada $.post incompleta")
    return results


def _endpoint_expression(raw: str) -> str:
    match = re.fullmatch(r"\s*seajs\s*\.\s*root\s*\+\s*(['\"])/ext/ajax_proList\.jsp\1\s*", raw)
    if not match: raise DiscoveryError("Expresión del endpoint oficial ausente o ambigua")
    return _strict_url(SEAJ_DOMAIN + "/ext/ajax_proList.jsp", "endpoint")


def parse_listing_module(source: str) -> dict:
    validate_javascript(source)
    if re.search(r"\b(?:WebSocket|jsonp|csrf|token|Authorization|Cookie)\b", source, re.I):
        raise DiscoveryError("El módulo requiere un protocolo, token o credencial no admitido")
    clean = _strip_javascript_comments(source)
    initializers = _literal_initializers(clean)
    candidates = []
    for block in _ajax_objects(clean):
        data = re.search(r"\bdata\s*:\s*\{([^{}]*)\}", block, re.S)
        if data:
            params, refs = _parse_data_object(data.group(1), initializers)
            candidates.append({"method": (re.search(r"\b(?:type|method)\s*:\s*(['\"])(GET|POST)\1", block, re.I) or [None, None, ""])[2].upper(), "params": params, "refs": refs})
    for url_raw, data_raw, callback in _post_calls(clean):
        object_match = re.fullmatch(r"\s*\{([\s\S]*)\}\s*", data_raw)
        if not object_match: raise DiscoveryError("El segundo argumento de $.post debe ser un objeto literal")
        params, refs = _parse_data_object(object_match.group(1), initializers)
        candidates.append({"method": "POST", "endpoint": _endpoint_expression(url_raw), "params": params,
                           "refs": refs, "html_callback": bool(re.search(r"\$\s*\(\s*['\"]#container['\"]\s*\)\s*\.\s*(?:html|append)\s*\(", callback))})
    product_calls = [candidate for candidate in candidates if candidate["params"].get("flag") == "pro"]
    expected = {"flag", "min1", "max1", "min2", "max2", "min3", "max3", "min4", "max4", "catId", "key", "nowPage", "gmzhi"}
    valid = [candidate for candidate in product_calls if candidate["method"] == "POST" and candidate.get("endpoint") == LISTING_ENDPOINT_URL and candidate.get("html_callback") and set(candidate["params"]) == expected]
    if len(valid) != 1: raise DiscoveryError("Operación flag:'pro' oficial ausente o ambigua")
    operation = valid[0]; params, refs = operation["params"], operation["refs"]
    constants = {"flag": "pro", "min1": "", "max1": "", "min2": "", "max2": "", "min3": "", "max3": "", "min4": "", "max4": "", "key": "", "gmzhi": 1}
    expected_refs = {"min1": "data1", "max1": "data2", "min2": "data3", "max2": "data4",
                     "min3": "data5", "max3": "data6", "min4": "data7", "max4": "data8",
                     "catId": "catId", "key": "key", "nowPage": "nowPage", "gmzhi": "gmzhi"}
    expected_initializers = {"catId": "", "data1": "", "data2": "", "data3": "", "data4": "", "data5": "",
                             "data6": "", "data7": "", "data8": "", "key": "", "gmzhi": 1, "nowPage": 1}
    if (any(params.get(key) != value for key, value in constants.items()) or refs != expected_refs
            or any(initializers.get(key) != value for key, value in expected_initializers.items())):
        raise DiscoveryError("Valores iniciales de la operación de productos no permitidos")
    return {"endpoint": LISTING_ENDPOINT_URL, "method": "POST", "body_format": "application/x-www-form-urlencoded",
            "parameters": params, "category_parameter": "catId", "page_parameter": "nowPage", "page_size_parameter": None,
            "initial_page": 1, "response_container": "html", "termination": "empty_or_repeated_or_no_new",
            "variables": sorted(set(refs.values()))}


def parse_dynamic_response(payload: bytes | str, content_type: str, base_url: str, family: dict, page: int) -> tuple[list[dict], list[dict]]:
    raw = payload.decode("utf-8", "strict") if isinstance(payload, bytes) else payload
    if len(raw.encode("utf-8")) > MAX_HTML_BYTES or "\x00" in raw:
        raise DiscoveryError("Respuesta dinámica binaria o demasiado grande")
    if "json" in content_type.casefold():
        try: value = json.loads(raw)
        except json.JSONDecodeError as exc: raise DiscoveryError("JSON de listado inválido") from exc
        if isinstance(value, dict):
            html_value = next((value[k] for k in ("html", "content", "data") if isinstance(value.get(k), str)), None)
            records = next((value[k] for k in ("items", "records", "products", "data") if isinstance(value.get(k), list)), [])
            candidates = re.findall(r"href\s*=\s*['\"]([^'\"]+)", html_value or "", re.I)
            for record in records:
                if isinstance(record, dict):
                    candidate = next((record.get(k) for k in ("url", "href", "link", "detailUrl") if isinstance(record.get(k), str)), None)
                    if candidate: candidates.append(candidate)
        else: raise DiscoveryError("El JSON no contiene un listado estructurado")
    elif "html" in content_type.casefold() or "text/plain" in content_type.casefold():
        candidates = re.findall(r"href\s*=\s*['\"]([^'\"]+)", raw, re.I)
    else: raise DiscoveryError("Content-Type de listado no admitido")
    accepted, rejected = [], []
    for candidate in candidates:
        try: target = _strict_url(urljoin(base_url, candidate), "detail")
        except DiscoveryError as exc:
            rejected.append({"url": clean_text(candidate)[:200], "reason": str(exc)}); continue
        accepted.append({"family_id": family["id"], "family": family["name"], "url": target, "page": page})
    return accepted, rejected


def deduplicate_discovery(rows: list[dict]) -> list[dict]:
    first = {}
    for order, row in enumerate(rows, 1):
        row["order"] = order; row["duplicate"] = row["url"] in first
        row["status"] = "duplicate" if row["duplicate"] else "accepted"
        first.setdefault(row["url"], row)
    return list(first.values())


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

    def fetch_controlled(self, url: str, kind: str, *, method="GET", parameters=None,
                         body_format="application/x-www-form-urlencoded", max_bytes=MAX_HTML_BYTES) -> tuple[bytes, str]:
        url = _strict_url(url, kind)
        parameters = parameters or {}
        if method not in ("GET", "POST"):
            raise DiscoveryError("Método de listado no permitido")
        data = None
        if method == "GET" and parameters:
            url += "?" + urlencode(parameters)
        elif method == "POST":
            if body_format == "application/json": data = json.dumps(parameters, separators=(",", ":")).encode()
            elif body_format == "application/x-www-form-urlencoded": data = urlencode(parameters).encode()
            else: raise DiscoveryError("Formato POST no permitido")
        cache_key = f"{method}\n{url}\n{data!r}"
        cache = self.cache_dir / (hashlib.sha256(cache_key.encode()).hexdigest() + ".bin")
        meta = cache.with_suffix(".json")
        if cache.exists() and meta.exists() and not self.refresh:
            return cache.read_bytes(), json.loads(meta.read_text(encoding="utf-8"))["content_type"]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        headers = {"User-Agent": self.user_agent, "Accept": "application/json,text/html,application/javascript;q=0.9"}
        if data is not None: headers["Content-Type"] = body_format
        request = Request(url, data=data, headers=headers, method=method)
        handler = SafeRedirectHandler(); self.last_request = time.monotonic()
        try:
            with build_opener(handler).open(request, timeout=self.timeout) as response:
                _strict_url(response.url.split("?", 1)[0], kind)
                content = response.read(max_bytes + 1)
                if len(content) > max_bytes: raise DiscoveryError("Recurso controlado excede el tamaño máximo")
                content_type = response.headers.get_content_type()
                atomic_write(cache, content); write_json(meta, {"content_type": content_type})
                return content, content_type
        except HTTPError as exc:
            raise DiscoveryError(f"{kind}: HTTP {exc.code} al solicitar recurso controlado") from None
        except (URLError, TimeoutError):
            raise DiscoveryError(f"{kind}: fallo de red al solicitar recurso controlado") from None


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
    parser.add_argument("--discovery-mode", choices=("static", "dynamic"), default="static")
    parser.add_argument("--discovery-only", action="store_true")
    parser.add_argument("--inventory-all", action="store_true")
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
        maximum = HARD_MAX_PRODUCTS if args.inventory_all else MAX_PRODUCTS
        if not 1 <= args.max_products <= maximum: raise ValueError(f"--max-products debe estar entre 1 y {maximum}")
        if args.inventory_all and args.discovery_mode != "dynamic": raise ValueError("--inventory-all exige --discovery-mode dynamic")
        if args.discovery_mode == "dynamic" and not args.start_url: raise ValueError("El modo dinámico exige --start-url")
        if args.discovery_only and (args.download_images or args.download_datasheets): raise ValueError("--discovery-only no admite descargas")
        if args.delay_seconds < 1.0: raise ValueError("--delay-seconds no puede ser inferior a 1.0")
        if not 5 <= args.timeout_seconds <= 60: raise ValueError("--timeout-seconds debe estar entre 5 y 60")
        validate_download_flags(args)
        repo_root = Path(__file__).resolve().parents[2]
        output = validate_output_dir(args.output_dir, repo_root); output.mkdir(parents=True, exist_ok=True)
        (output / "cache").mkdir(exist_ok=True); (output / "images").mkdir(exist_ok=True)
        fetcher = Fetcher(output / "cache", args.delay_seconds, args.timeout_seconds, args.user_agent, args.refresh_cache)
        errors = []; skipped = 0; uncertain = 0; pages_requested = 0
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
        report = {"start_url": None, "mode": args.discovery_mode, "seajs_module": None,
            "config_url": None, "module_url": None, "endpoint": None, "method": None,
            "parameters": {}, "response_format": None, "families": [], "pages_requested": 0,
            "details_found": 0, "details_unique": 0, "rejected_links": [], "status": discovery_status,
            "warnings": [], "stop_reason": None}
        discovery_rows = []; family_rows = []
        exit_code = 0
        if args.start_url and args.discovery_mode == "dynamic":
            start = _strict_url(args.start_url, "listing"); report["start_url"] = start
            error_url = start
            try:
                index_bytes, index_type = fetcher.fetch_controlled(start, "listing")
                if "html" not in index_type: raise DiscoveryError("El listado inicial no es HTML")
                index = index_bytes.decode("utf-8", "strict")
                listing = CatalogueParser(start); listing.feed(index)
                config_url = detect_seajs_config(index, start); report["config_url"] = config_url
                module = detect_seajs_module(index); report["seajs_module"] = module
                error_url = config_url
                config_bytes, config_type = fetcher.fetch_controlled(config_url, "config", max_bytes=512 * 1024)
                config_source = config_bytes.decode("utf-8", "strict"); validate_javascript(config_source, config_type)
                module_url = resolve_seajs_module(config_source, module, SEAJ_DOMAIN); report["module_url"] = module_url
                error_url = module_url
                module_bytes, module_type = fetcher.fetch_controlled(module_url, "module", max_bytes=1024 * 1024)
                module_source = module_bytes.decode("utf-8", "strict"); validate_javascript(module_source, module_type)
                operation = parse_listing_module(module_source)
                report.update({"endpoint": operation["endpoint"], "method": operation["method"],
                    "parameters": operation["parameters"], "response_format": operation["response_container"]})
                families = listing.families
                if not families: raise DiscoveryError("No se identificaron familias públicas estructuradas")
                seen_responses = set(); unique_urls = set(); stop_all = False
                for family_order, family in enumerate(families, 1):
                    found_before = len(discovery_rows); unique_before = len(unique_urls); family_pages = 0; family_seen = set()
                    family_status = "complete"; warning = ""
                    for offset in range(HARD_MAX_PAGES):
                        page = operation["initial_page"] + offset
                        params = {}
                        for key, value in operation["parameters"].items():
                            if key == operation["category_parameter"]: params[key] = family["id"]
                            elif key == operation["page_parameter"]: params[key] = page
                            elif isinstance(value, str) and value.startswith("{"):
                                if operation["page_size_parameter"] == key: params[key] = min(args.max_products, HARD_MAX_PRODUCTS)
                                else: raise DiscoveryError("Variable pública no asignable de forma cerrada")
                            else: params[key] = value
                        error_url = operation["endpoint"]
                        payload, content_type = fetcher.fetch_controlled(operation["endpoint"], "endpoint", method=operation["method"],
                            parameters=params, body_format=operation["body_format"])
                        pages_requested += 1; family_pages += 1
                        digest = hashlib.sha256(payload).hexdigest()
                        if digest in seen_responses: family_status = "stopped_repeated_response"; break
                        seen_responses.add(digest)
                        rows, rejected = parse_dynamic_response(payload, content_type, start, family, page)
                        report["rejected_links"].extend(rejected)
                        if not rows: family_status = "complete_empty_page"; break
                        page_urls = tuple(row["url"] for row in rows)
                        if page_urls in family_seen: family_status = "stopped_repeated_page"; break
                        family_seen.add(page_urls)
                        new_count = 0
                        for row in rows:
                            row["endpoint"] = operation["endpoint"]; row["rejection_reason"] = ""
                            discovery_rows.append(row)
                            if row["url"] not in unique_urls:
                                unique_urls.add(row["url"]); new_count += 1
                                if len(unique_urls) == args.max_products:
                                    family_status = "stopped_by_limit"; discovery_status = "stopped_by_limit"; stop_all = True
                                    break
                        if stop_all: break
                        if new_count == 0: family_status = "stopped_no_new_details"; break
                    else: family_status = "stopped_by_page_limit"; warning = "Se alcanzó el máximo duro de 50 páginas"
                    family_rows.append({"order": family_order, "id": family["id"], "name": family["name"],
                        "found": len(discovery_rows) - found_before, "unique": len(unique_urls) - unique_before,
                        "pages": family_pages, "status": family_status, "warnings": warning, "source_url": start,
                        "method": "listing_html"})
                    if stop_all: break
                if discovery_status != "stopped_by_limit": discovery_status = "dynamic_listing"
                if len(unique_urls) > args.max_products:
                    raise DiscoveryError("Inconsistencia interna: el descubrimiento excedió --max-products")
            except (DiscoveryError, UnicodeError, RuntimeError) as exc:
                discovery_status = "dynamic_inspection_required"; report["stop_reason"] = str(exc)
                errors.append({"stage": "dynamic_discovery", "url": error_url, "message": str(exc)})
                urls = []; exit_code = 3
        elif args.start_url:
            start = canonical_url(args.start_url)
            report["start_url"] = start
            index = fetcher.fetch(start).decode("utf-8", "replace")
            discovery = CatalogueParser(start); discovery.feed(index)
            urls = dedupe([canonical_url(url) for url in discovery.links])
            discovery_status = "static_listing" if urls else "dynamic_inspection_required"
            discovery_rows = [{"family_id": "", "family": "", "url": url, "page": 1, "endpoint": start, "rejection_reason": ""} for url in urls]
            if not urls:
                errors.append({"stage": "discovery", "url": start, "message": "El listado dinámico requiere --discovery-mode dynamic o --seed-file."}); exit_code = 2
        else:
            start = None; seed = Path(args.seed_file).resolve(strict=True)
            urls = dedupe([canonical_url(line.strip()) for line in seed.read_text(encoding="utf-8-sig").splitlines() if line.strip() and not line.lstrip().startswith("#")])
            discovery_rows = [{"family_id": "", "family": "", "url": url, "page": 1, "endpoint": "seed_file", "rejection_reason": ""} for url in urls]
        final_rows = deduplicate_discovery(discovery_rows)
        if args.discovery_mode == "dynamic" and len(final_rows) > args.max_products:
            raise DiscoveryError("Inconsistencia interna: las filas dinámicas exceden --max-products")
        discovery_rows = final_rows[:args.max_products]
        urls = [row["url"] for row in discovery_rows]
        unique_count = len({row["url"] for row in discovery_rows})
        if len(discovery_rows) > args.max_products or unique_count > args.max_products or len(urls) > args.max_products:
            raise DiscoveryError("Inconsistencia interna: los resultados finales exceden --max-products")
        if discovery_status == "stopped_by_limit" and unique_count != args.max_products:
            raise DiscoveryError("Inconsistencia interna: stopped_by_limit sin alcanzar --max-products")
        report.update({"families": family_rows, "pages_requested": pages_requested,
            "details_found": len(discovery_rows), "details_unique": unique_count, "status": discovery_status})
        if not report["stop_reason"] and discovery_status == "stopped_by_limit": report["stop_reason"] = "maximum_products"
        discovered = len(discovery_rows); products = []; reviewed_products = []
        for url in ([] if args.discovery_only else urls):
            try:
                product = parse_product(fetcher.fetch(url).decode("utf-8", "replace"), url)
                reviewed_products.append(product)
                if args.electric_only and product["is_electric"] is False: skipped += 1; continue
                if args.electric_only and product["is_electric"] is None: uncertain += 1; continue
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
        write_json(output / "catalog.json", products); write_json(output / "errors.json", errors); write_json(output / "discovery.json", report)
        write_csv(output / "discovery.csv", "order family family_id url page endpoint status duplicate rejection_reason".split(), discovery_rows)
        write_csv(output / "families.csv", "order id name found unique pages status warnings".split(), family_rows)
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
                   "translation_issues": " | ".join(p["translation_issues"]), "suggested_action": "Revisar evidencia oficial antes de importar"} for p in reviewed_products if p["needs_review"] or p["is_electric"] is None]
        write_csv(output / "review.csv", "metric_model imperial_model source_url needs_review warnings missing_fields translation_issues suggested_action".split(), review)
        manifest = {"tool": "lgmg-catalog-extractor", "version": TOOL_VERSION, "start_url": start, "discovery_mode": args.discovery_mode,
            "discovery_status": discovery_status, "discovery_module": report["module_url"], "listing_endpoint": report["endpoint"], "listing_method": report["method"],
            "families_discovered": len(family_rows), "pages_requested": pages_requested, "detail_urls_discovered": len(discovery_rows),
            "detail_urls_unique": unique_count, "user_agent": args.user_agent,
            "extracted_at_utc": datetime.now(timezone.utc).isoformat(), "requested_count": args.max_products, "discovered_count": discovered,
            "processed_count": len(products), "skipped_count": skipped, "failed_pages": [e for e in errors if e.get("stage") == "detail"],
            "robots_status": robots_status, "delay_seconds": args.delay_seconds, "timeout_seconds": args.timeout_seconds,
            "electric_confirmed": sum(p["is_electric"] is True for p in reviewed_products), "non_electric_skipped": skipped,
            "classification_uncertain": uncertain, "needs_review_count": len(review), "images_downloaded": downloaded,
            "datasheets_downloaded": 0, "hashes": hashes, "jem_nexus_called": False, "content_published": False}
        write_json(output / "manifest.json", manifest)
        print(f"Procesados: {len(products)}; omitidos: {skipped}; errores: {len(errors)}; salida: {output}")
        return exit_code
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    try: raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrumpido limpiamente; los archivos completos existentes se conservaron.", file=sys.stderr)
        raise SystemExit(130)
