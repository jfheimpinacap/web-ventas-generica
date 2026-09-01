#!/usr/bin/env python3
"""Produce a read-only, offline approval catalogue for the remaining LGMG plan."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile

TOOL_NAME = "audit_lgmg_remaining_catalog"
TOOL_VERSION = "1.0.0"
PLAN_TOOL = "lgmg-jem-import-plan-generator"
MEDIA_TOOL = "lgmg-jem-review-media-downloader"
PACKAGE_VERSION = "1.0.0"
APPROVED_PLAN_FINGERPRINT = "75d68378dcd7bf77b19f9c7f0e60806085deaecadf2b7fa70e3102812be4bcb7"
APPROVED_MEDIA_FINGERPRINT = "b16d7f40250cc9b7a1b4affe029d0a87bba4355968e289fdab99ddbb4d656c9b"
PLAN_FILES = ("import-products.csv", "import-specifications.csv", "import-images.csv",
    "import-datasheets.csv", "import-categories.csv", "import-brand.csv", "import-warnings.csv",
    "manual-actions.csv", "import-plan.json", "import-summary.json", "import-summary.txt",
    "README-import-plan.txt")
MEDIA_REPORTS = ("media-files.csv", "downloaded-images.csv", "downloaded-datasheets.csv",
    "media-failures.csv", "media-summary.json")
EXPECTED_COUNTS = {"import-products.csv": 57, "import-specifications.csv": 1635,
    "import-images.csv": 127, "import-datasheets.csv": 57, "import-categories.csv": 7,
    "import-brand.csv": 1, "import-warnings.csv": 44, "manual-actions.csv": 7}
OUTPUT_NAMES = ("remaining-catalog-scope.csv", "remaining-products-for-approval.csv",
    "remaining-families.csv", "remaining-media.csv", "remaining-conflicts.csv",
    "remaining-summary.json", "remaining-summary.txt", "remaining-manifest.json",
    "README-remaining-audit.txt")
FAMILIES = {
    "Elevador Eléctrico RT de Tijera": ("Elevadores tipo tijera todoterreno", "Elevador tipo tijera todoterreno eléctrico LGMG"),
    "Elevadores de Brazo Articulado": ("Elevadores tipo brazo articulado", "Elevador tipo brazo articulado eléctrico LGMG"),
    "Elevadores de Brazo Telescópico": ("Elevadores tipo brazo telescópico", "Elevador tipo brazo telescópico eléctrico LGMG"),
    "Elevador Mástil Vertical": ("Elevadores tipo mástil vertical", "Elevador tipo mástil vertical eléctrico LGMG"),
    "Elevador de Tijera Sobre Orugas": ("Elevadores tipo tijera sobre orugas", "Elevador tipo tijera sobre orugas eléctrico LGMG"),
    "Manipuladores Telescópicos": ("Manipuladores telescópicos", "Manipulador telescópico eléctrico LGMG"),
}
MISSING_DATASHEETS = {"AR24JE", "T38JE"}
POWER_ENUM = {"electric_24v", "electric_lithium"}
MAX_DATASHEET_BYTES = 10_485_760


class AuditError(ValueError):
    """A controlled package or catalogue conflict."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or re.match(r"^[A-Za-z]:", value) or any(ord(c) < 32 for c in value):
        raise AuditError("Ruta relativa inválida")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or path.as_posix() != value:
        raise AuditError("Ruta relativa no canónica o traversal")
    return value


def read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
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


def model_source_keys(tool_dir: Path | None = None):
    """Read the closed cohort as syntax, without executing the importing tool."""
    path = (tool_dir or Path(__file__).resolve().parent) / "import_lgmg_scissors_minimal.py"
    tree = ast.parse(read_regular(path, path.name).decode("utf-8"), filename=path.name)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL_SOURCE_KEYS" for t in node.targets):
            pairs = tuple(ast.literal_eval(node.value))
            if len(pairs) != 21 or len(set(pairs)) != 21:
                raise AuditError("MODEL_SOURCE_KEYS no contiene 21 pares únicos")
            return pairs
    raise AuditError("No se encontró MODEL_SOURCE_KEYS")


def safe_paths(plan: Path, media: Path, output: Path):
    for item in (plan, media):
        if item.is_symlink() or not item.is_dir():
            raise AuditError("Las entradas deben ser directorios físicos locales")
    resolved = (plan.resolve(), media.resolve(), output.resolve(strict=False))
    if len(set(resolved)) != 3 or any(a in b.parents or b in a.parents for i, a in enumerate(resolved) for b in resolved[i + 1:]):
        raise AuditError("Las rutas no pueden coincidir, contenerse ni solaparse")
    ancestor = resolved[2]
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if ancestor.is_symlink() or (output.exists() and output.is_symlink()):
        raise AuditError("La salida no puede atravesar symlinks")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise AuditError("La salida debe estar ausente o completamente vacía")


def _closed_tree(root: Path, declared: set[str], manifest_name: str):
    actual = set()
    for item in root.rglob("*"):
        if item.is_symlink():
            raise AuditError("Symlink detectado en paquete")
        if item.is_file():
            actual.add(item.relative_to(root).as_posix())
        elif not item.is_dir():
            raise AuditError("Tipo especial detectado en paquete")
    if actual != declared | {manifest_name}:
        raise AuditError("Conjunto cerrado de archivos inconsistente")


def validate_inputs(plan_root: Path, media_root: Path):
    plan_raw = {name: read_regular(plan_root / name, name) for name in (*PLAN_FILES, "import-manifest.json")}
    pm = json_value(plan_raw["import-manifest.json"], "import-manifest.json")
    if pm.get("tool") != PLAN_TOOL or pm.get("version") != PACKAGE_VERSION:
        raise AuditError("Manifest de plan no admitido")
    declared = {item.get("name"): item for item in pm.get("generated_files", []) if isinstance(item, dict)}
    if set(declared) != set(PLAN_FILES):
        raise AuditError("Conjunto declarado del plan inconsistente")
    _closed_tree(plan_root, set(PLAN_FILES), "import-manifest.json")
    for name in PLAN_FILES:
        if declared[name].get("sha256") != sha(plan_raw[name]) or declared[name].get("size") != len(plan_raw[name]):
            raise AuditError(f"Hash o tamaño del plan inconsistente: {name}")
    rows = {name: csv_rows(plan_raw[name], name) for name in PLAN_FILES if name.endswith(".csv")}
    if any(len(rows[name]) != count for name, count in EXPECTED_COUNTS.items()):
        raise AuditError("Conteos aprobados 57/1635/127/57/7/1/44/7 incumplidos")
    document = json_value(plan_raw["import-plan.json"], "import-plan.json")
    plan_fp = pm.get("combined_fingerprint_sha256")
    if not plan_fp or document.get("combined_fingerprint_sha256") != plan_fp or plan_fp != APPROVED_PLAN_FINGERPRINT:
        raise AuditError("Fingerprint combinado del plan no aprobado")
    for key in ("ready_for_import", "content_published", "network_used"):
        if pm.get(key) is not False:
            raise AuditError("Garantías conservadoras del plan incumplidas")

    media_raw = {name: read_regular(media_root / name, name) for name in (*MEDIA_REPORTS, "media-manifest.json")}
    mm = json_value(media_raw["media-manifest.json"], "media-manifest.json")
    if mm.get("tool") != MEDIA_TOOL or mm.get("version") != PACKAGE_VERSION:
        raise AuditError("Manifest de medios no admitido")
    media_fp = sha(media_raw["media-manifest.json"])
    if not media_fp or media_fp != APPROVED_MEDIA_FINGERPRINT or pm.get("media_fingerprint_sha256") != media_fp:
        raise AuditError("Fingerprint contractual o cruzado de medios no aprobado")
    required = {"jem_nexus_called": False, "products_imported": 0, "content_published": False,
        "all_products_ready_for_import": False, "package_complete": True}
    if any(mm.get(key) != value for key, value in required.items()):
        raise AuditError("Garantías conservadoras de medios incumplidas")
    files = {}
    for item in mm.get("files", []):
        if not isinstance(item, dict):
            raise AuditError("Declaración de medio inválida")
        name = safe_relative(item.get("name", ""))
        if name in files:
            raise AuditError("Ruta de medio declarada más de una vez")
        files[name] = item
    _closed_tree(media_root, set(files), "media-manifest.json")
    for name, item in files.items():
        data = read_regular(media_root.joinpath(*PurePosixPath(name).parts), name)
        if item.get("sha256") != sha(data) or item.get("size") != len(data):
            raise AuditError("Hash o tamaño físico de medio inconsistente")
    media_rows = {name: csv_rows(media_raw[name], name) for name in MEDIA_REPORTS if name.endswith(".csv")}
    if media_rows["media-failures.csv"]:
        raise AuditError("El paquete de medios contiene fallos")
    return ({"manifest": pm, "raw": plan_raw, "rows": rows, "fingerprint": plan_fp},
            {"manifest": mm, "raw": media_raw, "rows": media_rows, "files": files, "fingerprint": media_fp})


def split_scope(products, pairs=None):
    if len(products) != 57:
        raise AuditError("El plan no contiene exactamente 57 productos")
    pairs = tuple(pairs or model_source_keys())
    pair_set = set(pairs)
    seen = set(); scope = []; processed = []; remaining = []
    for order, row in enumerate(products, 1):
        key = row.get("source_key", ""); pair = (row.get("metric_model", ""), key)
        if not key or key in seen:
            raise AuditError("source_key vacío o duplicado")
        seen.add(key)
        classification = "processed_closed_cohort" if pair in pair_set else "remaining_candidate"
        enriched = {**row, "source_order": order, "scope_classification": classification}
        scope.append(enriched); (processed if classification == "processed_closed_cohort" else remaining).append(enriched)
    if len(processed) != 21 or {(r["metric_model"], r["source_key"]) for r in processed} != pair_set:
        raise AuditError("La cohorte cerrada no coincide exactamente mediante source_key + metric_model")
    if any(r.get("source_category") != "Elevadores de Tijera" for r in processed):
        raise AuditError("La cohorte cerrada contiene otra familia")
    if any(r.get("source_category") == "Elevadores de Tijera" for r in remaining):
        raise AuditError("Existe una tijera estándar fuera de la cohorte cerrada")
    families = {r.get("source_category") for r in remaining}
    if len(remaining) != 36 or families != set(FAMILIES):
        raise AuditError("La separación 21 + 36 o las seis familias no coincide")
    return scope, processed, remaining


def _bool(row, key, expected=False):
    return row.get(key, "").casefold() == str(expected).casefold()


def _validate_signature(data: bytes, mime: str, suffix: str, kind: str):
    valid_image = ((mime == "image/jpeg" and suffix in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8\xff")) or
        (mime == "image/png" and suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
        (mime == "image/webp" and suffix == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
    if kind == "image" and not valid_image:
        raise AuditError("MIME, extensión o firma de imagen inválidos")
    if kind == "datasheet" and not (mime == "application/pdf" and suffix == ".pdf" and data.startswith(b"%PDF-")):
        raise AuditError("MIME, extensión o firma de PDF inválidos")


def extract_pdf_text(data: bytes):
    """Extract only simple literal PDF text; return None rather than guessing."""
    chunks = re.findall(rb"\(([^()]*)\)\s*T[jJ]", data) or re.findall(rb"\(([^()]{3,})\)", data)
    if not chunks:
        return None
    text = " ".join(chunk.decode("latin-1", "ignore") for chunk in chunks)
    return text if len(re.findall(r"[A-Za-z0-9]", text)) >= 4 else None


def conservative_model_markers(value: str, models):
    """Find literal catalogue models without globally transforming their spelling."""
    return sorted(model for model in models if re.search(
        rf"(?<![A-Za-z0-9]){re.escape(model)}(?![A-Za-z0-9])", str(value or ""), re.IGNORECASE))


def model_like_markers(value: str):
    """Return conservative LGMG-shaped tokens, including models outside this cohort."""
    return sorted(set(re.findall(r"(?<![A-Za-z0-9])(?:[A-Z]{1,4}\d{2,4}[A-Z](?:-\d+)?)(?![A-Za-z0-9])",
        str(value or "").upper())))


def analyze_media_findings(records):
    """Classify general cross-product datasheet/image patterns for tests and audits."""
    findings = {record["metric_model"]: [] for record in records}
    models = set(findings)
    datasheet_owners = {}
    image_sets = {}
    for record in records:
        model = record["metric_model"]
        sheet = record.get("datasheet") or {}
        digest = sheet.get("sha256", "")
        if digest: datasheet_owners.setdefault(digest, set()).add(model)
        if int(sheet.get("size_bytes") or 0) > MAX_DATASHEET_BYTES:
            findings[model].append("datasheet_exceeds_backend_limit")
        text = sheet.get("text")
        markers = sorted(set(conservative_model_markers(text or "", models) + model_like_markers(text or "")))
        if text is not None and (model.upper() not in markers or any(marker != model.upper() for marker in markers)):
            findings[model].append("datasheet_model_mismatch")
        filename_markers = sorted(set(conservative_model_markers(sheet.get("filename", ""), models) + model_like_markers(sheet.get("filename", ""))))
        if any(marker != model.upper() for marker in filename_markers):
            findings[model].append("datasheet_filename_mentions_other_model")
            if model.upper() not in filename_markers:
                findings[model].append("datasheet_model_mismatch")
        images = record.get("images") or []
        image_sets[model] = {item.get("sha256") for item in images if item.get("sha256")}
        primary = next((item for item in images if item.get("is_primary")), None)
        if primary and any(marker != model.upper() for marker in sorted(set(conservative_model_markers(primary.get("filename", ""), models) + model_like_markers(primary.get("filename", ""))))):
            findings[model].append("primary_filename_mentions_other_model")
    for owners in datasheet_owners.values():
        if len(owners) > 1:
            for model in owners: findings[model].append("datasheet_shared_across_products")
    ordered = sorted(image_sets)
    for index, first in enumerate(ordered):
        if not image_sets[first]: continue
        for second in ordered[index + 1:]:
            if image_sets[first] == image_sets[second]:
                findings[first].append("all_images_shared_across_products")
                findings[second].append("all_images_shared_across_products")
    return {model: sorted(set(values)) for model, values in findings.items()}


def inspect_media(remaining, plan, media, media_root: Path):
    keys = {r["source_key"]: r for r in remaining}
    file_rows = {}
    for row in media["rows"]["media-files.csv"]:
        rel = safe_relative(row.get("local_file", ""))
        if rel in file_rows: raise AuditError("Archivo físico duplicado en media-files.csv")
        file_rows[rel] = row
    downloaded_images = {(r.get("source_key"), r.get("image_order")): r for r in media["rows"]["downloaded-images.csv"]}
    downloaded_sheets = {(r.get("source_key"), r.get("datasheet_order")): r for r in media["rows"]["downloaded-datasheets.csv"]}
    images_by = {key: [] for key in keys}; sheets_by = {key: [] for key in keys}
    for row in plan["rows"]["import-images.csv"]:
        if row.get("source_key") in keys: images_by[row["source_key"]].append(row)
    for row in plan["rows"]["import-datasheets.csv"]:
        if row.get("source_key") in keys: sheets_by[row["source_key"]].append(row)
    hash_owners = {}
    results = {}
    def physical(row, kind, downloaded):
        rel = safe_relative(row.get("local_file", "")); data = read_regular(media_root.joinpath(*PurePosixPath(rel).parts), rel)
        companion = file_rows.get(rel); association = downloaded.get((row.get("source_key"), row.get(kind + "_order")))
        if not companion or not association:
            raise AuditError("Asociación contractual de medio ausente")
        for value in (row, companion, association):
            if value.get("sha256") != sha(data) or str(value.get("size_bytes")) != str(len(data)) or value.get("mime_type") != row.get("mime_type"):
                raise AuditError("Hash, tamaño o MIME de asociación inconsistente")
        _validate_signature(data, row["mime_type"], Path(rel).suffix.casefold(), kind)
        hash_owners.setdefault(sha(data), set()).add(row["source_key"])
        return rel, sha(data), len(data), row["mime_type"]
    for key, product in keys.items():
        images = images_by[key]
        if not images or any(r.get("metric_model") != product.get("metric_model") for r in images):
            raise AuditError("Asociaciones de imagen ausentes o con modelo incorrecto")
        primary = [r for r in images if r.get("primary_candidate", "").casefold() == "true"]
        if len(primary) != 1:
            raise AuditError("Debe existir exactamente una imagen candidata principal")
        physical_images = [physical(r, "image", downloaded_images) for r in images]
        sheet_rows = sheets_by[key]
        if len(sheet_rows) != 1 or sheet_rows[0].get("metric_model") != product.get("metric_model"):
            raise AuditError("Debe existir exactamente una fila de ficha por producto")
        sheet = sheet_rows[0]; status = sheet.get("datasheet_status")
        if status == "missing_at_source":
            if product.get("metric_model") not in MISSING_DATASHEETS or any(sheet.get(k) for k in ("local_file", "sha256", "size_bytes", "mime_type")):
                raise AuditError("Ficha missing_at_source no autorizada o con medio inventado")
            sheet_info = ("", "", "", "")
        else:
            if status != "available_at_source": raise AuditError("Estado de ficha desconocido")
            sheet_info = physical(sheet, "datasheet", downloaded_sheets)
        results[key] = {"images": physical_images, "primary": physical(primary[0], "image", downloaded_images),
            "image_rows": images, "datasheet": sheet_info, "datasheet_row": sheet, "datasheet_status": status}
    missing = {p["metric_model"] for p in remaining if results[p["source_key"]]["datasheet_status"] == "missing_at_source"}
    if missing != MISSING_DATASHEETS:
        raise AuditError("AR24JE y T38JE deben ser las únicas fichas missing_at_source")
    for value in results.values():
        value["shared_image_hashes"] = sorted({h for _, h, _, _ in value["images"] if len(hash_owners[h]) > 1})
        sheet_hash = value["datasheet"][1]
        value["shared_datasheet_hash"] = sheet_hash if sheet_hash and len(hash_owners[sheet_hash]) > 1 else ""
    return results


def approval_key(row, media_info, plan_fp, media_fp):
    payload = {"plan_fingerprint": plan_fp, "media_fingerprint": media_fp,
        "source_key": row["source_key"], "source_family": row["source_category"],
        "source_model": row["metric_model"], "proposed_target_subcategory": row["proposed_target_subcategory"],
        "proposed_target_model": row["proposed_target_model"], "proposed_target_name": row["proposed_target_name"],
        "primary_image_sha256": media_info["primary"][1],
        "datasheet": media_info["datasheet"][1] or media_info["datasheet_status"]}
    return sha(canonical(payload))


def build_audit(plan, media, media_root: Path):
    scope, processed, remaining = split_scope(plan["rows"]["import-products.csv"])
    media_info = inspect_media(remaining, plan, media, media_root)
    specs = {r["source_key"]: [] for r in remaining}
    for row in plan["rows"]["import-specifications.csv"]:
        if row.get("source_key") in specs: specs[row["source_key"]].append(row)
    fixed = {"target_brand": "LGMG", "product_type": "machinery", "condition": "new", "stock_status": "on_request"}
    finding_records = []
    for source in remaining:
        info = media_info[source["source_key"]]
        sheet = info["datasheet"]
        text = extract_pdf_text(read_regular(media_root.joinpath(*PurePosixPath(sheet[0]).parts), sheet[0])) if sheet[0] else None
        finding_records.append({"metric_model": source["metric_model"],
            "datasheet": {"sha256": sheet[1], "size_bytes": sheet[2] or 0,
                "filename": Path(sheet[0]).name if sheet[0] else "", "text": text},
            "images": [{"sha256": item[1], "filename": Path(item[0]).name,
                "is_primary": item[1] == info["primary"][1]} for item in info["images"]]})
    media_findings = analyze_media_findings(finding_records)
    output = []
    for source in remaining:
        conflicts = []
        for key, expected in fixed.items():
            if source.get(key) != expected: conflicts.append(f"{key}_must_equal_{expected}")
        null_fields = ("price", "currency", "price_tax_mode")
        if any(source.get(k, "") not in ("", None) for k in null_fields): conflicts.append("commercial_value_must_be_null")
        false_fields = ("show_price", "is_published", "is_featured", "ready_for_import",
            "includes_technical_review", "includes_commercial_technical_advice", "includes_coordinated_delivery")
        if any(not _bool(source, k) for k in false_fields): conflicts.append("commercial_boolean_must_be_false")
        subcategory, prefix = FAMILIES[source["source_category"]]
        model = source["metric_model"]
        info = media_info[source["source_key"]]
        power = source.get("target_power_source", "")
        findings = media_findings[model]
        followup = info["datasheet_status"] == "missing_at_source" or power not in POWER_ENUM or bool(findings)
        media_review = any(x in findings for x in ("all_images_shared_across_products", "primary_filename_mentions_other_model"))
        exceeds = "datasheet_exceeds_backend_limit" in findings
        datasheet_problem = any(x in findings for x in ("datasheet_model_mismatch", "datasheet_filename_mentions_other_model"))
        row = {**source, "source_family": source["source_category"], "source_model": model,
            "source_proposed_name": source.get("proposed_name", ""), "proposed_target_subcategory": subcategory,
            "proposed_target_model": model, "proposed_target_name": f"{prefix} {model}",
            "naming_transformation": "prefijo cerrado por familia + espacio + metric_model exacto; pendiente de aprobación humana",
            "brand": source.get("target_brand", ""), "specification_count": len(specs[source["source_key"]]),
            "maximum_load_capacity_candidate_kg": source.get("maximum_load_capacity_kg", ""),
            "power_source_candidate": power if power in POWER_ENUM else "", "power_source_representable": power in POWER_ENUM,
            "image_association_count": len(info["images"]), "unique_physical_image_count": len({x[0] for x in info["images"]}),
            "primary_image_status": "valid_unique_candidate", "datasheet_status": info["datasheet_status"],
            "technical_followup_required": followup, "minimal_import_status": "candidate_after_approval" if not conflicts else "blocked_identity",
            "approval_status": "pending_human_approval", "product_data_approval_status": "pending_human_approval",
            "media_approval_status": "pending_human_visual_review" if media_review else ("requires_datasheet_repair" if datasheet_problem else "media_prepared"),
            "datasheet_upload_status": "excluded_backend_size_limit" if exceeds else ("blocked_model_mismatch" if datasheet_problem else info["datasheet_status"]),
            "ready_for_controlled_import": False, "ready_for_import": False, "media_findings": findings,
            "warnings": ";".join((["technical_followup_required"] if followup else []) + findings + conflicts)}
        row["approval_key"] = approval_key(row, info, plan["fingerprint"], media["fingerprint"])
        row["_conflicts"] = conflicts
        row["_media_findings"] = findings
        output.append(row)
    fingerprint = sha(canonical([{k: v for k, v in row.items() if k != "_conflicts"} for row in output]))
    return {"scope": scope, "processed": processed, "products": output, "media": media_info,
        "remaining_catalog_fingerprint_sha256": fingerprint}


def formula_safe(value):
    text = "" if value is None else (json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (list, dict)) else str(value))
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows: writer.writerow({key: formula_safe(row.get(key, "")) for key in fields})


def _input_files(plan, media):
    result = []
    for package, raw in (("plan", plan["raw"]), ("media", media["raw"])):
        for name in sorted(raw): result.append({"package": package, "name": name, "sha256": sha(raw[name]), "size": len(raw[name])})
    report_names = set(media["raw"])
    for name in sorted(media["files"]):
        if name not in report_names:
            item = media["files"][name]
            result.append({"package": "media", "name": name, "sha256": item["sha256"], "size": item["size"]})
    return result


def write_outputs(output: Path, audit, plan, media, created_at: str):
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".remaining-audit-", dir=output))
    try:
        scope_fields = ("source_order", "source_key", "source_category", "metric_model", "scope_classification")
        product_fields = ("source_order", "approval_key", "source_key", "source_family", "source_model", "metric_model", "imperial_model", "aliases",
            "source_proposed_name", "proposed_target_subcategory", "proposed_target_model", "proposed_target_name", "naming_transformation", "brand",
            "product_type", "condition", "stock_status", "specification_count", "maximum_load_capacity_candidate_kg", "power_source_candidate",
            "power_source_representable", "image_association_count", "unique_physical_image_count", "primary_image_status", "datasheet_status",
            "technical_followup_required", "minimal_import_status", "approval_status", "product_data_approval_status",
            "media_approval_status", "datasheet_upload_status", "ready_for_controlled_import", "ready_for_import", "media_findings", "warnings")
        write_csv(staging / OUTPUT_NAMES[0], scope_fields, audit["scope"])
        write_csv(staging / OUTPUT_NAMES[1], product_fields, audit["products"])
        family_rows = []
        for family, (subcategory, prefix) in FAMILIES.items():
            rows = [r for r in audit["products"] if r["source_family"] == family]
            family_rows.append({"source_family": family, "proposed_target_subcategory": subcategory, "commercial_prefix": prefix,
                "product_count": len(rows), "candidate_after_approval_count": sum(r["minimal_import_status"] == "candidate_after_approval" for r in rows),
                "blocked_count": sum(r["minimal_import_status"] != "candidate_after_approval" for r in rows), "images_available_count": len(rows),
                "datasheets_available_count": sum(r["datasheet_status"] == "available_at_source" for r in rows),
                "datasheets_missing_at_source_count": sum(r["datasheet_status"] == "missing_at_source" for r in rows),
                "technical_followup_count": sum(bool(r["technical_followup_required"]) for r in rows)})
        write_csv(staging / OUTPUT_NAMES[2], tuple(family_rows[0]), family_rows)
        media_rows = []
        for row in audit["products"]:
            info = audit["media"][row["source_key"]]; image = info["primary"]; sheet = info["datasheet"]
            media_rows.append({"source_order": row["source_order"], "source_key": row["source_key"], "metric_model": row["metric_model"],
                "image_association_count": len(info["images"]), "unique_physical_image_count": len({x[0] for x in info["images"]}),
                "primary_image_relative_path": image[0], "primary_image_sha256": image[1], "primary_image_size": image[2], "primary_image_mime": image[3],
                "primary_image_status": "ready_for_future_minimal_import", "shared_image_hashes": info["shared_image_hashes"],
                "datasheet_status": info["datasheet_status"], "datasheet_relative_path": sheet[0], "datasheet_sha256": sheet[1],
                "datasheet_size": sheet[2], "datasheet_mime": sheet[3], "shared_datasheet_hash": info["shared_datasheet_hash"],
                "datasheet_physically_present": bool(sheet[0])})
        write_csv(staging / OUTPUT_NAMES[3], tuple(media_rows[0]), media_rows)
        conflict_fields = ("source_order", "source_key", "metric_model", "conflict_code", "detail", "blocking")
        conflicts = [{"source_order": r["source_order"], "source_key": r["source_key"], "metric_model": r["metric_model"],
            "conflict_code": code, "detail": "Valor conservador del plan incumplido", "blocking": True}
            for r in audit["products"] for code in r["_conflicts"]]
        conflicts.extend({"source_order": r["source_order"], "source_key": r["source_key"], "metric_model": r["metric_model"],
            "conflict_code": code, "detail": "Hallazgo general de coherencia de medios; requiere reparación o revisión humana",
            "blocking": code not in ("datasheet_exceeds_backend_limit", "datasheet_shared_across_products")}
            for r in audit["products"] for code in r.get("_media_findings", []))
        write_csv(staging / OUTPUT_NAMES[4], conflict_fields, conflicts)
        summary = {"verdict": "AUDIT_COMPLETE" if not conflicts else "CONFLICT", "approved_plan_fingerprint": plan["fingerprint"],
            "approved_media_fingerprint": media["fingerprint"], "remaining_catalog_fingerprint_sha256": audit["remaining_catalog_fingerprint_sha256"],
            "total_plan_products": 57, "processed_closed_cohort": 21, "remaining_products": 36, "remaining_families": 6,
            "products_automatically_approved": 0, "products_ready_for_import": 0, "human_review_required": True,
            "known_missing_datasheets": ["AR24JE", "T38JE"], "minimal_import_scope": "identity, proposed category, exact model, proposed name and primary image after approval",
            "technical_enrichment_scope": "existing plan candidates and datasheet association; follow-up remains separate",
            "catalog_scope_note": "El plan electric-only no representa necesariamente todo el catálogo mundial de LGMG; productos no eléctricos o inciertos fuera del plan no se consideran importados ni deben olvidarse."}
        (staging / OUTPUT_NAMES[5]).write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        prose = ("AUDIT_COMPLETE\n57 productos: 21 en processed_closed_cohort y 36 pendientes de aprobación humana en seis familias.\n"
            "Cero aprobados automáticamente y cero listos para importar antes de aprobación.\nAR24JE y T38JE: ficha missing_at_source; importación mínima no bloqueada, enriquecimiento técnico pendiente.\n"
            "La importación mínima futura es distinta del enriquecimiento técnico. El plan electric-only no equivale a todo el catálogo mundial; los productos no eléctricos o inciertos excluidos no se importaron ni deben olvidarse.\n")
        (staging / OUTPUT_NAMES[6]).write_text(prose, encoding="utf-8")
        readme = ("AUDITORÍA OFFLINE DEL CATÁLOGO LGMG RESTANTE\n\n" + prose +
            "Esta evidencia es una propuesta para revisión, no una consulta de base de datos ni una aprobación. No usa red, API, credenciales ni modo de aplicación.\n")
        (staging / OUTPUT_NAMES[8]).write_text(readme, encoding="utf-8")
        generated = []
        for name in OUTPUT_NAMES:
            if name == "remaining-manifest.json": continue
            data = (staging / name).read_bytes(); generated.append({"name": name, "sha256": sha(data), "size": len(data)})
        manifest = {**summary, "tool": TOOL_NAME, "version": TOOL_VERSION, "created_at_utc": created_at,
            "input_files": _input_files(plan, media), "output_files": generated, "apply_supported": False,
            "network_called": False, "api_called": False, "database_modified": False, "products_created": 0,
            "products_updated": 0, "products_deleted": 0, "images_uploaded": 0, "datasheets_uploaded": 0,
            "content_published": False, "credentials_persisted": False}
        (staging / OUTPUT_NAMES[7]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if set(p.name for p in staging.iterdir()) != set(OUTPUT_NAMES): raise AuditError("Conjunto de salida incompleto")
        for name in OUTPUT_NAMES: os.replace(staging / name, output / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def run(plan_input: Path, media_input: Path, output_dir: Path, *, created_at=None):
    safe_paths(plan_input, media_input, output_dir)
    try:
        plan, media = validate_inputs(plan_input, media_input)
        audit = build_audit(plan, media, media_input)
        write_outputs(output_dir, audit, plan, media, created_at or datetime.now(timezone.utc).isoformat())
    except Exception:
        if output_dir.exists() and not any(p.name in OUTPUT_NAMES for p in output_dir.iterdir()):
            for item in output_dir.iterdir():
                if item.name.startswith(".remaining-audit-"): shutil.rmtree(item, ignore_errors=True)
        raise
    return audit


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Audita offline los 36 productos LGMG restantes")
    parser.add_argument("--plan-input", required=True)
    parser.add_argument("--media-input", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        run(Path(args.plan_input), Path(args.media_input), Path(args.output_dir))
        print("AUDIT_COMPLETE")
        return 0
    except (AuditError, OSError) as exc:
        print(f"CONFLICT: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
