#!/usr/bin/env python3
"""Build an offline, deterministic and non-applying LGMG import plan."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata
import zipfile

TOOL_NAME = "lgmg-jem-import-plan-generator"
TOOL_VERSION = "1.0.0"
REVIEW_TOOL = "lgmg-jem-review-preparer"
MEDIA_TOOL = "lgmg-jem-review-media-downloader"
REVIEW_REQUIRED = (
    "review-products.csv", "review-specifications.csv", "review-images.csv",
    "review-datasheets.csv", "review-missing-datasheets.csv", "review-categories.csv",
    "review-uncertain.csv", "jem-review-drafts.json", "review-summary.json",
    "review-summary.txt", "README-review.txt", "review-manifest.json",
)
MEDIA_REPORTS = (
    "downloaded-images.csv", "downloaded-datasheets.csv", "media-files.csv",
    "media-failures.csv", "media-summary.json", "media-summary.txt",
    "media-download-state.json", "README-media.txt",
)
OUTPUTS = (
    "import-products.csv", "import-specifications.csv", "import-images.csv",
    "import-datasheets.csv", "import-categories.csv", "import-brand.csv",
    "import-warnings.csv", "manual-actions.csv", "import-plan.json",
    "import-summary.json", "import-summary.txt", "README-import-plan.txt",
)
CATEGORY_MAPPING = (
    ("Elevadores de Tijera", "Elevadores tipo tijera eléctricos"),
    ("Elevador Eléctrico RT de Tijera", "Elevadores tipo tijera todoterreno"),
    ("Elevadores de Brazo Articulado", "Elevadores tipo brazo articulado"),
    ("Elevadores de Brazo Telescópico", "Elevadores tipo brazo telescópico"),
    ("Elevador Mástil Vertical", "Elevadores tipo mástil vertical"),
    ("Elevador de Tijera Sobre Orugas", "Elevadores tipo tijera sobre orugas"),
    ("Manipuladores Telescópicos", "Manipuladores telescópicos"),
)
MAPPING_VERSION = "lgmg-owner-decisions-1"
EFFECTS = {"api_called": False, "database_changed": False, "categories_changed": False,
    "brands_changed": False, "products_created": 0, "images_uploaded": 0,
    "datasheets_uploaded": 0, "products_deleted": 0, "content_published": False}
MAX_SELECTED = 128 * 1024 * 1024


class PlanError(ValueError):
    """A controlled validation failure safe to show without machine paths."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes, name: str):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"JSON inválido: {name}") from exc


def _csv(data: bytes, name: str) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise PlanError(f"CSV inválido: {name}") from exc
    return [row for row in rows if any((value or "").strip() for value in row.values())]


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise PlanError("Ruta relativa inválida")
    parts = value.split("/")
    if any(not part or part in (".", "..") or any(ord(c) < 32 for c in part) for part in parts):
        raise PlanError("Ruta con traversal o segmentos ambiguos")
    normalized = PurePosixPath(*parts).as_posix()
    if normalized != value:
        raise PlanError("Ruta relativa no canónica")
    return normalized


def _zip_name(name: str) -> str:
    if not name:
        raise PlanError("ZIP con ruta insegura")
    name = name.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise PlanError("ZIP con ruta insegura")
    trailing = name.endswith("/")
    parts = name[:-1].split("/") if trailing else name.split("/")
    if any(not part or part in (".", "..") for part in parts):
        raise PlanError("ZIP con traversal o segmentos ambiguos")
    return "/".join(parts) + ("/" if trailing else "")


def _read_review_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        normalized = {}
        roots = set()
        for info in archive.infolist():
            name = _zip_name(info.filename)
            mode = info.external_attr >> 16
            if info.flag_bits & 1 or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
                raise PlanError("ZIP cifrado, symlink o tipo especial no admitido")
            if name in normalized:
                raise PlanError("ZIP con duplicados después de normalizar")
            normalized[name] = info
            parts = PurePosixPath(name.rstrip("/")).parts
            roots.update("/".join(parts[:i + 1]) for i, part in enumerate(parts) if part == "review-package")
        if len(roots) != 1:
            raise PlanError("Se exige exactamente un review-package")
        root = next(iter(roots)); result = {}; total = 0
        for leaf in REVIEW_REQUIRED:
            info = normalized.get(f"{root}/{leaf}")
            if info is None or info.is_dir():
                raise PlanError(f"Archivo de revisión ausente: {leaf}")
            total += info.file_size
            if total > MAX_SELECTED:
                raise PlanError("Paquete de revisión demasiado grande")
            result[leaf] = archive.read(info)
        return result


def _find_package(path: Path, package_name: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise PlanError("La entrada debe ser una carpeta segura")
    roots = [path] if path.name == package_name else [p for p in path.iterdir()
        if p.name == package_name and p.is_dir() and not p.is_symlink()]
    if len(roots) != 1:
        raise PlanError(f"Se exige exactamente un {package_name}")
    return roots[0]


def read_review(path: Path) -> tuple[dict[str, bytes], str]:
    if path.is_symlink():
        raise PlanError("La entrada de revisión no puede ser symlink")
    if path.is_file() and path.suffix.casefold() == ".zip":
        return _read_review_zip(path), "zip"
    root = _find_package(path, "review-package"); raw = {}; total = 0
    for leaf in REVIEW_REQUIRED:
        item = root / leaf
        if not item.is_file() or item.is_symlink():
            raise PlanError(f"Archivo de revisión ausente o inseguro: {leaf}")
        total += item.stat().st_size
        if total > MAX_SELECTED: raise PlanError("Paquete de revisión demasiado grande")
        raw[leaf] = item.read_bytes()
    return raw, "folder"


def read_media(path: Path) -> tuple[Path, dict[str, bytes]]:
    if path.is_file():
        raise PlanError("El paquete de medios no admite ZIP")
    root = _find_package(path, "media-package"); raw = {}
    for leaf in (*MEDIA_REPORTS, "media-manifest.json"):
        item = root / leaf
        if not item.is_file() or item.is_symlink():
            raise PlanError(f"Archivo de medios ausente o inseguro: {leaf}")
        raw[leaf] = item.read_bytes()
    return root, raw


def review_fingerprint(raw: dict[str, bytes]) -> str:
    # This is the exact fingerprint consumed by the media downloader.
    names = ("review-products.csv", "review-images.csv", "review-datasheets.csv",
        "review-missing-datasheets.csv", "review-manifest.json", "jem-review-drafts.json")
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode()); digest.update(b"\0"); digest.update(raw[name])
    return digest.hexdigest()


def validate_review(raw: dict[str, bytes]) -> dict:
    manifest = _json(raw["review-manifest.json"], "review-manifest.json")
    if not isinstance(manifest, dict) or manifest.get("tool") != REVIEW_TOOL or manifest.get("version") != "1.0.0":
        raise PlanError("Manifest de revisión no admitido")
    generated = {x.get("name"): x for x in manifest.get("generated_files", []) if isinstance(x, dict)}
    for name in REVIEW_REQUIRED:
        if name == "review-manifest.json": continue
        item = generated.get(name)
        if not item or item.get("size") != len(raw[name]) or item.get("sha256") != _sha(raw[name]):
            raise PlanError(f"Hash o tamaño de revisión inconsistente: {name}")
    products = _csv(raw["review-products.csv"], "review-products.csv")
    specs = _csv(raw["review-specifications.csv"], "review-specifications.csv")
    images = _csv(raw["review-images.csv"], "review-images.csv")
    sheets = _csv(raw["review-datasheets.csv"], "review-datasheets.csv")
    missing = _csv(raw["review-missing-datasheets.csv"], "review-missing-datasheets.csv")
    uncertain = _csv(raw["review-uncertain.csv"], "review-uncertain.csv")
    drafts = _json(raw["jem-review-drafts.json"], "jem-review-drafts.json")
    keys = []
    for row in products:
        key = row.get("source_key", "")
        if not re.fullmatch(r"lgmg-[0-9a-f]{16}", key) or key in keys:
            raise PlanError("Clave estable inválida o duplicada")
        keys.append(key)
        if row.get("ready_for_import", "").casefold() != "false" or row.get("published", "").casefold() != "false":
            raise PlanError("La revisión contiene productos listos o publicados")
        if row.get("price") or row.get("currency") or row.get("source_category") not in dict(CATEGORY_MAPPING):
            raise PlanError("Precio, moneda o categoría fuente inválidos")
        if not row.get("source_url", "").startswith("https://www.lgmglifts.com/es/product/"):
            raise PlanError("Procedencia oficial inválida")
    if not isinstance(drafts, list) or [d.get("source_key") for d in drafts] != keys:
        raise PlanError("Borradores fuera de orden o inconsistentes")
    for draft in drafts:
        if draft.get("ready_for_import") is not False or (draft.get("product_draft") or {}).get("published") is not False:
            raise PlanError("Borrador listo o publicado")
    keyset = set(keys)
    for rows, order_name in ((specs, "specification_order"), (images, "image_order"), (sheets, "datasheet_order")):
        positions = {}
        for row in rows:
            key = row.get("source_key")
            if key not in keyset: raise PlanError("Asociación con producto incierto")
            try: order = int(row.get(order_name, ""))
            except ValueError as exc: raise PlanError("Orden fuente inválido") from exc
            if order != positions.get(key, 0) + 1: raise PlanError("Orden fuente no contiguo")
            positions[key] = order
    counts = manifest.get("counts", {})
    expected = {"products_in_review": len(products), "specifications": len(specs),
        "image_references": len(images), "datasheet_references": len(sheets),
        "products_without_datasheets": len(missing), "classification_uncertain": len(uncertain)}
    if any(counts.get(k) != v for k, v in expected.items()) or counts.get("content_published") is not False:
        raise PlanError("Conteos o estado de revisión inconsistentes")
    return {"manifest": manifest, "products": products, "specs": specs, "images": images,
        "datasheets": sheets, "missing": missing, "uncertain": uncertain, "drafts": drafts,
        "fingerprint": review_fingerprint(raw)}


def validate_media(root: Path, raw: dict[str, bytes], review: dict) -> dict:
    manifest = _json(raw["media-manifest.json"], "media-manifest.json")
    if not isinstance(manifest, dict) or manifest.get("tool") != MEDIA_TOOL or manifest.get("version") != "1.0.0":
        raise PlanError("Manifest de medios no admitido")
    required = {"operator_confirmed_media_rights": True, "robots_allowed": True, "package_complete": True,
        "jem_nexus_called": False, "products_imported": 0, "content_published": False,
        "all_products_ready_for_import": False}
    if any(manifest.get(k) != v for k, v in required.items()): raise PlanError("Garantías del paquete de medios incumplidas")
    if manifest.get("input_fingerprint_sha256") != review["fingerprint"]: raise PlanError("Fingerprint cruzado incorrecto")
    declared = manifest.get("files", [])
    by_name = {}
    for item in declared:
        if not isinstance(item, dict): raise PlanError("Archivo declarado inválido")
        name = safe_relative(item.get("name", ""))
        if name in by_name: raise PlanError("Ruta declarada duplicada")
        by_name[name] = item
    for name in MEDIA_REPORTS:
        item = by_name.get(name)
        if not item or item.get("size") != len(raw[name]) or item.get("sha256") != _sha(raw[name]):
            raise PlanError(f"Hash o tamaño de reporte inconsistente: {name}")
    actual = set()
    for item in root.rglob("*"):
        if item.is_symlink(): raise PlanError("Symlink detectado en medios")
        if item.is_file(): actual.add(item.relative_to(root).as_posix())
        elif not item.is_dir(): raise PlanError("Tipo especial detectado en medios")
    if actual != set(by_name) | {"media-manifest.json"}: raise PlanError("Archivos físicos ausentes o no declarados")
    file_rows = _csv(raw["media-files.csv"], "media-files.csv")
    for row in file_rows:
        rel = safe_relative(row.get("local_file", "")); item = root.joinpath(*PurePosixPath(rel).parts)
        data = item.read_bytes(); declared_item = by_name.get(rel)
        if not declared_item or int(row.get("size_bytes", -1)) != len(data) or row.get("sha256") != _sha(data):
            raise PlanError("Hash o tamaño de medio inconsistente")
        if declared_item.get("size") != len(data) or declared_item.get("sha256") != _sha(data):
            raise PlanError("Manifest físico inconsistente")
        kind = row.get("media_type"); mime = row.get("mime_type", "")
        if (kind == "image" and mime not in ("image/jpeg", "image/png", "image/webp")) or (kind == "datasheet" and mime != "application/pdf"):
            raise PlanError("MIME o tipo físico incompatible")
    images = _csv(raw["downloaded-images.csv"], "downloaded-images.csv")
    sheets = _csv(raw["downloaded-datasheets.csv"], "downloaded-datasheets.csv")
    failures = _csv(raw["media-failures.csv"], "media-failures.csv")
    if failures: raise PlanError("El paquete de medios contiene fallos")
    review_images = [(r["source_key"], r["source_url"], r["image_order"]) for r in review["images"]]
    review_sheets = [(r["source_key"], r["source_url"], r["datasheet_order"]) for r in review["datasheets"]]
    if [(r.get("source_key"), r.get("source_url"), r.get("image_order")) for r in images] != review_images:
        raise PlanError("Asociaciones de imágenes inconsistentes")
    if [(r.get("source_key"), r.get("source_url"), r.get("datasheet_order")) for r in sheets] != review_sheets:
        raise PlanError("Asociaciones de fichas inconsistentes")
    for row, kind in [(r, "image") for r in images] + [(r, "datasheet") for r in sheets]:
        rel = safe_relative(row.get("local_file", "")); physical = next((f for f in file_rows if f.get("local_file") == rel), None)
        if not physical or row.get("sha256") != physical.get("sha256") or row.get("size_bytes") != physical.get("size_bytes") or row.get("mime_type") != physical.get("mime_type"):
            raise PlanError("Asociación no coincide con archivo deduplicado")
        if row.get("download_status") != "downloaded" or row.get("rights_status") != "operator_confirmed_for_local_download":
            raise PlanError("Asociación de medio no validada")
    summary = _json(raw["media-summary.json"], "media-summary.json")
    derived = {"products": len(review["products"]), "image_associations": len(images),
        "unique_image_urls": len({r["source_url"] for r in images}),
        "physical_image_files": sum(r.get("media_type") == "image" for r in file_rows),
        "datasheet_associations": len(sheets), "unique_datasheet_urls": len({r["source_url"] for r in sheets}),
        "physical_datasheet_files": sum(r.get("media_type") == "datasheet" for r in file_rows),
        "failures": len(failures), "products_without_datasheet": len(review["missing"])}
    if any(summary.get(k) != v for k, v in derived.items()) or any((manifest.get("counts") or {}).get(k) != v for k, v in derived.items()):
        raise PlanError("Contadores de medios inconsistentes")
    return {"manifest": manifest, "images": images, "datasheets": sheets, "files": file_rows,
        "summary": summary, "fingerprint": _sha(raw["media-manifest.json"])}


def normalize_label(value: str) -> str:
    """Normalize a structural label without altering its preserved source text."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    plain = "".join(character for character in decomposed
        if unicodedata.category(character) != "Mn")
    return " ".join(plain.casefold().split())


POWER_LABELS = {
    "fuente de potencia", "fuente de alimentacion", "power source",
    "bateria de plomo-acido", "lead-acid battery", "bateria de litio",
    "lithium battery", "tecnologia de la bateria", "battery technology",
    "voltaje nominal de la bateria", "battery nominal voltage",
    "capacidad de la bateria", "battery capacity",
}
PRIMARY_POWER_LABELS = {"fuente de potencia", "fuente de alimentacion", "power source"}


def power_evidence(specs: list[dict]) -> list[str]:
    """Return energy rows in their original order and wording."""
    return [f'{row.get("source_label", "")}: {row.get("source_value", "")}'
        for row in specs if normalize_label(row.get("source_label") or "") in POWER_LABELS]


def map_power(specs: list[dict]) -> tuple[str, str, list[str]]:
    rows = [row for row in specs
        if normalize_label(row.get("source_label") or "") in POWER_LABELS]
    evidence = power_evidence(specs)
    if not evidence:
        return "", "Fuente de energía eléctrica sin evidencia representable", evidence
    normalized = [(normalize_label(row.get("source_label") or ""),
        normalize_label(row.get("source_value") or "")) for row in rows]
    primary = [value for label, value in normalized if label in PRIMARY_POWER_LABELS]
    text = " | ".join(f"{label}: {value}" for label, value in normalized)
    lithium = bool(re.search(r"\b(litio|lithium)\b", text))
    lead = bool(re.search(r"\b(plomo-acido|lead-acid)\b", text))
    alternatives = (lead and lithium) or len(primary) > 1 or any(
        token in value for value in primary for token in (" o ", " or ", "opcional", "option", "-li"))
    if alternatives:
        return "", "Fuente de energía con varias configuraciones", evidence
    # The first voltage in each row is the system voltage; parenthesized values
    # such as 2x12V describe components of that declared system.
    voltages = set()
    for _, value in normalized:
        match = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*v\b", value)
        if match:
            voltages.add(Decimal(match.group(1).replace(",", ".")))
    if len(voltages) > 1:
        return "", "Fuente de energía con varias configuraciones", evidence
    if lithium:
        return "electric_lithium", "", evidence
    if voltages == {Decimal("24")}:
        return "electric_24v", "", evidence
    if voltages:
        displayed = ", ".join(format(value, "f").rstrip("0").rstrip(".")
            if "." in format(value, "f") else format(value, "f") for value in sorted(voltages))
        return "", f"Voltaje eléctrico confirmado ({displayed} V), sin opción equivalente en el contrato actual", evidence
    return "", "Fuente de energía no representable por el contrato actual", evidence


def map_capacity(specs: list[dict]) -> tuple[str, str]:
    values = []
    for row in specs:
        label = normalize_label(row.get("source_label") or "").replace("-", " ")
        excluded = any(word in label for word in ("aceite", "oil", "tanque", "tank", "combustible", "fuel", "bateria", "battery"))
        capacity_label = ("capacidad" in label and "plataforma" in label) or "platform capacity" in label \
            or bool(re.fullmatch(r"max\.? capacidad(?: \([^)]*\))?(?: kg(?:/lbs|/libras)?)?", label)) \
            or bool(re.fullmatch(r"capacidad (?:con|sin) restricciones(?: kg(?:/lbs|/libras)?)?", label))
        if excluded or not capacity_label: continue
        source_value = (row.get("source_value") or "").strip()
        metric_in_label = bool(re.search(r"\bkg(?:/lbs|/libras)?\b", label))
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(kg)?", source_value, re.I)
        if not match or (not match.group(2) and not metric_in_label): continue
        number = match.group(1)
        if "," in number:
            whole, fraction = number.split(",", 1)
            number = whole + fraction if len(fraction) == 3 else whole + "." + fraction
        if match:
            try: value = Decimal(number)
            except InvalidOperation: continue
            if value > 0: values.append(value)
    if values:
        value = max(values); rendered = format(value, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered, ""
    return "", "Capacidad máxima ausente o ambigua; no se convirtieron libras ni otras unidades"


def manual_actions() -> list[dict]:
    common = {"automatic": False, "requires_local_preflight": True}
    return [
        {**common, "action_type":"rename_existing_category", "current_name":"Elevador tipo tijera electrico", "target_name":"Elevadores tipo tijera eléctricos", "brand":"", "requires_exact_product_confirmation":False, "description":"Reutilizar la categoría existente; no crear un duplicado antes del preflight."},
        {**common, "action_type":"review_example_product_removal", "current_name":"", "target_name":"", "brand":"JLG", "requires_exact_product_confirmation":True, "description":"Revisar y eliminar mediante el panel de vendedor únicamente el producto JLG utilizado como ejemplo antes de aplicar la importación LGMG."},
        {**common, "action_type":"resolve_local_category_ids", "current_name":"", "target_name":"", "brand":"", "requires_exact_product_confirmation":False, "description":"Resolver raíz y siete subcategorías contra la API local."},
        {**common, "action_type":"resolve_or_create_lgmg_brand", "current_name":"", "target_name":"", "brand":"LGMG", "requires_exact_product_confirmation":False, "description":"Resolver la marca LGMG o proponer su creación durante el preflight."},
        {**common, "action_type":"review_unrepresentable_power_sources", "current_name":"", "target_name":"", "brand":"", "requires_exact_product_confirmation":False, "description":"Revisar fuentes de energía que no caben inequívocamente en el enum actual."},
        {**common, "action_type":"review_ambiguous_capacities", "current_name":"", "target_name":"", "brand":"", "requires_exact_product_confirmation":False, "description":"Revisar capacidades ausentes, múltiples o ambiguas sin convertir unidades."},
        {**common, "action_type":"accept_missing_datasheets", "current_name":"AR24JE;T38JE", "target_name":"", "brand":"", "requires_exact_product_confirmation":False, "description":"Aceptar o revisar que AR24JE y T38JE no tienen ficha técnica en la fuente."},
    ]


def build_plan(review: dict, media: dict) -> dict:
    specs_by = {key: [] for key in (p["source_key"] for p in review["products"])}
    for row in review["specs"]: specs_by[row["source_key"]].append(row)
    images_by = {key: [] for key in specs_by}; sheets_by = {key: [] for key in specs_by}
    for row in media["images"]: images_by[row["source_key"]].append(row)
    for row in media["datasheets"]: sheets_by[row["source_key"]].append(row)
    products=[]; warnings=[]; out_specs=[]; out_images=[]; out_sheets=[]
    missing_keys={r["source_key"] for r in review["missing"]}
    for product in review["products"]:
        key=product["source_key"]
        power,power_warning,electric_evidence=map_power(specs_by[key])
        capacity,capacity_warning=map_capacity(specs_by[key])
        messages=[x for x in (power_warning,capacity_warning) if x]
        if key in missing_keys: messages.append("Ficha técnica ausente en la fuente; revisión humana requerida")
        for message in messages: warnings.append({"source_key":key,"metric_model":product.get("metric_model", ""),"warning":message,"blocking_for_plan":False,"requires_human_review":True})
        name=product.get("suggested_name", "")
        products.append({"source_key":key,"source_url":product.get("source_url", ""),"proposed_name":name,
            "metric_model":product.get("metric_model", ""),"imperial_model":product.get("imperial_model", ""),
            "aliases":product.get("model_aliases", ""),"source_category":product["source_category"],
            "target_root_category":"Maquinarias","target_subcategory":dict(CATEGORY_MAPPING)[product["source_category"]],
            "target_brand":"LGMG","product_type":"machinery","condition":"new","stock_status":"on_request",
            "price":"","currency":"","show_price":False,"is_published":False,"is_featured":False,
            "includes_technical_review":False,"includes_commercial_technical_advice":False,"includes_coordinated_delivery":False,
            "target_power_source":power,"electric_evidence":electric_evidence,
            "maximum_load_capacity_kg":capacity,"datasheet_status":"missing_at_source" if key in missing_keys else "available_at_source",
            "image_count":len(images_by[key]),"warnings":messages,"eligible_for_local_preflight":True,"ready_for_import":False})
        for row in specs_by[key]: out_specs.append({**row,"maximum_load_capacity_candidate_kg":capacity if row is specs_by[key][0] else ""})
        for index,row in enumerate(images_by[key],1): out_images.append({"source_key":key,"metric_model":product.get("metric_model", ""),
            "image_order":index,"source_url":row["source_url"],"local_file":row["local_file"],"sha256":row["sha256"],
            "size_bytes":row["size_bytes"],"mime_type":row["mime_type"],"primary_candidate":index==1,
            "proposed_alt":f"{name} — imagen {index}","alt_status":"proposal_requires_review"})
        if key in missing_keys: out_sheets.append({"source_key":key,"metric_model":product.get("metric_model", ""),"datasheet_order":"",
            "source_url":"","local_file":"","sha256":"","size_bytes":"","mime_type":"","datasheet_status":"missing_at_source",
            "blocking_for_plan":False,"requires_human_review":True})
        else:
            for index,row in enumerate(sheets_by[key],1): out_sheets.append({"source_key":key,"metric_model":product.get("metric_model", ""),
                "datasheet_order":index,"source_url":row["source_url"],"local_file":row["local_file"],"sha256":row["sha256"],
                "size_bytes":row["size_bytes"],"mime_type":row["mime_type"],"datasheet_status":"available_at_source",
                "blocking_for_plan":False,"requires_human_review":False})
    categories=[{"expected_root":"Maquinarias","source_category":source,"target_name":target,
        "known_existing_alias":"Elevador tipo tijera electrico" if source=="Elevadores de Tijera" else "",
        "resolution_required":True,"automatic_creation_enabled":False} for source,target in CATEGORY_MAPPING]
    summary={"products":len(products),"specifications":len(out_specs),"image_associations":len(out_images),
        "datasheet_associations":len(review["datasheets"]),"products_without_datasheets":len(missing_keys),
        "classification_uncertain_excluded":len(review["uncertain"]),"target_categories":7,"warnings":len(warnings),
        "eligible_for_local_preflight":len(products),"ready_for_import":False,**EFFECTS}
    return {"products":products,"specifications":out_specs,"images":out_images,"datasheets":out_sheets,
        "categories":categories,"brand":[{"name":"LGMG","id":"","resolution_required":True,"create_if_missing":"pending_local_preflight"}],
        "warnings":warnings,"manual_actions":manual_actions(),"summary":summary}


def _excel(value):
    if value is None: return ""
    if isinstance(value,bool): return str(value).lower()
    if isinstance(value,(list,dict)): value=json.dumps(value,ensure_ascii=False,separators=(",",":"),sort_keys=True)
    text=str(value)
    return "'"+text if text.lstrip().startswith(("=","+","-","@")) else text


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    out=io.StringIO(newline=""); writer=csv.DictWriter(out,fields,extrasaction="ignore",lineterminator="\r\n")
    writer.writeheader(); writer.writerows({key:_excel(row.get(key)) for key in fields} for row in rows)
    path.write_bytes(b"\xef\xbb\xbf"+out.getvalue().encode("utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")


def combined_fingerprint(review_fp: str, media_fp: str, selected: dict[str, bytes]) -> str:
    digest=hashlib.sha256()
    for value in (review_fp,media_fp,MAPPING_VERSION): digest.update(value.encode()); digest.update(b"\0")
    for name in sorted(selected): digest.update(name.encode()); digest.update(b"\0"); digest.update(_sha(selected[name]).encode()); digest.update(b"\0")
    return digest.hexdigest()


def write_plan(staging: Path, plan: dict, review: dict, media: dict, selected: dict[str, bytes], created_at: str) -> None:
    field_map={
        "import-products.csv":list(plan["products"][0]) if plan["products"] else [],
        "import-specifications.csv":"source_key metric_model group_order group_name specification_order source_label source_value normalized_label normalized_value unit requires_review maximum_load_capacity_candidate_kg".split(),
        "import-images.csv":"source_key metric_model image_order source_url local_file sha256 size_bytes mime_type primary_candidate proposed_alt alt_status".split(),
        "import-datasheets.csv":"source_key metric_model datasheet_order source_url local_file sha256 size_bytes mime_type datasheet_status blocking_for_plan requires_human_review".split(),
        "import-categories.csv":"expected_root source_category target_name known_existing_alias resolution_required automatic_creation_enabled".split(),
        "import-brand.csv":"name id resolution_required create_if_missing".split(),
        "import-warnings.csv":"source_key metric_model warning blocking_for_plan requires_human_review".split(),
        "manual-actions.csv":"action_type current_name target_name brand automatic requires_local_preflight requires_exact_product_confirmation description".split(),
    }
    row_map={"import-products.csv":plan["products"],"import-specifications.csv":plan["specifications"],"import-images.csv":plan["images"],
        "import-datasheets.csv":plan["datasheets"],"import-categories.csv":plan["categories"],"import-brand.csv":plan["brand"],
        "import-warnings.csv":plan["warnings"],"manual-actions.csv":plan["manual_actions"]}
    for name,fields in field_map.items(): _write_csv(staging/name,fields,row_map[name])
    fp=combined_fingerprint(review["fingerprint"],media["fingerprint"],selected)
    document={"tool":TOOL_NAME,"version":TOOL_VERSION,"mapping_version":MAPPING_VERSION,"combined_fingerprint_sha256":fp,
        "products":plan["products"],"categories":plan["categories"],"brand":plan["brand"][0],"manual_actions":plan["manual_actions"],
        "effects":EFFECTS,"eligible_for_local_preflight":True,"ready_for_import":False,"content_published":False}
    _write_json(staging/"import-plan.json",document); _write_json(staging/"import-summary.json",plan["summary"])
    (staging/"import-summary.txt").write_text("\n".join(f"{k}: {str(v).lower() if isinstance(v,bool) else v}" for k,v in plan["summary"].items())+"\n",encoding="utf-8",newline="\n")
    (staging/"README-import-plan.txt").write_text("PLAN OFFLINE LGMG PARA JEM NEXUS\n\nEste paquete no importa ni publica. Conserva referencias relativas a media-package; no copia imágenes ni PDF. Debe validarse en un preflight local antes de cualquier aplicación.\n",encoding="utf-8",newline="\n")
    files=[]
    for name in OUTPUTS:
        data=(staging/name).read_bytes(); files.append({"name":name,"size":len(data),"sha256":_sha(data)})
    manifest={"tool":TOOL_NAME,"version":TOOL_VERSION,"created_at_utc":created_at,
        "review_fingerprint_sha256":review["fingerprint"],"media_fingerprint_sha256":media["fingerprint"],
        "combined_fingerprint_sha256":fp,"generated_files":files,"counts":plan["summary"],
        "target_categories":[target for _,target in CATEGORY_MAPPING],"target_brand":"LGMG",**EFFECTS,
        "network_used":False,"files_copied":False,"ready_for_import":False,"content_published":False}
    _write_json(staging/"import-manifest.json",manifest)


def _safe_paths(review: Path, media: Path, output: Path) -> None:
    resolved=[review.resolve(),media.resolve(),output.resolve(strict=False)]
    if len(set(resolved)) != 3: raise PlanError("Entradas y salida deben ser distintas")
    out=resolved[2]
    if len(out.parts)<3 or out in (Path(out.anchor),Path.home().resolve()): raise PlanError("Salida demasiado amplia")
    for inp in resolved[:2]:
        if inp in out.parents or out in inp.parents: raise PlanError("Entradas y salida no pueden contenerse")
    current=out
    while not current.exists() and current!=current.parent: current=current.parent
    if current.is_symlink() or (output.exists() and output.is_symlink()): raise PlanError("Salida mediante symlink")
    if output.exists() and (not output.is_dir() or any(output.iterdir())): raise PlanError("La salida debe estar vacía")


def run(review_path: Path, media_path: Path, output: Path, *, created_at: str | None=None) -> None:
    _safe_paths(review_path,media_path,output)
    review_raw,_=read_review(review_path); review=validate_review(review_raw)
    media_root,media_raw=read_media(media_path); media=validate_media(media_root,media_raw,review)
    selected={**{f"review/{k}":v for k,v in review_raw.items()},**{f"media/{k}":v for k,v in media_raw.items()}}
    plan=build_plan(review,media); output.mkdir(parents=True,exist_ok=True); staging=output/".staging"
    try:
        staging.mkdir()
        write_plan(staging,plan,review,media,selected,created_at or datetime.now(timezone.utc).isoformat())
        if set(p.name for p in staging.iterdir()) != set(OUTPUTS)|{"import-manifest.json"}: raise PlanError("Conjunto de salidas incompleto")
        for item in staging.iterdir(): os.replace(item,output/item.name)
        staging.rmdir()
    except Exception:
        if staging.exists():
            for item in staging.iterdir():
                if item.is_file(): item.unlink()
            staging.rmdir()
        if output.exists() and not any(output.iterdir()): output.rmdir()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="Genera un plan offline LGMG para JEM Nexus")
    parser.add_argument("--review-input",required=True); parser.add_argument("--media-input",required=True); parser.add_argument("--output-dir",required=True)
    return parser


def main(argv=None) -> int:
    try:
        args=build_parser().parse_args(argv)
        run(Path(args.review_input),Path(args.media_input),Path(args.output_dir)); return 0
    except (PlanError,OSError,zipfile.BadZipFile) as exc:
        message=re.sub(r"(?:[A-Za-z]:)?[/\\][^\n:]+","ruta",str(exc).splitlines()[0])[:200]
        print("Error: "+message,file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
