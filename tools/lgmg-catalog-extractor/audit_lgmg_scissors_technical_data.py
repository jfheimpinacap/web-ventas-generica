#!/usr/bin/env python3
"""Audita, sin red ni escrituras externas, datos técnicos LGMG locales."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import unicodedata

TOOL_NAME = "audit_lgmg_scissors_technical_data"
TOOL_VERSION = "1.0.0"
PLAN_TOOL = "lgmg-jem-import-plan-generator"
MEDIA_TOOL = "lgmg-jem-review-media-downloader"
PLAN_VERSION = MEDIA_VERSION = "1.0.0"
SOURCE_CATEGORY = "Elevadores de Tijera"
OUTPUT_NAMES = (
    "technical-audit-products.csv", "technical-audit-field-candidates.csv",
    "technical-audit-specifications.csv", "technical-audit-datasheets.csv",
    "technical-audit-warnings.csv", "technical-audit-summary.json",
    "technical-audit-summary.txt", "technical-audit-manifest.json",
    "README-technical-audit.txt",
)
PLAN_FILES = (
    "import-products.csv", "import-specifications.csv", "import-images.csv",
    "import-datasheets.csv", "import-categories.csv", "import-brand.csv",
    "import-warnings.csv", "manual-actions.csv", "import-plan.json",
    "import-summary.json", "import-summary.txt", "README-import-plan.txt",
)
MEDIA_REPORTS = (
    "media-files.csv", "downloaded-images.csv", "downloaded-datasheets.csv",
    "media-failures.csv", "media-summary.json",
)
EXPECTED_COUNTS = {"import-products.csv": 57, "import-specifications.csv": 1635,
    "import-images.csv": 127, "import-datasheets.csv": 57,
    "import-categories.csv": 7, "import-brand.csv": 1,
    "import-warnings.csv": 44, "manual-actions.csv": 7}
PRODUCT_FIELDS = {"source_key", "metric_model", "source_category", "target_power_source",
    "maximum_load_capacity_kg", "ready_for_import", "is_published", "is_featured", "show_price"}
EFFECTS = {"network_used": False, "api_called": False, "database_modified": False,
    "input_files_modified": False, "files_copied": False, "products_created": 0,
    "products_updated": 0, "products_deleted": 0, "specifications_created": 0,
    "datasheets_uploaded": 0, "content_published": False, "apply_supported": False,
    "ready_for_update": False, "human_review_required": True}
WORKING_HEIGHT_LABELS = {"altura maxima de trabajo", "maximum working height", "max. working height"}
MACHINE_WEIGHT_LABELS = {"peso de la maquina", "machine weight", "peso total de la maquina", "overall machine weight"}
TERRAIN_VALUES = {"interior liso": "indoor_smooth", "indoor smooth": "indoor_smooth",
    "exterior": "outdoor", "outdoor": "outdoor",
    "exterior pendientes y rampas": "outdoor_slopes_and_ramps",
    "outdoor slopes and ramps": "outdoor_slopes_and_ramps"}
YEAR_LABELS = {"ano de fabricacion", "manufacturing year", "year of manufacture"}


class AuditError(ValueError):
    """Fallo controlado, sin revelar contenido o rutas completas."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


def safe_relative(value) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or
            re.match(r"^[A-Za-z]:", value) or any(ord(c) < 32 for c in value)):
        raise AuditError("Ruta relativa inválida")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in path.parts) or path.as_posix() != value:
        raise AuditError("Ruta relativa no canónica o traversal")
    return value


def read_regular(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise AuditError(f"Archivo obligatorio ausente o inseguro: {label}")
    return path.read_bytes()


def csv_rows(data: bytes, label: str) -> list[dict[str, str]]:
    try:
        return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except (UnicodeError, csv.Error) as exc:
        raise AuditError(f"CSV inválido: {label}") from exc


def json_value(data: bytes, label: str):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"JSON inválido: {label}") from exc


def _literal_assignment(path: Path, name: str):
    """Lee una constante literal del código existente sin ejecutar ese módulo."""
    tree = ast.parse(read_regular(path, path.name).decode("utf-8"), filename=path.name)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "dict":
                value = value.args[0]
            return ast.literal_eval(value)
    raise AuditError(f"No se encontró la tabla cerrada {name}")


def closed_catalog(tool_dir: Path | None = None):
    root = tool_dir or Path(__file__).resolve().parent
    pairs = tuple(_literal_assignment(root / "import_lgmg_scissors_minimal.py", "MODEL_SOURCE_KEYS"))
    targets = dict(_literal_assignment(root / "canonicalize_lgmg_scissors_catalog.py", "SOURCE_TARGET_MODELS"))
    if len(pairs) != 21 or len(set(pairs)) != 21 or len({m for m, _ in pairs}) != 21 or len({k for _, k in pairs}) != 21:
        raise AuditError("La selección cerrada no contiene 21 asociaciones únicas")
    if tuple(m for m, _ in pairs) != tuple(targets) or any(m not in targets for m, _ in pairs):
        raise AuditError("Las tablas cerradas de importación y canonización no coinciden")
    return tuple({"catalog_order": i, "source_model": model, "source_key": key,
        "target_model": targets[model], "target_name": f"Elevador tipo tijera eléctrico LGMG {targets[model]}"}
        for i, (model, key) in enumerate(pairs, 1))


def safe_paths(plan: Path, media: Path, output: Path):
    for item in (plan, media):
        if item.is_symlink() or not item.is_dir(): raise AuditError("Las entradas deben ser carpetas físicas seguras")
    resolved = plan.resolve(), media.resolve(), output.resolve(strict=False)
    if len(set(resolved)) != 3: raise AuditError("Entradas y salida deben ser distintas")
    if any(resolved[2] in p.parents or p in resolved[2].parents for p in resolved[:2]):
        raise AuditError("Entradas y salida no pueden contenerse")
    current = resolved[2]
    while not current.exists() and current != current.parent: current = current.parent
    if current.is_symlink() or (output.exists() and output.is_symlink()): raise AuditError("Salida mediante symlink")
    if output.exists() and (not output.is_dir() or any(output.iterdir())): raise AuditError("La salida debe ser nueva o vacía")


def validate_inputs(plan_root: Path, media_root: Path):
    plan_raw = {n: read_regular(plan_root / n, n) for n in (*PLAN_FILES, "import-manifest.json")}
    pm = json_value(plan_raw["import-manifest.json"], "import-manifest.json")
    if pm.get("tool") != PLAN_TOOL or pm.get("version") != PLAN_VERSION: raise AuditError("Manifest de plan no admitido")
    declared = {x.get("name"): x for x in pm.get("generated_files", []) if isinstance(x, dict)}
    if set(declared) != set(PLAN_FILES): raise AuditError("Conjunto cerrado del plan inconsistente")
    for name in PLAN_FILES:
        if declared[name].get("size") != len(plan_raw[name]) or declared[name].get("sha256") != sha(plan_raw[name]):
            raise AuditError(f"Hash o tamaño del plan inconsistente: {name}")
    if any(pm.get(k) is not False for k in ("ready_for_import", "content_published", "network_used")):
        raise AuditError("Estado conservador del plan incumplido")
    rows = {n: csv_rows(plan_raw[n], n) for n in PLAN_FILES if n.endswith(".csv")}
    if any(len(rows[n]) != count for n, count in EXPECTED_COUNTS.items()): raise AuditError("Conteos aprobados del plan incumplidos")
    products = rows["import-products.csv"]
    if not products or not PRODUCT_FIELDS.issubset(products[0]): raise AuditError("Esquema de productos incompleto")
    if any(r.get("ready_for_import", "").casefold() != "false" or r.get("is_published", "").casefold() != "false" or
           r.get("is_featured", "").casefold() != "false" or r.get("show_price", "").casefold() != "false" for r in products):
        raise AuditError("Estado conservador de productos incumplido")
    document = json_value(plan_raw["import-plan.json"], "import-plan.json")
    if document.get("combined_fingerprint_sha256") != pm.get("combined_fingerprint_sha256") or document.get("ready_for_import") is not False or document.get("content_published") is not False:
        raise AuditError("Fingerprint o estado del plan inconsistente")

    media_raw = {n: read_regular(media_root / n, n) for n in (*MEDIA_REPORTS, "media-manifest.json")}
    mm = json_value(media_raw["media-manifest.json"], "media-manifest.json")
    if mm.get("tool") != MEDIA_TOOL or mm.get("version") != MEDIA_VERSION: raise AuditError("Manifest de medios no admitido")
    required = {"jem_nexus_called": False, "products_imported": 0, "content_published": False,
        "all_products_ready_for_import": False, "package_complete": True}
    if any(mm.get(k) != v for k, v in required.items()): raise AuditError("Estado conservador de medios incumplido")
    if pm.get("media_fingerprint_sha256") != sha(media_raw["media-manifest.json"]): raise AuditError("Fingerprint cruzado de medios incorrecto")
    files = {}
    for item in mm.get("files", []):
        name = safe_relative(item.get("name", ""))
        if name in files: raise AuditError("Ruta de medio declarada duplicada")
        files[name] = item
    actual = set()
    for item in media_root.rglob("*"):
        if item.is_symlink(): raise AuditError("Symlink detectado en medios")
        if item.is_file(): actual.add(item.relative_to(media_root).as_posix())
        elif not item.is_dir(): raise AuditError("Tipo especial detectado en medios")
    if actual != set(files) | {"media-manifest.json"}: raise AuditError("Conjunto cerrado de medios inconsistente")
    for name, item in files.items():
        data = read_regular(media_root.joinpath(*PurePosixPath(name).parts), name)
        if item.get("size") != len(data) or item.get("sha256") != sha(data): raise AuditError("Hash físico de medio inconsistente")
    media_rows = {n: csv_rows(media_raw[n], n) for n in MEDIA_REPORTS if n.endswith(".csv")}
    if media_rows["media-failures.csv"]: raise AuditError("El paquete de medios contiene fallos")
    return {"manifest": pm, "rows": rows}, {"manifest": mm, "rows": media_rows, "files": files}


def select_products(products, catalog=None):
    catalog = catalog or closed_catalog()
    by_pair, seen_keys = {}, set()
    for row in products:
        key = row.get("source_key", ""); model = row.get("metric_model", "")
        if key in seen_keys: raise AuditError("source_key duplicado en el plan")
        seen_keys.add(key); by_pair.setdefault((model, key), []).append(row)
    selected = []
    for approved in catalog:
        matches = by_pair.get((approved["source_model"], approved["source_key"]), [])
        if len(matches) != 1: raise AuditError("Modelo faltante, duplicado o asociación ambigua")
        row = matches[0]
        if row.get("source_category") != SOURCE_CATEGORY: raise AuditError("Familia fuente incorrecta")
        selected.append({**approved, **row, "source_model": approved["source_model"], "target_model": approved["target_model"], "target_name": approved["target_name"]})
    return selected


def metric_number(value: str, unit: str):
    text = str(value or "").strip(); declared = str(unit or "").strip().casefold()
    if re.search(r"\b(ft|feet|foot|lbs?|pounds?)\b", text, re.I): return None
    match = re.fullmatch(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*(m|kg)?\s*", text, re.I)
    if not match: return None
    found = (match.group(2) or declared).casefold()
    if found != unit.casefold(): return None
    try: number = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation: return None
    if number <= 0: return None
    rendered = format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def evidence(specs, labels, unit, field, rule):
    matches = []
    for row in specs:
        if normalized(row.get("source_label")) in labels:
            value = metric_number(row.get("source_value", ""), unit)
            if value: matches.append((value, row))
    unique = {v for v, _ in matches}
    if len(unique) == 1:
        return next(iter(unique)), "safe_candidate", [(r, next(iter(unique)), rule) for _, r in matches]
    return "", "manual_review", [(r, "", rule + ("_ambiguous" if matches else "_absent")) for _, r in matches]


def capacity_evidence(specs, expected):
    """Reproduce las etiquetas/unidades conservadoras de map_capacity."""
    matches = []
    for row in specs:
        label = normalized(row.get("source_label")).replace("-", " ")
        excluded = any(word in label for word in ("aceite", "oil", "tanque", "tank", "combustible", "fuel", "bateria", "battery"))
        accepted = (("capacidad" in label and "plataforma" in label) or "platform capacity" in label or
            bool(re.fullmatch(r"max\.? capacidad(?: \([^)]*\))?(?: kg(?:/lbs|/libras)?)?", label)) or
            bool(re.fullmatch(r"capacidad (?:con|sin) restricciones(?: kg(?:/lbs|/libras)?)?", label)))
        if excluded or not accepted: continue
        source = row.get("source_value", "").strip()
        metric_label = bool(re.search(r"\bkg(?:/lbs|/libras)?\b", label))
        found = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(kg)?", source, re.I)
        if not found or (not found.group(2) and not metric_label): continue
        number = found.group(1)
        if "," in number:
            whole, fraction = number.split(",", 1); number = whole + fraction if len(fraction) == 3 else whole + "." + fraction
        try: value = Decimal(number)
        except InvalidOperation: continue
        if value > 0: matches.append((value, row))
    if not matches: return []
    maximum = max(value for value, _ in matches); rendered = format(maximum, "f")
    rendered = rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    return [row for value, row in matches if value == maximum] if rendered == expected else []


def field_analysis(product, specs):
    result, rows, warnings = {}, [], []
    for field, labels, unit, rule in (
        ("WorkingHeightM", WORKING_HEIGHT_LABELS, "m", "explicit_working_height_metric"),
        ("MachineWeightKg", MACHINE_WEIGHT_LABELS, "kg", "explicit_machine_weight_metric")):
        value, status, evidence_rows = evidence(specs, labels, unit, field, rule)
        result[field] = (value, status)
        for source, candidate, mapping in evidence_rows:
            rows.append(candidate_row(product, field, candidate, unit, status, source, mapping))
        if status != "safe_candidate": warnings.append((field, "Campo ausente o ambiguo"))
    capacity = product.get("maximum_load_capacity_kg", "")
    cap_specs = capacity_evidence(specs, capacity)
    cap_status = "safe_candidate" if capacity and cap_specs else "manual_review"
    result["MaximumLoadCapacityKg"] = (capacity if cap_status == "safe_candidate" else "", cap_status)
    for source in cap_specs: rows.append(candidate_row(product, "MaximumLoadCapacityKg", capacity, "kg", cap_status, source, "existing_conservative_plan_derivation"))
    if cap_status != "safe_candidate": warnings.append(("MaximumLoadCapacityKg", "Derivación ausente o sin evidencia"))
    power = product.get("target_power_source", "")
    power_specs = [s for s in specs if normalized(s.get("source_label")) in {
        "fuente de potencia", "fuente de alimentacion", "power source", "bateria de plomo-acido",
        "lead-acid battery", "bateria de litio", "lithium battery", "tecnologia de la bateria", "battery technology"}]
    power_status = "representable_candidate" if power in ("electric_24v", "electric_lithium") and power_specs else "manual_review"
    result["PowerSource"] = (power if power_status == "representable_candidate" else "", power_status)
    for source in power_specs: rows.append(candidate_row(product, "PowerSource", result["PowerSource"][0], "", power_status, source, "existing_conservative_plan_derivation"))
    if power_status != "representable_candidate": warnings.append(("PowerSource", "Configuración ausente, ambigua o no representable"))
    terrain_specs = [(TERRAIN_VALUES.get(normalized(s.get("source_value"))), s) for s in specs if normalized(s.get("source_label")) in {"tipo de terreno", "terrain type"}]
    terrain_values = {v for v, _ in terrain_specs if v}
    terrain = next(iter(terrain_values)) if len(terrain_values) == 1 else ""
    terrain_status = "safe_candidate" if terrain else "manual_review"; result["TerrainType"] = terrain, terrain_status
    for _, source in terrain_specs: rows.append(candidate_row(product, "TerrainType", terrain, "", terrain_status, source, "explicit_terrain_enum_equivalence"))
    if not terrain: warnings.append(("TerrainType", "No se infiere por familia o modelo"))
    year_specs = [s for s in specs if normalized(s.get("source_label")) in YEAR_LABELS and re.fullmatch(r"(?:19|20)\d{2}", s.get("source_value", "").strip())]
    years = {s["source_value"].strip() for s in year_specs}; year = next(iter(years)) if len(years) == 1 else ""
    result["Year"] = year, "safe_candidate" if year else "not_provided"
    for source in year_specs: rows.append(candidate_row(product, "Year", year, "", result["Year"][1], source, "explicit_manufacturing_year"))
    result["HoursMeter"] = "", "not_provided_not_applicable"
    rows.append(candidate_row(product, "HoursMeter", "", "h", "not_provided_not_applicable", None, "new_products_audit_no_source_evidence"))
    result["TechnicalSheetId"] = "", "not_checked_offline"
    return result, rows, warnings


def candidate_row(product, field, value, unit, status, source, rule):
    source = source or {}
    return {"source_key": product["source_key"], "source_model": product["source_model"],
        "target_model": product["target_model"], "target_field": field, "candidate_value": value,
        "unit": unit, "status": status, "source_label": source.get("source_label", ""),
        "source_value": source.get("source_value", ""), "specification_order": source.get("specification_order", ""),
        "mapping_rule": rule, "requires_human_review": True}


def validate_datasheets(selected, plan, media, media_root):
    keys = {p["source_key"]: p for p in selected}; associations = []
    file_rows = {r.get("local_file"): r for r in media["rows"]["media-files.csv"]}
    downloaded = {(r.get("source_key"), r.get("datasheet_order")): r for r in media["rows"]["downloaded-datasheets.csv"]}
    for row in plan["rows"]["import-datasheets.csv"]:
        if row.get("source_key") not in keys: continue
        product = keys[row["source_key"]]
        if row.get("metric_model") != product["source_model"]: raise AuditError("Modelo de ficha inconsistente")
        if row.get("datasheet_status") == "missing_at_source": continue
        rel = safe_relative(row.get("local_file", "")); physical = media_root.joinpath(*PurePosixPath(rel).parts)
        if physical.is_symlink() or not physical.is_file(): raise AuditError("PDF físico ausente o inseguro")
        data = physical.read_bytes(); physical_row = file_rows.get(rel); downloaded_row = downloaded.get((row["source_key"], row.get("datasheet_order")))
        if not physical_row or not downloaded_row: raise AuditError("Asociación de ficha ausente en medios")
        if any(str(item.get("sha256")) != sha(data) or str(item.get("size_bytes")) != str(len(data)) or item.get("mime_type") != "application/pdf" for item in (row, physical_row, downloaded_row)):
            raise AuditError("Hash, tamaño o MIME de PDF inconsistente")
        if not data.startswith(b"%PDF-"): raise AuditError("Firma física PDF inválida")
        associations.append({"catalog_order": product["catalog_order"], "source_key": row["source_key"],
            "source_model": product["source_model"], "target_model": product["target_model"],
            "datasheet_order": row.get("datasheet_order", ""), "relative_path": rel,
            "file_name": PurePosixPath(rel).name, "sha256": sha(data), "size_bytes": len(data),
            "mime_type": "application/pdf", "physical_file_validated": True,
            "source_pdf_available": True, "jem_nexus_assignment_status": "not_checked_offline"})
    counts = {}
    for row in associations: counts[row["sha256"]] = counts.get(row["sha256"], set()) | {row["source_key"]}
    for row in associations: row["products_sharing_physical_file"] = len(counts[row["sha256"]])
    return associations


def excel(value):
    if value is None: return ""
    if isinstance(value, bool): return str(value).lower()
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_csv(path, fields, rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fields, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader(); writer.writerows({f: excel(row.get(f, "")) for f in fields} for row in rows)
    path.write_bytes(b"\xef\xbb\xbf" + output.getvalue().encode("utf-8"))


def build_audit(plan, media, media_root):
    selected = select_products(plan["rows"]["import-products.csv"])
    by_key = {p["source_key"]: [] for p in selected}
    for spec in plan["rows"]["import-specifications.csv"]:
        if spec.get("source_key") in by_key: by_key[spec["source_key"]].append(spec)
    sheets = validate_datasheets(selected, plan, media, media_root)
    sheet_by_key = {p["source_key"]: [] for p in selected}
    for row in sheets: sheet_by_key[row["source_key"]].append(row)
    products, candidates, specifications, warnings = [], [], [], []
    for product in selected:
        specs = by_key[product["source_key"]]; fields, field_rows, field_warnings = field_analysis(product, specs)
        candidates.extend(field_rows)
        evidence_orders = {(r["target_field"], r["specification_order"]) for r in field_rows if r["specification_order"]}
        seen = set()
        for spec in specs:
            identity = (spec.get("source_label"), spec.get("source_value"), spec.get("unit"))
            direct = any(order == spec.get("specification_order") for _, order in evidence_orders)
            classification = "duplicate_evidence" if identity in seen else ("direct_product_field_candidate" if direct else ("manual_review" if spec.get("requires_review", "").casefold() == "true" else "additional_product_spec"))
            seen.add(identity)
            specifications.append({"source_key": product["source_key"], "source_model": product["source_model"],
                "target_model": product["target_model"], "specification_order": spec.get("specification_order", ""),
                "source_group_order": spec.get("group_order", ""), "source_group": spec.get("group_name", ""),
                "source_label": spec.get("source_label", ""), "source_value": spec.get("source_value", ""),
                "unit": spec.get("unit", ""), "review_status": classification})
        for field, message in field_warnings:
            warnings.append({"source_key": product["source_key"], "source_model": product["source_model"],
                "target_field": field, "warning": message, "requires_human_review": True})
        extra = sum(r["review_status"] == "additional_product_spec" for r in specifications if r["source_key"] == product["source_key"])
        product_sheets = sheet_by_key[product["source_key"]]
        products.append({"catalog_order": product["catalog_order"], "source_key": product["source_key"],
            "source_model": product["source_model"], "target_model": product["target_model"], "target_name": product["target_name"],
            "source_category": SOURCE_CATEGORY, "specification_count": len(specs),
            "datasheet_association_count": len(product_sheets), "physical_datasheet_count": len({s["sha256"] for s in product_sheets}),
            "working_height_m_candidate": fields["WorkingHeightM"][0], "working_height_status": fields["WorkingHeightM"][1],
            "maximum_load_capacity_kg_candidate": fields["MaximumLoadCapacityKg"][0], "maximum_load_capacity_status": fields["MaximumLoadCapacityKg"][1],
            "machine_weight_kg_candidate": fields["MachineWeightKg"][0], "machine_weight_status": fields["MachineWeightKg"][1],
            "power_source_candidate": fields["PowerSource"][0], "power_source_status": fields["PowerSource"][1],
            "terrain_type_candidate": fields["TerrainType"][0], "terrain_type_status": fields["TerrainType"][1],
            "year_candidate": fields["Year"][0], "year_status": fields["Year"][1],
            "hours_meter_candidate": "", "hours_meter_status": fields["HoursMeter"][1],
            "additional_specification_count": extra, "warning_count": len(field_warnings),
            "requires_human_review": True, "ready_for_update": False})
    summary = {"status": "AUDIT_COMPLETE", "products_audited": len(products),
        "specifications_audited": len(specifications), "datasheet_associations": len(sheets),
        "unique_physical_pdfs": len({r["sha256"] for r in sheets}),
        "products_with_datasheet": sum(bool(sheet_by_key[p["source_key"]]) for p in selected),
        "products_without_datasheet": sum(not sheet_by_key[p["source_key"]] for p in selected),
        "safe_working_height_candidates": sum(bool(p["working_height_m_candidate"]) for p in products),
        "safe_maximum_load_capacity_candidates": sum(bool(p["maximum_load_capacity_kg_candidate"]) for p in products),
        "safe_machine_weight_candidates": sum(bool(p["machine_weight_kg_candidate"]) for p in products),
        "representable_power_source_candidates": sum(bool(p["power_source_candidate"]) for p in products),
        "safe_terrain_type_candidates": sum(bool(p["terrain_type_candidate"]) for p in products),
        "fields_requiring_review": sum(p["warning_count"] for p in products), "warnings": len(warnings),
        "products_ready_for_update": 0, "human_review_required": True, "ready_for_update": False}
    return products, candidates, specifications, sheets, warnings, summary


def write_outputs(output, audit, plan_fp, media_fp, created_at):
    products, candidates, specs, sheets, warnings, summary = audit
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".technical-audit-", dir=output))
    try:
        write_csv(staging / OUTPUT_NAMES[0], list(products[0]), products)
        write_csv(staging / OUTPUT_NAMES[1], "source_key source_model target_model target_field candidate_value unit status source_label source_value specification_order mapping_rule requires_human_review".split(), candidates)
        write_csv(staging / OUTPUT_NAMES[2], "source_key source_model target_model specification_order source_group_order source_group source_label source_value unit review_status".split(), specs)
        write_csv(staging / OUTPUT_NAMES[3], "catalog_order source_key source_model target_model datasheet_order relative_path file_name sha256 size_bytes mime_type physical_file_validated products_sharing_physical_file source_pdf_available jem_nexus_assignment_status".split(), sheets)
        write_csv(staging / OUTPUT_NAMES[4], "source_key source_model target_field warning requires_human_review".split(), warnings)
        (staging / OUTPUT_NAMES[5]).write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[6]).write_text("\n".join(f"{k}: {str(v).lower() if isinstance(v, bool) else v}" for k, v in summary.items()) + "\n", encoding="utf-8")
        manifest = {"tool": TOOL_NAME, "version": TOOL_VERSION, "created_at_utc": created_at,
            "plan_fingerprint_sha256": plan_fp, "media_fingerprint_sha256": media_fp,
            "status": "AUDIT_COMPLETE", "generated_files": list(OUTPUT_NAMES), **EFFECTS}
        (staging / OUTPUT_NAMES[7]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (staging / OUTPUT_NAMES[8]).write_text("AUDITORÍA TÉCNICA OFFLINE LGMG\n\nNueve informes para revisión humana. No copia ni sube PDF, no consulta JEM Nexus y no autoriza publicación comercial.\n", encoding="utf-8")
        if {p.name for p in staging.iterdir()} != set(OUTPUT_NAMES): raise AuditError("Conjunto de salidas incompleto")
        for name in OUTPUT_NAMES: os.replace(staging / name, output / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def run(plan_input: Path, media_input: Path, output: Path, *, created_at=None):
    safe_paths(plan_input, media_input, output)
    try:
        plan, media = validate_inputs(plan_input, media_input)
        audit = build_audit(plan, media, media_input)
        write_outputs(output, audit, plan["manifest"]["combined_fingerprint_sha256"], sha((media_input / "media-manifest.json").read_bytes()), created_at or datetime.now(timezone.utc).isoformat())
    except Exception:
        if output.exists() and output.is_dir():
            for item in output.iterdir():
                if item.is_file(): item.unlink()
                elif item.is_dir(): shutil.rmtree(item)
            output.rmdir()
        raise


def build_parser():
    parser = argparse.ArgumentParser(description="Auditoría técnica offline de 21 tijeras LGMG")
    parser.add_argument("--plan-input", required=True); parser.add_argument("--media-input", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        run(Path(args.plan_input), Path(args.media_input), Path(args.output_dir)); return 0
    except (AuditError, OSError) as exc:
        message = re.sub(r"(?:[A-Za-z]:)?[/\\][^\n:]+", "ruta", str(exc).splitlines()[0])[:200]
        print("Error: " + message, file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
