#!/usr/bin/env python3
"""Prepare a new, reviewable media package for the 36 remaining LGMG products."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html import escape
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

_AUDIT_SPEC = importlib.util.spec_from_file_location(
    "_lgmg_remaining_audit_contract", Path(__file__).with_name("audit_lgmg_remaining_catalog.py"))
audit_contract = importlib.util.module_from_spec(_AUDIT_SPEC)
_AUDIT_SPEC.loader.exec_module(audit_contract)

TOOL_NAME = "repair_lgmg_remaining_media"
TOOL_VERSION = "1.0.0"
MAX_DATASHEET_BYTES = 10_485_760
APPROVAL_TEXT = "APRUEBO LAS 6 FAMILIAS Y LOS 36 NOMBRES"
REPAIR_MODELS = ("SR1018E-2", "T28JE")
OFFICIAL_PAGES = {
    "SR1018E-2": "https://www.lgmglifts.com/product/pro-detail-5182.htm",
    "T28JE": "https://www.lgmglifts.com/product/pro-detail-2045.htm",
    "H625E": "https://www.lgmglifts.com/product/pro-detail-5148.htm",
    "A13JE": "https://www.lgmglifts.com/product/pro-detail-4895.htm",
    "A14JE": "https://www.lgmglifts.com/product/pro-detail-616.htm",
}
VISUAL_DECISIONS = {
    "approve_shared_images_for_both", "approve_images_for_a13je_only",
    "approve_images_for_a14je_only", "reject_shared_images_for_both",
    "pending_human_visual_review", "approve_separate_model_images",
}
OFFICIAL_DATASHEETS = {
    "SR1018E-2": "https://www.lgmglifts.com/upload/file/2025/04/lgmg-RT-scissorlift-en-SR1018E-2.pdf",
    "T28JE": "https://www.lgmglifts.com/upload/file/2023/07/10/73e3683775884b6da85c0f265d315616.pdf",
}
EXPECTED_MODEL_MARKERS = {
    "SR1018E-2": ["SR1018E-2", "SR3369E-2"],
    "T28JE": ["T28JE", "T92JE"],
}
APPROVED_SEPARATE_IMAGES = {
    "A13JE": {
        "primary_sha256": "21b8e8bbb8d2b40617b01fd86aee1c8c30025e742f90cc8f4229eaea264744ce",
        "ordered_sha256": [
            "21b8e8bbb8d2b40617b01fd86aee1c8c30025e742f90cc8f4229eaea264744ce",
            "3fc3777d98efadbd36a4cc31fde58887a476e92f1b163250011128ad02f946f4",
        ],
    },
    "A14JE": {
        "primary_sha256": "e3e568efc55d1f9dcadc9bdd76f80a2ec1a6fe7d88df776cc3c5b8c1b16fe9de",
        "ordered_sha256": [
            "e3e568efc55d1f9dcadc9bdd76f80a2ec1a6fe7d88df776cc3c5b8c1b16fe9de",
            "b95ee211b2a20be84372f88bfb828be596fe4fce6618b4e32f0dd6dfa9a13541",
            "acb85d1fbe203d02ef7f1af42ef0e00d6f43cb643be952b8c65c85c572c9ab41",
        ],
    },
}
AUDIT_OUTPUTS = audit_contract.OUTPUT_NAMES
OUTPUT_NAMES = (
    "corrected-media", "repair-summary.json", "repair-summary.txt", "repair-manifest.json",
    "repair-conflicts.csv", "repair-datasheets.csv", "repair-images.csv",
    "controlled-import-readiness.csv", "A13JE-A14JE-visual-review.html",
    "A13JE-A14JE-visual-review.csv", "README-repaired-media.txt",
)


class RepairError(ValueError):
    """A controlled structural, safety, or media conflict."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def safe_relative(value: str) -> str:
    try:
        return audit_contract.safe_relative(value)
    except audit_contract.AuditError as exc:
        raise RepairError(str(exc)) from exc


def read_regular(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise RepairError(f"Archivo obligatorio ausente: {label}") from exc
    if path.is_symlink() or not stat.S_ISREG(mode):
        raise RepairError(f"Archivo inseguro o de tipo especial: {label}")
    return path.read_bytes()


def _assert_physical_directory(path: Path, label: str):
    if path.is_symlink() or not path.is_dir():
        raise RepairError(f"{label} debe ser un directorio físico")
    current = path.absolute()
    while current != current.parent:
        if current.is_symlink():
            raise RepairError(f"{label} no puede resolverse mediante symlink")
        current = current.parent


def safe_paths(plan: Path, media: Path, remaining: Path, decisions: Path, output: Path):
    for path, label in ((plan, "plan-input"), (media, "media-input"), (remaining, "remaining-audit-input")):
        _assert_physical_directory(path, label)
    read_regular(decisions, "decisions-input")
    _assert_physical_directory(decisions.parent, "padre de decisions-input")
    _assert_physical_directory(output.parent, "padre de output-dir")
    resolved_inputs = [p.resolve() for p in (plan, media, remaining, decisions)]
    resolved_output = output.resolve(strict=False)
    for source in resolved_inputs:
        if resolved_output == source or resolved_output in source.parents or source in resolved_output.parents:
            raise RepairError("output-dir no puede coincidir, contenerse ni contener una entrada")
    if output.exists():
        if output.is_symlink() or not output.is_dir() or any(output.iterdir()):
            raise RepairError("output-dir debe estar ausente o completamente vacío")


def csv_rows(data: bytes, label: str):
    try:
        return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except (UnicodeError, csv.Error) as exc:
        raise RepairError(f"CSV inválido: {label}") from exc


def json_value(data: bytes, label: str):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RepairError(f"JSON inválido: {label}") from exc


def validate_remaining_audit(root: Path, plan_fp: str, media_fp: str):
    raw = {name: read_regular(root / name, name) for name in AUDIT_OUTPUTS}
    actual = set()
    for item in root.rglob("*"):
        if item.is_symlink() or (not item.is_file() and not item.is_dir()):
            raise RepairError("El paquete de auditoría contiene symlinks o tipos especiales")
        if item.is_file():
            actual.add(item.relative_to(root).as_posix())
    if actual != set(AUDIT_OUTPUTS):
        raise RepairError("La auditoría restante no contiene exactamente sus nueve salidas")
    manifest = json_value(raw["remaining-manifest.json"], "remaining-manifest.json")
    if (manifest.get("tool") != audit_contract.TOOL_NAME or manifest.get("version") != audit_contract.TOOL_VERSION or
            manifest.get("approved_plan_fingerprint") != plan_fp or manifest.get("approved_media_fingerprint") != media_fp or
            manifest.get("remaining_products") != 36 or manifest.get("processed_closed_cohort") != 21):
        raise RepairError("Fingerprint, versión o conteos de auditoría restante incoherentes")
    declared = {x.get("name"): x for x in manifest.get("output_files", []) if isinstance(x, dict)}
    for name in AUDIT_OUTPUTS:
        if name == "remaining-manifest.json":
            continue
        if name not in declared or declared[name].get("sha256") != sha(raw[name]) or declared[name].get("size") != len(raw[name]):
            raise RepairError(f"Hash de salida de auditoría incoherente: {name}")
    products = csv_rows(raw["remaining-products-for-approval.csv"], "remaining-products-for-approval.csv")
    if len(products) != 36 or len({r.get("metric_model") for r in products}) != 36:
        raise RepairError("La auditoría no conserva exactamente 36 modelos")
    fingerprint = manifest.get("remaining_catalog_fingerprint_sha256")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise RepairError("Fingerprint del catálogo restante inválido")
    return {"raw": raw, "manifest": manifest, "products": products,
        "fingerprint": fingerprint, "input_fingerprint": sha(canonical([
            {"name": name, "sha256": sha(raw[name]), "size": len(raw[name])} for name in sorted(raw)]))}


def validate_decisions(data: bytes):
    value = json_value(data, "decisions-input")
    if not isinstance(value, dict) or set(value) != {"schema_version", "catalog_approval", "datasheet_repairs", "shared_image_decisions"}:
        raise RepairError("Contrato de decisiones incompleto o con claves desconocidas")
    approval = value.get("catalog_approval", {})
    if value.get("schema_version") != "1.0" or approval.get("approved") is not True or approval.get("approval_text") != APPROVAL_TEXT:
        raise RepairError("La aprobación comercial no coincide literalmente")
    repairs = value.get("datasheet_repairs")
    if not isinstance(repairs, dict) or set(repairs) != {"SR1018E-2", "T28JE", "H625E"}:
        raise RepairError("Decisiones de fichas incompletas")
    for model in REPAIR_MODELS:
        item = repairs[model]
        if (item.get("action") != "replace_from_official_source" or item.get("product_page_url") != OFFICIAL_PAGES[model] or
                item.get("expected_model_markers") != EXPECTED_MODEL_MARKERS[model] or not isinstance(item.get("datasheet_url"), str)):
            raise RepairError(f"Decisión cerrada inválida para {model}")
        if item["datasheet_url"]:
            validate_official_url(item["datasheet_url"])
            if item["datasheet_url"] != OFFICIAL_DATASHEETS[model]:
                raise RepairError(f"URL oficial no aprobada para {model}")
    h625e = repairs["H625E"]
    if h625e != {"action": "exclude_backend_size_limit", "maximum_backend_size_bytes": MAX_DATASHEET_BYTES}:
        raise RepairError("La exclusión contractual de H625E fue alterada")
    shared = value.get("shared_image_decisions")
    if not isinstance(shared, dict) or set(shared) != {"A13JE|A14JE"}:
        raise RepairError("Decisión visual cerrada ausente")
    visual = shared["A13JE|A14JE"]
    expected_keys = {"decision", "notes", "approved_images"} if visual.get("decision") == "approve_separate_model_images" else {"decision", "notes"}
    if set(visual) != expected_keys or visual.get("decision") not in VISUAL_DECISIONS or not isinstance(visual.get("notes"), str):
        raise RepairError("Decisión visual desconocida o inválida")
    if visual.get("decision") == "approve_separate_model_images":
        approved = visual.get("approved_images")
        if not isinstance(approved, dict) or set(approved) != {"A13JE", "A14JE"}:
            raise RepairError("approved_images debe declarar exactamente A13JE y A14JE")
        for model, expected in APPROVED_SEPARATE_IMAGES.items():
            item = approved.get(model)
            if not isinstance(item, dict) or set(item) != {"primary_sha256", "ordered_sha256"}:
                raise RepairError(f"Contrato approved_images inválido para {model}")
            primary, ordered = item["primary_sha256"], item["ordered_sha256"]
            if (not isinstance(primary, str) or not re.fullmatch(r"[0-9a-f]{64}", primary) or
                    not isinstance(ordered, list) or not ordered or
                    any(not isinstance(x, str) or not re.fullmatch(r"[0-9a-f]{64}", x) for x in ordered) or
                    len(ordered) != len(set(ordered)) or primary not in ordered or ordered[0] != primary):
                raise RepairError(f"Hashes approved_images inválidos para {model}")
            if item != expected:
                raise RepairError(f"Conjunto de imágenes aprobado inesperado para {model}")
    return value


def validate_official_url(url: str) -> str:
    if not isinstance(url, str) or not url or "\\" in url or any(ord(c) < 32 for c in url):
        raise RepairError("URL directa inválida")
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if (parsed.scheme != "https" or (host != "lgmglifts.com" and not host.endswith(".lgmglifts.com")) or
            parsed.username or parsed.password or parsed.fragment):
        raise RepairError("Solo se admiten URLs HTTPS oficiales de LGMG")
    try:
        if parsed.port not in (None, 443):
            raise RepairError("Puerto de URL no admitido")
    except ValueError as exc:
        raise RepairError("Puerto de URL inválido") from exc
    decoded = urllib.parse.unquote(parsed.path)
    if not decoded or "\\" in decoded or any(part in (".", "..") for part in decoded.split("/")):
        raise RepairError("Ruta de URL insegura")
    return urllib.parse.urlunsplit(parsed)


class StrictRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__(); self.followed = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_official_url(newurl)
        self.followed += 1
        if self.followed > 3:
            raise RepairError("Demasiadas redirecciones")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def open(self, url):
        redirect = StrictRedirect()
        response = urllib.request.build_opener(redirect).open(
            urllib.request.Request(url, headers={"User-Agent": "LGMG-media-repair/1.0", "Accept": "application/pdf"}), timeout=30)
        return response, redirect


def _header(response, name):
    headers = getattr(response, "headers", {})
    return headers.get(name, "") if hasattr(headers, "get") else ""


def extract_pdf_text(data: bytes):
    """Conservative dependency-free extraction for PDFs with literal text operands."""
    chunks = re.findall(rb"\(([^()]*)\)\s*T[jJ]", data)
    if not chunks:
        chunks = re.findall(rb"\(([^()]{3,})\)", data)
    if not chunks:
        return None
    text = " ".join(c.decode("latin-1", "ignore") for c in chunks)
    text = re.sub(r"\\([()\\])", r"\1", text)
    return text if len(re.findall(r"[A-Za-z0-9]", text)) >= 4 else None


def validate_pdf(data: bytes, mime: str, expected_model: str, *, known_models=(), expected_markers=None):
    if not data or len(data) > MAX_DATASHEET_BYTES:
        raise RepairError("Ficha vacía o superior al límite de 10 MiB")
    base_mime = str(mime).partition(";")[0].strip().casefold()
    if base_mime not in {"application/pdf", "application/octet-stream"}:
        raise RepairError("MIME de ficha incompatible con PDF")
    head = data[:1024].lstrip().lower()
    if not data.startswith(b"%PDF-") or head.startswith((b"<html", b"<!doctype html")) or b"%%EOF" not in data[-2048:]:
        raise RepairError("Respuesta HTML o PDF vacío/truncado")
    text = extract_pdf_text(data)
    if text is None:
        return "downloaded_pending_human_content_review", None
    normalize = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())
    markers = expected_markers or [expected_model]
    found = {m for m in known_models if normalize(m) and normalize(m) in normalize(text)}
    if not any(normalize(marker) in normalize(text) for marker in markers):
        other = sorted(m for m in found if m != expected_model)
        raise RepairError("datasheet_model_mismatch" + (":" + ",".join(other) if other else ""))
    return "validated_model_content", text


def download_datasheet(url: str, expected_model: str, known_models, fetcher=None, expected_markers=None):
    url = validate_official_url(url); fetcher = fetcher or Fetcher()
    try:
        opened = fetcher.open(url)
        response, redirect = opened if isinstance(opened, tuple) else (opened, None)
        with response:
            status = getattr(response, "status", response.getcode() if hasattr(response, "getcode") else 200)
            if not 200 <= int(status) < 300:
                raise RepairError("Código HTTP no satisfactorio")
            final_url = validate_official_url(response.geturl() if hasattr(response, "geturl") else url)
            length = _header(response, "Content-Length")
            if length and (not str(length).isdigit() or int(length) > MAX_DATASHEET_BYTES):
                raise RepairError("Ficha superior al límite de 10 MiB")
            data = response.read(MAX_DATASHEET_BYTES + 1)
            mime = _header(response, "Content-Type")
    except RepairError:
        raise
    except Exception as exc:
        raise RepairError("Descarga oficial fallida") from exc
    validation, _ = validate_pdf(data, mime, expected_model, known_models=known_models,
        expected_markers=expected_markers)
    filename = Path(urllib.parse.urlsplit(final_url).path).name
    filename = re.sub(r"[^A-Za-z0-9._-]", "-", filename) or f"{expected_model}.pdf"
    if not filename.casefold().endswith(".pdf"):
        filename += ".pdf"
    return {"data": data, "sha256": sha(data), "size_bytes": len(data), "mime": "application/pdf",
        "validation": validation, "filename": filename, "url": url,
        "redirects": getattr(redirect, "followed", 0)}


def image_dimensions(data: bytes, mime: str):
    if mime == "image/png" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if mime == "image/jpeg":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xff: i += 1; continue
            marker = data[i + 1]; length = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in range(0xc0, 0xc4): return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
            i += 2 + max(length, 2)
    if mime == "image/webp" and len(data) >= 30 and data[12:16] == b"VP8X":
        return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
    return "", ""


def formula_safe(value):
    text = "" if value is None else (json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (list, dict)) else str(value))
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def write_csv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: formula_safe(row.get(field, "")) for field in fields})


def _media_associations(remaining_products, plan, media, media_root, target_media):
    keys = {r["source_key"]: r for r in remaining_products}
    image_plan = [r for r in plan["rows"]["import-images.csv"] if r.get("source_key") in keys]
    sheets = {r["source_key"]: r for r in plan["rows"]["import-datasheets.csv"] if r.get("source_key") in keys}
    hashes, copied, image_rows = {}, {}, []
    known_models = {r["metric_model"] for r in remaining_products}
    for row in image_plan:
        rel = safe_relative(row.get("local_file", "")); data = read_regular(media_root.joinpath(*PurePosixPath(rel).parts), rel)
        digest = sha(data)
        if digest != row.get("sha256") or str(len(data)) != str(row.get("size_bytes")):
            raise RepairError("Hash o tamaño de imagen incoherente")
        audit_contract._validate_signature(data, row.get("mime_type", ""), Path(rel).suffix.casefold(), "image")
        hashes.setdefault(digest, set()).add(row["metric_model"])
        suffix = Path(rel).suffix.casefold(); corrected = copied.get(digest)
        if not corrected:
            corrected = f"corrected-media/images/{digest}{suffix}"
            destination = target_media.parent.joinpath(*PurePosixPath(corrected).parts)
            destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(data); copied[digest] = corrected
        width, height = image_dimensions(data, row.get("mime_type", ""))
        markers = sorted(m for m in known_models if re.search(rf"(?<![A-Za-z0-9]){re.escape(m)}(?![A-Za-z0-9])", Path(rel).name, re.I))
        image_rows.append({"metric_model": row["metric_model"], "association_order": row.get("image_order", ""),
            "is_primary": row.get("primary_candidate", "").casefold() == "true", "relative_path": corrected,
            "original_filename": Path(rel).name, "sha256": digest, "size_bytes": len(data), "mime": row.get("mime_type", ""),
            "width": width, "height": height, "filename_model_markers": markers})
    for item in image_rows:
        owners = sorted(hashes[item["sha256"]]); item["shared_product_count"] = len(owners); item["shared_products"] = owners
        item["media_review_required"] = item["metric_model"] in {"A13JE", "A14JE"} and len(owners) > 1
        item["warnings"] = ";".join((["shared_physical_content"] if len(owners) > 1 else []) +
            (["filename_mentions_other_model"] if any(m != item["metric_model"] for m in item["filename_model_markers"]) else []))
    return image_rows, sheets, known_models


def _visual_status(model, decision):
    if decision == "pending_human_visual_review": return "pending_human_visual_review", False
    if decision == "approve_separate_model_images": return "approved_separate_model_images", True
    approved = decision == "approve_shared_images_for_both" or decision == f"approve_images_for_{model.casefold()}_only"
    return ("approved_by_human_visual_decision" if approved else "rejected_by_human_visual_decision"), approved


def _apply_separate_images(image_rows, approved_images):
    """Validate the closed original associations and return the approved associations."""
    relevant = {model: [row for row in image_rows if row["metric_model"] == model]
        for model in ("A13JE", "A14JE")}
    expected_a13 = set(APPROVED_SEPARATE_IMAGES["A13JE"]["ordered_sha256"])
    expected_a14_own = set(APPROVED_SEPARATE_IMAGES["A14JE"]["ordered_sha256"])
    original = {model: {row["sha256"] for row in rows} for model, rows in relevant.items()}
    if original["A13JE"] != expected_a13 or original["A14JE"] != expected_a13 | expected_a14_own:
        raise RepairError("Asociaciones originales A13JE/A14JE incoherentes con la evidencia aprobada")
    if any(len(rows) != len(original[model]) for model, rows in relevant.items()):
        raise RepairError("Asociaciones originales duplicadas para A13JE/A14JE")
    keep = {model: approved_images[model]["ordered_sha256"] for model in approved_images}
    unaffected = [row.copy() for row in image_rows if row["metric_model"] not in relevant]
    selected = []
    for model in ("A13JE", "A14JE"):
        by_hash = {row["sha256"]: row.copy() for row in relevant[model]}
        if set(keep[model]) - set(by_hash):
            raise RepairError(f"Hash aprobado inexistente o no asociado originalmente a {model}")
        for order, digest in enumerate(keep[model], 1):
            row = by_hash[digest]
            row["association_order"] = str(order)
            row["is_primary"] = digest == approved_images[model]["primary_sha256"]
            row["media_review_required"] = False
            row["warnings"] = ";".join(w for w in row.get("warnings", "").split(";") if w and w != "shared_physical_content")
            selected.append(row)
    if unaffected != [row for row in image_rows if row["metric_model"] not in relevant]:
        raise RepairError("Una imagen de otro producto fue alterada")
    return unaffected + selected


def build_package(plan, media, remaining, decisions, media_root: Path, staging: Path, fetcher=None):
    products = remaining["products"]
    by_model = {r["metric_model"]: r for r in products}
    if len(by_model) != 36 or set(REPAIR_MODELS + ("H625E", "A13JE", "A14JE", "AR24JE", "T38JE")) - set(by_model):
        raise RepairError("La cohorte restante no contiene todos los modelos contractuales")
    corrected = staging / "corrected-media"; corrected.mkdir()
    image_rows, sheet_plan, known_models = _media_associations(products, plan, media, media_root, corrected)
    visual_contract = decisions["shared_image_decisions"]["A13JE|A14JE"]
    if visual_contract["decision"] == "approve_separate_model_images":
        image_rows = _apply_separate_images(image_rows, visual_contract["approved_images"])
    network_urls, network_downloads, redirects, datasheet_rows, conflicts = [], [], 0, [], []
    sheet_hash_owners = {}
    for row in sheet_plan.values():
        if row.get("datasheet_status") == "available_at_source": sheet_hash_owners.setdefault(row.get("sha256"), set()).add(row.get("metric_model"))
    downloaded_hashes = {}
    for product in products:
        model, key = product["metric_model"], product["source_key"]; source = sheet_plan.get(key)
        if not source: raise RepairError("Fila de ficha ausente")
        source_status = source.get("datasheet_status", ""); source_rel = source.get("local_file", "")
        source_hash = source.get("sha256", ""); source_size = int(source.get("size_bytes") or 0)
        status, corrected_rel, corrected_hash, corrected_size = source_status, "", "", ""
        validation, upload, followup, warnings = "not_applicable", False, False, []
        approved_url = ""
        if model in REPAIR_MODELS:
            approved_url = decisions["datasheet_repairs"][model]["datasheet_url"]
            status, followup, validation = "awaiting_approved_datasheet_url", True, "not_downloaded"
            if approved_url:
                network_urls.append(approved_url)
                downloaded = download_datasheet(approved_url, model, known_models, fetcher,
                    decisions["datasheet_repairs"][model]["expected_model_markers"])
                network_downloads.append({"metric_model": model, "url": approved_url,
                    "sha256": downloaded["sha256"], "size_bytes": downloaded["size_bytes"],
                    "redirects_followed": downloaded["redirects"]})
                redirects += downloaded["redirects"]
                if downloaded["sha256"] == source_hash or downloaded["sha256"] in sheet_hash_owners and model not in sheet_hash_owners[downloaded["sha256"]]:
                    raise RepairError(f"Ficha reparada físicamente compartida o no reemplazada: {model}")
                if downloaded["sha256"] in downloaded_hashes and downloaded_hashes[downloaded["sha256"]] != model:
                    raise RepairError("Las dos fichas reparadas comparten contenido físico")
                downloaded_hashes[downloaded["sha256"]] = model
                corrected_rel = f"corrected-media/datasheets/{model}-{downloaded['sha256'][:12]}.pdf"
                destination = staging.joinpath(*PurePosixPath(corrected_rel).parts); destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(downloaded["data"])
                corrected_hash, corrected_size, validation = downloaded["sha256"], downloaded["size_bytes"], downloaded["validation"]
                status = "validated_replacement" if validation == "validated_model_content" else "downloaded_pending_human_content_review"
                upload = validation == "validated_model_content"; followup = not upload
                if followup: warnings.append("human_pdf_content_review_required")
        elif model == "H625E":
            if source_status != "available_at_source" or source_size <= MAX_DATASHEET_BYTES:
                raise RepairError("H625E no cumple la evidencia de tamaño contractual")
            status, validation, followup = "excluded_backend_size_limit", "excluded_backend_size_limit", True
            warnings.append("technical_followup_required")
        elif source_status == "missing_at_source":
            if model not in audit_contract.MISSING_DATASHEETS: raise RepairError("missing_at_source inesperado")
            status, validation, followup = "missing_at_source", "not_available", True
            warnings.append("technical_followup_required")
        else:
            data = read_regular(media_root.joinpath(*PurePosixPath(safe_relative(source_rel)).parts), source_rel)
            if sha(data) != source_hash or len(data) != source_size: raise RepairError("Ficha fuente alterada")
            if source_size > MAX_DATASHEET_BYTES:
                status, validation, followup = "excluded_backend_size_limit", "excluded_backend_size_limit", True
            else:
                corrected_rel = f"corrected-media/datasheets/{source_hash}.pdf"
                destination = staging.joinpath(*PurePosixPath(corrected_rel).parts); destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists(): destination.write_bytes(data)
                corrected_hash, corrected_size, status, validation, upload = source_hash, source_size, "available", "source_contract_preserved", True
        datasheet_rows.append({"metric_model": model, "source_status": source_status, "corrected_status": status,
            "source_relative_path": source_rel, "corrected_relative_path": corrected_rel, "source_sha256": source_hash,
            "corrected_sha256": corrected_hash, "source_size_bytes": source_size or "", "corrected_size_bytes": corrected_size,
            "mime": source.get("mime_type", ""), "model_content_validation": validation,
            "backend_size_compatible": bool(corrected_size and int(corrected_size) <= MAX_DATASHEET_BYTES),
            "datasheet_upload_allowed": upload, "datasheet_followup_required": followup,
            "official_product_page_url": OFFICIAL_PAGES.get(model, ""), "approved_datasheet_url": approved_url,
            "warnings": ";".join(warnings)})
    decision = decisions["shared_image_decisions"]["A13JE|A14JE"]["decision"]
    notes = decisions["shared_image_decisions"]["A13JE|A14JE"]["notes"]
    readiness = []
    sheet_by_model = {r["metric_model"]: r for r in datasheet_rows}
    for product in products:
        model = product["metric_model"]; sheet = sheet_by_model[model]
        media_status, image_ready = ("approved_no_visual_conflict", True)
        if model in {"A13JE", "A14JE"}: media_status, image_ready = _visual_status(model, decision)
        blocking = []
        if not image_ready: blocking.append("visual_media_decision")
        if model in REPAIR_MODELS and sheet["corrected_status"] != "validated_replacement": blocking.append("datasheet_repair")
        ready = not blocking
        readiness.append({"metric_model": model, "approval_key": product.get("approval_key", ""),
            "approved_family": product.get("proposed_target_subcategory", ""), "approved_name": product.get("proposed_target_name", ""),
            "product_data_approval_status": "approved_6_families_36_names", "image_status": "available",
            "datasheet_status": sheet["corrected_status"], "media_approval_status": media_status,
            "technical_followup_required": sheet["datasheet_followup_required"],
            "datasheet_followup_required": sheet["datasheet_followup_required"],
            "ready_for_controlled_import": ready, "blocking_reasons": ";".join(blocking), "warnings": sheet["warnings"]})
    complete = all(sheet_by_model[m]["corrected_status"] == "validated_replacement" for m in REPAIR_MODELS) and decision != "pending_human_visual_review"
    verdict = "REPAIR_COMPLETE" if complete else "REVIEW_REQUIRED"
    return {"products": products, "images": image_rows, "datasheets": datasheet_rows, "readiness": readiness,
        "conflicts": conflicts, "verdict": verdict, "network_urls": network_urls,
        "network_downloads": network_downloads, "redirects": redirects,
        "visual_decision": decision, "visual_notes": notes}


def _write_visual(staging: Path, result):
    rows = []
    for item in result["images"]:
        if item["metric_model"] not in {"A13JE", "A14JE"}: continue
        other = "A14JE" if item["metric_model"] == "A13JE" else "A13JE"
        disposition = ("Imágenes conservadas para A13JE" if item["metric_model"] == "A13JE" else
            "Imágenes propias conservadas para A14JE")
        if item["metric_model"] == "A14JE" and item["is_primary"]:
            disposition = "Nueva imagen principal de A14JE"
        rows.append({"product_model": item["metric_model"], "other_product_model": other,
            "association_order": item["association_order"], "is_primary": item["is_primary"], "relative_path": item["relative_path"],
            "original_filename": item["original_filename"], "sha256": item["sha256"], "size_bytes": item["size_bytes"],
            "mime": item["mime"], "width": item["width"], "height": item["height"],
            "shared_physical_content": other in item["shared_products"],
            "filename_mentions_other_model": other in item["filename_model_markers"],
            "disposition": disposition, "human_decision": result["visual_decision"], "human_notes": result["visual_notes"]})
    if result["visual_decision"] == "approve_separate_model_images":
        by_hash = {row["sha256"]: row for row in rows if row["product_model"] == "A13JE"}
        for digest in APPROVED_SEPARATE_IMAGES["A13JE"]["ordered_sha256"]:
            source = dict(by_hash[digest])
            source.update({"product_model": "A14JE", "other_product_model": "A13JE",
                "is_primary": False, "disposition": "Imágenes retiradas de A14JE"})
            rows.append(source)
    fields = tuple(rows[0]) if rows else ("product_model", "other_product_model", "association_order", "is_primary", "relative_path", "original_filename", "sha256", "size_bytes", "mime", "width", "height", "shared_physical_content", "filename_mentions_other_model", "human_decision", "human_notes")
    write_csv(staging / "A13JE-A14JE-visual-review.csv", fields, rows)
    products = {r["metric_model"]: r for r in result["products"]}
    cards = []
    for row in rows:
        cards.append(f'''<article><h2>{escape(row['disposition'])}</h2><h3>{escape(row['product_model'])} — {'PRINCIPAL' if row['is_primary'] else 'adicional'}</h3>
<img src="{escape(row['relative_path'])}" alt="Evidencia sin interpretación de {escape(row['product_model'])}">
<dl><dt>Nombre aprobado</dt><dd>{escape(products[row['product_model']].get('proposed_target_name',''))}</dd>
<dt>Categoría</dt><dd>{escape(products[row['product_model']].get('proposed_target_subcategory',''))}</dd>
<dt>Ruta relativa</dt><dd>{escape(row['relative_path'])}</dd><dt>Nombre original</dt><dd>{escape(row['original_filename'])}</dd>
<dt>SHA-256</dt><dd>{row['sha256']}</dd><dt>Tamaño/MIME/dimensiones</dt><dd>{row['size_bytes']} · {escape(row['mime'])} · {row['width']}×{row['height']}</dd>
<dt>Contenido compartido</dt><dd>{row['shared_physical_content']}</dd><dt>Nombre menciona otro modelo</dt><dd>{row['filename_mentions_other_model']}</dd></dl></article>''')
    html = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Revisión humana A13JE/A14JE</title>
<style>body{{font-family:sans-serif;max-width:1100px;margin:auto;padding:2rem}}.warning{{border:3px solid #a50;padding:1rem}}article{{border:1px solid #888;padding:1rem;margin:1rem 0}}img{{max-width:100%;max-height:600px}}dt{{font-weight:bold}}dd{{overflow-wrap:anywhere}}</style></head>
<body><h1>Revisión visual humana A13JE / A14JE</h1><p class="warning">No se realizó OCR, visión artificial ni reconocimiento del equipo. Compare manualmente estas evidencias con las páginas oficiales.</p>
<p>A13JE: <a href="{OFFICIAL_PAGES['A13JE']}">{OFFICIAL_PAGES['A13JE']}</a><br>A14JE: <a href="{OFFICIAL_PAGES['A14JE']}">{OFFICIAL_PAGES['A14JE']}</a></p>
{''.join(cards)}<section><h2>Decisión humana posterior</h2><p>Decisión actual: {escape(result['visual_decision'])}</p><p>Notas: {escape(result['visual_notes'])}</p></section></body></html>'''
    (staging / "A13JE-A14JE-visual-review.html").write_text(html, encoding="utf-8")


def _finish_outputs(staging, result, plan, media, remaining, decisions_raw, created_at):
    ds_fields = ("metric_model", "source_status", "corrected_status", "source_relative_path", "corrected_relative_path", "source_sha256", "corrected_sha256", "source_size_bytes", "corrected_size_bytes", "mime", "model_content_validation", "backend_size_compatible", "datasheet_upload_allowed", "datasheet_followup_required", "official_product_page_url", "approved_datasheet_url", "warnings")
    image_fields = ("metric_model", "association_order", "is_primary", "relative_path", "original_filename", "sha256", "size_bytes", "mime", "width", "height", "shared_product_count", "shared_products", "filename_model_markers", "media_review_required", "warnings")
    ready_fields = ("metric_model", "approval_key", "approved_family", "approved_name", "product_data_approval_status", "image_status", "datasheet_status", "media_approval_status", "technical_followup_required", "datasheet_followup_required", "ready_for_controlled_import", "blocking_reasons", "warnings")
    conflict_fields = ("metric_model", "conflict_code", "detail", "blocking")
    write_csv(staging / "repair-datasheets.csv", ds_fields, result["datasheets"])
    write_csv(staging / "repair-images.csv", image_fields, result["images"])
    write_csv(staging / "controlled-import-readiness.csv", ready_fields, result["readiness"])
    write_csv(staging / "repair-conflicts.csv", conflict_fields, result["conflicts"])
    _write_visual(staging, result)
    physical = []
    for path in sorted((staging / "corrected-media").rglob("*")):
        if path.is_file():
            data = path.read_bytes(); physical.append({"name": path.relative_to(staging / "corrected-media").as_posix(), "sha256": sha(data), "size": len(data)})
    internal = {"tool": TOOL_NAME, "version": TOOL_VERSION, "files": physical}
    (staging / "corrected-media" / "manifest.json").write_text(json.dumps(internal, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fingerprint_payload = {"plan": plan["fingerprint"], "media": media["fingerprint"], "remaining": remaining["fingerprint"],
        "remaining_input": remaining["input_fingerprint"], "decisions": sha(decisions_raw), "readiness": result["readiness"],
        "images": [{k: r[k] for k in ("metric_model", "sha256", "is_primary")} for r in result["images"]],
        "datasheets": [{k: r[k] for k in ("metric_model", "corrected_status", "corrected_sha256")} for r in result["datasheets"]],
        "visual_decision": result["visual_decision"]}
    repaired_fp = sha(canonical(fingerprint_payload))
    summary = {"verdict": result["verdict"], "remaining_products": 36, "remaining_families": 6,
        "catalog_families_approved": True, "catalog_names_approved": 36,
        "ready_for_controlled_import": sum(bool(r["ready_for_controlled_import"]) for r in result["readiness"]),
        "human_review_required": result["verdict"] == "REVIEW_REQUIRED"}
    (staging / "repair-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (staging / "repair-summary.txt").write_text(f"{result['verdict']}\n36 productos restantes; aprobación comercial registrada separadamente de la aprobación de medios.\n", encoding="utf-8")
    (staging / "README-repaired-media.txt").write_text("Paquete nuevo de medios LGMG para revisión e importación completa controlada futura. No importa, publica ni carga productos o medios.\n", encoding="utf-8")
    input_files = []
    for package, raw in (("plan", plan["raw"]), ("media", media["raw"]), ("remaining_audit", remaining["raw"])):
        input_files.extend({"package": package, "name": name, "sha256": sha(data), "size": len(data)} for name, data in sorted(raw.items()))
    input_files.append({"package": "decisions", "name": "decisions-input", "sha256": sha(decisions_raw), "size": len(decisions_raw)})
    outputs = []
    for path in sorted(staging.rglob("*")):
        if path.is_file() and path.name != "repair-manifest.json":
            data = path.read_bytes(); outputs.append({"name": path.relative_to(staging).as_posix(), "sha256": sha(data), "size": len(data)})
    manifest = {**summary, "tool": TOOL_NAME, "version": TOOL_VERSION, "created_at_utc": created_at,
        "approved_plan_fingerprint": plan["fingerprint"], "approved_media_fingerprint": media["fingerprint"],
        "remaining_catalog_fingerprint_sha256": remaining["fingerprint"],
        "remaining_audit_input_fingerprint_sha256": remaining["input_fingerprint"], "decisions_input_sha256": sha(decisions_raw),
        "repaired_media_fingerprint_sha256": repaired_fp, "input_files": input_files, "output_files": outputs,
        "total_plan_products": 57, "processed_closed_cohort": 21, "network_called": bool(result["network_urls"]),
        "network_request_count": len(result["network_urls"]), "network_requested_urls": result["network_urls"],
        "network_downloads": result["network_downloads"],
        "network_redirects_followed": result["redirects"], "api_called": False, "database_modified": False,
        "products_created": 0, "products_updated": 0, "products_deleted": 0, "images_uploaded": 0,
        "datasheets_uploaded": 0, "content_published": False, "credentials_persisted": False, "apply_supported": False}
    (staging / "repair-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if {p.name for p in staging.iterdir()} != set(OUTPUT_NAMES): raise RepairError("Conjunto exacto de salida incompleto")


def run(plan_input: Path, media_input: Path, remaining_audit_input: Path, decisions_input: Path, output_dir: Path, *, created_at=None, fetcher=None):
    safe_paths(plan_input, media_input, remaining_audit_input, decisions_input, output_dir)
    decisions_raw = read_regular(decisions_input, "decisions-input"); decisions = validate_decisions(decisions_raw)
    try:
        plan, media = audit_contract.validate_inputs(plan_input, media_input)
    except audit_contract.AuditError as exc:
        raise RepairError(str(exc)) from exc
    remaining = validate_remaining_audit(remaining_audit_input, plan["fingerprint"], media["fingerprint"])
    staging = Path(tempfile.mkdtemp(prefix=".lgmg-repair-staging-", dir=output_dir.parent))
    try:
        result = build_package(plan, media, remaining, decisions, media_input, staging, fetcher)
        _finish_outputs(staging, result, plan, media, remaining, decisions_raw, created_at or datetime.now(timezone.utc).isoformat())
        if output_dir.exists(): output_dir.rmdir()
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Repara y reaudita los medios de los 36 productos LGMG restantes")
    parser.add_argument("--plan-input", required=True)
    parser.add_argument("--media-input", required=True)
    parser.add_argument("--remaining-audit-input", required=True)
    parser.add_argument("--decisions-input", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run(Path(args.plan_input), Path(args.media_input), Path(args.remaining_audit_input), Path(args.decisions_input), Path(args.output_dir))
        print(result["verdict"]); return 0
    except (RepairError, OSError) as exc:
        print(f"CONFLICT: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
