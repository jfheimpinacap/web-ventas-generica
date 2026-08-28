#!/usr/bin/env python3
"""Create a deterministic, offline human-review package from LGMG results."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

from extract_lgmg import canonical_url

TOOL_VERSION = "1.0.0"
TOOL_NAME = "lgmg-jem-review-preparer"
REQUIRED = (
    "manifest.json", "catalog.json", "catalog.csv", "review.csv",
    "discovery.csv", "discovery.json", "families.csv", "errors.json",
)
OUTPUTS = (
    "review-products.csv", "review-specifications.csv", "review-images.csv",
    "review-datasheets.csv", "review-missing-datasheets.csv",
    "review-categories.csv", "review-uncertain.csv", "jem-review-drafts.json",
    "review-summary.json", "review-summary.txt", "README-review.txt",
)
MAX_MEMBERS = 10000
MAX_SELECTED_FILE = 64 * 1024 * 1024
MAX_SELECTED_TOTAL = 128 * 1024 * 1024


class ReviewInputError(ValueError):
    """A fail-closed input error whose message contains no machine path."""


def stable_source_key(url: str) -> str:
    safe = canonical_url(url)
    return "lgmg-" + hashlib.sha256(safe.encode("utf-8")).hexdigest()[:16]


def _safe_member(name: str) -> str:
    if not name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ReviewInputError("ZIP con nombre vacío o caracteres de control")
    value = name.replace("\\", "/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ReviewInputError("ZIP con ruta absoluta o letra de unidad")
    trailing = value.endswith("/")
    parts = value[:-1].split("/") if trailing else value.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ReviewInputError("ZIP con traversal o segmentos anómalos")
    return "/".join(parts) + ("/" if trailing else "")


def _zip_type(info: zipfile.ZipInfo) -> None:
    if info.flag_bits & 1:
        raise ReviewInputError("ZIP cifrado no admitido")
    mode = info.external_attr >> 16
    kind = stat.S_IFMT(mode)
    if kind and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise ReviewInputError("ZIP con enlace o tipo especial no admitido")


def _read_zip(path: Path) -> dict[str, bytes]:
    selected: dict[str, zipfile.ZipInfo] = {}
    roots: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ReviewInputError("ZIP excede el límite de miembros")
        normalized: set[str] = set()
        for info in infos:
            name = _safe_member(info.filename)
            if name in normalized:
                raise ReviewInputError("ZIP contiene nombres duplicados tras normalizar")
            normalized.add(name); _zip_type(info)
            parts = PurePosixPath(name.rstrip("/")).parts
            for index, part in enumerate(parts):
                if part == "resultado": roots.add("/".join(parts[:index + 1]))
        if len(roots) != 1:
            raise ReviewInputError("Se exige exactamente un directorio resultado")
        root = next(iter(roots))
        for leaf in REQUIRED:
            target = f"{root}/{leaf}"
            matches = [i for i in infos if _safe_member(i.filename) == target]
            if len(matches) != 1:
                raise ReviewInputError(f"Archivo obligatorio ausente o duplicado: {leaf}")
            if matches[0].file_size > MAX_SELECTED_FILE:
                raise ReviewInputError(f"Archivo obligatorio demasiado grande: {leaf}")
            selected[leaf] = matches[0]
        if sum(i.file_size for i in selected.values()) > MAX_SELECTED_TOTAL:
            raise ReviewInputError("Archivos seleccionados exceden el límite combinado")
        return {leaf: archive.read(info) for leaf, info in selected.items()}


def _read_folder(path: Path) -> dict[str, bytes]:
    if path.name == "resultado":
        roots = [path]
    else:
        roots = [item for item in path.iterdir() if item.name == "resultado" and item.is_dir() and not item.is_symlink()]
    if len(roots) != 1 or roots[0].is_symlink():
        raise ReviewInputError("Se exige exactamente un directorio resultado seguro")
    root = roots[0]
    data = {}
    total = 0
    for leaf in REQUIRED:
        item = root / leaf
        if not item.is_file() or item.is_symlink():
            raise ReviewInputError(f"Archivo obligatorio ausente o inseguro: {leaf}")
        size = item.stat().st_size
        if size > MAX_SELECTED_FILE:
            raise ReviewInputError(f"Archivo obligatorio demasiado grande: {leaf}")
        total += size
        if total > MAX_SELECTED_TOTAL:
            raise ReviewInputError("Archivos seleccionados exceden el límite combinado")
        data[leaf] = item.read_bytes()
    return data


def read_input(path: Path) -> tuple[dict[str, bytes], str]:
    if path.is_symlink(): raise ReviewInputError("La entrada no puede ser un enlace simbólico")
    if path.is_file() and path.suffix.casefold() == ".zip": return _read_zip(path), "zip"
    if path.is_dir(): return _read_folder(path), "folder"
    raise ReviewInputError("La entrada debe ser una carpeta o un ZIP")


def _decode_json(data: bytes, name: str):
    try: return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewInputError(f"JSON inválido: {name}") from exc


def _csv_rows(data: bytes, name: str) -> list[dict[str, str]]:
    try: text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise ReviewInputError(f"CSV inválido: {name}") from exc
    return list(csv.DictReader(text.splitlines()))


def _useful(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if any((value or "").strip() for value in row.values())]


def validate_input(raw: dict[str, bytes]) -> dict:
    manifest = _decode_json(raw["manifest.json"], "manifest.json")
    catalog = _decode_json(raw["catalog.json"], "catalog.json")
    errors = _decode_json(raw["errors.json"], "errors.json")
    discovery_json = _decode_json(raw["discovery.json"], "discovery.json")
    review = _useful(_csv_rows(raw["review.csv"], "review.csv"))
    discovery = _useful(_csv_rows(raw["discovery.csv"], "discovery.csv"))
    if not isinstance(manifest, dict) or manifest.get("tool") != "lgmg-catalog-extractor" or not manifest.get("version"):
        raise ReviewInputError("Manifest de origen no reconocido")
    if not isinstance(catalog, list) or not isinstance(errors, list):
        raise ReviewInputError("catalog.json y errors.json deben ser arreglos")
    if errors: raise ReviewInputError("La extracción contiene errores")
    checks = (("processed_count", len(catalog)), ("needs_review_count", len(review)))
    if any(manifest.get(key) != expected for key, expected in checks):
        raise ReviewInputError("Contadores del manifest inconsistentes")
    if manifest.get("electric_confirmed") != len(catalog):
        raise ReviewInputError("La entrada no es coherente con una extracción --electric-only")
    discovered = [row.get("url", "") for row in discovery if row.get("status") == "accepted"]
    declared = manifest.get("detail_urls_unique", manifest.get("discovered_count"))
    if declared is not None and declared != len(set(discovered)):
        raise ReviewInputError("URLs de discovery.csv inconsistentes")
    seen_urls, seen_keys = set(), set()
    for product in catalog:
        if not isinstance(product, dict) or product.get("is_electric") is not True or product.get("needs_review") is True:
            raise ReviewInputError("El catálogo contiene un producto no confirmado")
        source = product.get("source_url")
        canonical = canonical_url(product.get("canonical_url") or source)
        source = canonical_url(source)
        if source not in set(discovered):
            raise ReviewInputError("El catálogo contiene una URL no listada en discovery.csv")
        key = stable_source_key(canonical)
        if source in seen_urls or key in seen_keys: raise ReviewInputError("URL o clave estable duplicada")
        seen_urls.add(source); seen_keys.add(key)
        model = product.get("metric_model")
        if not model or re.search(r"pro-detail-[^/]*" + re.escape(str(model)), source, re.I):
            raise ReviewInputError("Modelo ausente o potencialmente fabricado desde la URL")
        for asset in list(product.get("images") or []) + list(product.get("datasheets") or []):
            canonical_url(asset.get("url", ""), page=False)
    return {"manifest": manifest, "catalog": catalog, "review": review,
            "discovery": discovery, "discovery_json": discovery_json}


def _excel(value):
    if value is None: return ""
    if isinstance(value, bool): return str(value).lower()
    if isinstance(value, (list, dict)): value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")): return "'" + text
    return text


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows({key: _excel(row.get(key)) for key in fields} for row in rows)


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _spec_rows(product: dict, key: str) -> list[dict]:
    rows = []
    for order, spec in enumerate(product.get("specifications") or [], 1):
        rows.append({"source_key": key, "metric_model": product["metric_model"], "group_order": 1,
            "group_name": "", "specification_order": order, "source_label": spec.get("name_original", ""),
            "source_value": spec.get("value_metric", ""), "normalized_label": "", "normalized_value": "",
            "unit": "", "requires_review": bool(spec.get("needs_review") or not spec.get("normalized_key"))})
    return rows


def build_package(validated: dict) -> tuple[dict[str, tuple[list[str], list[dict]]], dict, list[dict], str]:
    products, specs, images, sheets, missing, drafts = [], [], [], [], [], []
    categories: dict[str, int] = {}
    for product in validated["catalog"]:
        source_url = canonical_url(product["source_url"]); canon = canonical_url(product.get("canonical_url") or source_url)
        key = stable_source_key(canon); metric = product["metric_model"]; imperial = product.get("imperial_model") or ""
        aliases = product.get("model_aliases") or []; category = product.get("source_category") or ""
        categories[category] = categories.get(category, 0) + 1
        product_specs = _spec_rows(product, key); specs.extend(product_specs)
        product_images = []
        for order, image in enumerate(product.get("images") or [], 1):
            row = {"source_key": key, "metric_model": metric, "image_order": order,
                "source_url": canonical_url(image["url"], page=False), "suggested_alt": product.get("display_name_suggestion", ""),
                "primary_candidate": order == 1, "rights_status": "pending_confirmation", "download_status": "not_downloaded",
                "local_file": "", "review_decision": ""}
            images.append(row); product_images.append(row.copy())
        product_sheets = []
        for order, sheet in enumerate(product.get("datasheets") or [], 1):
            row = {"source_key": key, "metric_model": metric, "datasheet_order": order,
                "source_url": canonical_url(sheet["url"], page=False), "rights_status": "pending_confirmation",
                "download_status": "not_downloaded", "local_file": "", "review_decision": ""}
            sheets.append(row); product_sheets.append(row.copy())
        if not product_sheets:
            missing.append({"source_key": key, "metric_model": metric, "imperial_model": imperial,
                "suggested_name": product.get("display_name_suggestion", ""), "source_category": category,
                "source_url": source_url, "reason": "No se identificó una ficha técnica para este modelo"})
        source_draft = product.get("jem_nexus_draft") or {}
        blocking = ["human_review_required", "category_mapping_required", "media_rights_confirmation_required"]
        if not product_sheets: blocking.append("datasheet_missing")
        draft = {"source_key": key, "source": {"manufacturer": product.get("manufacturer") or "LGMG",
            "source_url": source_url, "canonical_url": canon, "metric_model": metric, "imperial_model": imperial,
            "model_aliases": aliases, "source_category": category, "model_evidence": product.get("model_evidence") or [],
            "warnings": product.get("warnings") or [], "translation_issues": product.get("translation_issues") or [],
            "missing_fields": product.get("missing_fields") or []}, "review_state": "pending", "ready_for_import": False,
            "blocking_reasons": blocking, "product_draft": {"suggested_name": source_draft.get("name") or product.get("display_name_suggestion"),
                "brand": "LGMG", "model": metric, "imperial_model_for_review": imperial, "product_type": "machinery",
                "condition": "new", "stock_status": source_draft.get("stock_status") if source_draft.get("stock_status") == "on_request" else None,
                "price": None, "currency": None, "show_price": False, "published": False, "featured": False,
                "category": None, "technical_sheet": None}, "specifications": product_specs,
            "media": {"images": product_images, "datasheets": product_sheets}}
        drafts.append(draft)
        products.append({"selection": "", "review_state": "pending", "source_key": key, "metric_model": metric,
            "imperial_model": imperial, "model_aliases": aliases, "suggested_name": product.get("display_name_suggestion", ""),
            "approved_name": "", "source_category": category, "suggested_category": category, "approved_category": "",
            "brand": "LGMG", "product_type": "machinery", "condition": "new", "stock_status": source_draft.get("stock_status") or "on_request",
            "price": "", "currency": "", "show_price": False, "published": False, "featured": False,
            "specifications_count": len(product_specs), "image_count": len(product_images), "datasheet_count": len(product_sheets),
            "datasheet_missing": not product_sheets, "source_url": source_url, "canonical_url": canon,
            "warnings": product.get("warnings") or [], "translation_issues": product.get("translation_issues") or [],
            "missing_fields": product.get("missing_fields") or [], "ready_for_import": False})
    category_rows = [{"source_category": name, "confirmed_product_count": count, "suggested_jem_category": name,
        "approved_jem_category": "", "jem_category_id": "", "requires_mapping": True} for name, count in categories.items()]
    uncertain = [{"metric_model": row.get("metric_model", ""), "imperial_model": row.get("imperial_model", ""),
        "display_name_suggestion": row.get("display_name_suggestion", ""), "source_category": row.get("source_category", ""),
        "source_url": row.get("source_url", ""), "electric_evidence": row.get("electric_evidence", ""),
        "warnings": row.get("warnings", ""), "missing_fields": row.get("missing_fields", ""), "review_decision": ""}
        for row in validated["review"]]
    fields = {
        "review-products.csv": "selection review_state source_key metric_model imperial_model model_aliases suggested_name approved_name source_category suggested_category approved_category brand product_type condition stock_status price currency show_price published featured specifications_count image_count datasheet_count datasheet_missing source_url canonical_url warnings translation_issues missing_fields ready_for_import".split(),
        "review-specifications.csv": "source_key metric_model group_order group_name specification_order source_label source_value normalized_label normalized_value unit requires_review".split(),
        "review-images.csv": "source_key metric_model image_order source_url suggested_alt primary_candidate rights_status download_status local_file review_decision".split(),
        "review-datasheets.csv": "source_key metric_model datasheet_order source_url rights_status download_status local_file review_decision".split(),
        "review-missing-datasheets.csv": "source_key metric_model imperial_model suggested_name source_category source_url reason".split(),
        "review-categories.csv": "source_category confirmed_product_count suggested_jem_category approved_jem_category jem_category_id requires_mapping".split(),
        "review-uncertain.csv": "metric_model imperial_model display_name_suggestion source_category source_url electric_evidence warnings missing_fields review_decision".split(),
    }
    csvs = {name: (fields[name], rows) for name, rows in zip(fields, (products, specs, images, sheets, missing, category_rows, uncertain))}
    manifest = validated["manifest"]
    summary = {"source": manifest["tool"], "source_version": manifest["version"],
        "products_discovered": manifest.get("discovered_count", manifest.get("detail_urls_unique", len(products))),
        "electric_confirmed": len(products), "combustion_excluded": manifest.get("non_electric_skipped", 0),
        "classification_uncertain": len(uncertain), "products_in_review": len(products), "categories": len(category_rows),
        "specifications": len(specs), "image_references": len(images), "products_with_images": sum(bool(d["media"]["images"]) for d in drafts),
        "datasheet_references": len(sheets), "products_with_datasheets": len(products) - len(missing),
        "products_without_datasheets": len(missing), "products_ready_for_import": 0, "downloads_performed": 0,
        "jem_nexus_calls": 0, "products_imported": 0, "content_published": False}
    return csvs, summary, drafts, _readme(summary)


def _readme(summary: dict) -> str:
    return ("PAQUETE LOCAL DE REVISIÓN LGMG PARA JEM NEXUS\n\n"
        "Los CSV separan productos, especificaciones, imágenes, fichas técnicas, faltantes, categorías e inciertos. "
        "jem-review-drafts.json contiene borradores bloqueados; los resúmenes y el manifest documentan procedencia y conteos.\n\n"
        "Complete selection, approved_name, approved_category, review_decision y jem_category_id únicamente tras revisión humana. "
        "Las imágenes y PDF son referencias remotas: no se descargaron y sus derechos siguen pendientes. Ningún borrador está aprobado, "
        "listo para importar ni publicar. No importe ni publique todavía.\n\n"
        f"Los {summary['classification_uncertain']} inciertos requieren revisión separada y no fueron clasificados. Todas las categorías deben "
        f"mapearse en JEM Nexus. Los {summary['products_without_datasheets']} productos sin PDF no deben recibir una ficha de otro modelo. "
        "Los CSV usan UTF-8 con BOM y pueden abrirse con Excel.\n")


def _summary_text(summary: dict) -> str:
    labels = {"products_discovered":"Productos descubiertos", "electric_confirmed":"Eléctricos confirmados",
        "combustion_excluded":"Combustión excluidos", "classification_uncertain":"Clasificación incierta",
        "products_in_review":"Productos en revisión", "categories":"Categorías", "specifications":"Especificaciones",
        "image_references":"Referencias de imagen", "products_with_images":"Productos con imagen",
        "datasheet_references":"Referencias de ficha técnica", "products_with_datasheets":"Productos con ficha técnica",
        "products_without_datasheets":"Productos sin ficha técnica", "products_ready_for_import":"Listos para importar",
        "downloads_performed":"Descargas", "jem_nexus_calls":"Llamadas a JEM Nexus", "products_imported":"Importados",
        "content_published":"Contenido publicado"}
    return f"Fuente: {summary['source']} {summary['source_version']}\n" + "".join(f"{labels[k]}: {str(summary[k]).lower() if isinstance(summary[k], bool) else summary[k]}\n" for k in labels)


def _fingerprint(raw: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in REQUIRED: digest.update(name.encode()); digest.update(b"\0"); digest.update(raw[name])
    return digest.hexdigest()


def write_package(output: Path, raw: dict[str, bytes], input_type: str, validated: dict) -> None:
    csvs, summary, drafts, readme = build_package(validated)
    for name, (fields, rows) in csvs.items(): _write_csv(output / name, fields, rows)
    _write_json(output / "jem-review-drafts.json", drafts)
    _write_json(output / "review-summary.json", summary)
    (output / "review-summary.txt").write_text(_summary_text(summary), encoding="utf-8", newline="\n")
    (output / "README-review.txt").write_text(readme, encoding="utf-8", newline="\n")
    generated = []
    for name in OUTPUTS:
        data = (output / name).read_bytes()
        generated.append({"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    package_manifest = {"tool": TOOL_NAME, "version": TOOL_VERSION, "source_extractor_version": validated["manifest"]["version"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "input_type": input_type, "input_fingerprint_sha256": _fingerprint(raw),
        "counts": summary, "generated_files": generated, "network_used": False, "images_downloaded": 0,
        "datasheets_downloaded": 0, "jem_nexus_called": False, "products_imported": 0, "content_published": False,
        "all_drafts_ready_for_import": False}
    _write_json(output / "review-manifest.json", package_manifest)


def _safe_paths(input_path: Path, output: Path) -> None:
    home = Path.home().resolve(); resolved_input = input_path.resolve(); resolved_output = output.resolve(strict=False)
    forbidden = {Path(resolved_output.anchor), home}
    if resolved_output in forbidden or len(resolved_output.parts) < 3: raise ReviewInputError("Salida demasiado amplia")
    if resolved_input == resolved_output: raise ReviewInputError("Entrada y salida no pueden coincidir")
    if input_path.is_dir() and resolved_input in resolved_output.parents: raise ReviewInputError("La salida no puede quedar dentro de la entrada")
    current = resolved_output
    while not current.exists() and current != current.parent: current = current.parent
    if current.is_symlink() or (output.exists() and output.is_symlink()): raise ReviewInputError("Salida mediante symlink no admitida")
    if output.exists() and (not output.is_dir() or any(output.iterdir())): raise ReviewInputError("La salida debe ser nueva o estar vacía")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepara offline un paquete local de revisión LGMG")
    parser.add_argument("--input", required=True); parser.add_argument("--output-dir", required=True)
    return parser


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv); input_path = Path(args.input); output = Path(args.output_dir)
        _safe_paths(input_path, output); raw, input_type = read_input(input_path); validated = validate_input(raw)
        output.mkdir(parents=True, exist_ok=True); write_package(output, raw, input_type, validated)
        return 0
    except (ReviewInputError, ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"Error: {str(exc).splitlines()[0]}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
