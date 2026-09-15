from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .models import read_model_aliases
from .paths import BRANDS, safe_path
from .reports import INVENTORY_FIELDS, PENDING_FIELDS, write_csv, write_json
from .sources import read_sources
from .validation import detect_binary


def _plain(value: str) -> str:
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return re.sub(r"[\s_-]+", "-", value.casefold()).strip("-")


def _brand_and_location(relative: Path) -> tuple[str, str]:
    if not relative.parts:
        return "", "unmanaged"
    brand = relative.parts[0].upper()
    if brand not in BRANDS:
        return "", "unmanaged"
    folder = relative.parts[1] if len(relative.parts) > 2 else ""
    canonical = {f"Imagenes modelos {brand}", f"fichas-tecnicas {brand}"}
    return brand, "canonical" if folder in canonical else "legacy"


def _canonical_tail(brand: str, stem: str) -> str:
    for prefix in (f"Ficha-tecnica-{brand}-", f"Ficha-técnica-{brand}-", f"{brand}-"):
        if stem.casefold().startswith(prefix.casefold()):
            return stem[len(prefix):]
    return ""


def _tokens(stem: str) -> list[str]:
    return [x.upper() for x in re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", unicodedata.normalize("NFKD", stem))]


def _exact_in_stem(stem: str, value: str) -> bool:
    pieces = [re.escape(piece) for piece in re.findall(r"[A-Za-z0-9]+", value)]
    if not pieces:
        return False
    expression = r"(?<![A-Za-z0-9])" + r"[\s_-]*".join(pieces) + r"(?![A-Za-z0-9])"
    return re.search(expression, stem, re.IGNORECASE) is not None


def _known_models(root: Path, files: list[Path], aliases) -> dict[str, set[str]]:
    known = {brand: set() for brand in BRANDS}
    source_path = safe_path(root, "_control/fuentes.csv")
    if source_path.exists():
        for source in read_sources(source_path):
            if source.model:
                known[source.target_brand].add(source.model)
    manifest_path = safe_path(root, "_control/manifest.json")
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("manifest corrupto") from error
        for item in manifest.get("associations", []):
            brand, model = str(item.get("brand", "")).upper(), str(item.get("model", "")).strip()
            if not brand and item.get("path"):
                brand = str(item["path"]).split("/", 1)[0].upper()
            if brand in known and model:
                known[brand].add(model)
    for alias in aliases:
        known[alias.brand].add(alias.canonical_model)
    for path in files:
        relative = path.relative_to(root)
        brand, location = _brand_and_location(relative)
        tail = _canonical_tail(brand, path.stem) if brand else ""
        if location == "canonical" and tail and re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]+", tail):
            known[brand].add(tail)
    return known


def _associate(brand: str, stem: str, known: set[str], aliases) -> tuple[str, str, str]:
    if not brand:
        return "", "unresolved", "MODEL_UNKNOWN"
    for alias in aliases:
        if alias.brand == brand and _exact_in_stem(stem, alias.alias):
            return alias.canonical_model, "manual_alias", "CLASSIFIED"
    tail = _canonical_tail(brand, stem)
    candidates: set[str] = set()
    if tail:
        candidates.update(model for model in known if _plain(model) == _plain(tail))
        # A trailing number can be either part of a model or a stable file position.
        stripped = re.sub(r"-\d+$", "", tail)
        candidates.update(model for model in known if _plain(model) == _plain(stripped))
        if len(candidates) == 1:
            return next(iter(candidates)), "canonical_filename", "CLASSIFIED"
        if len(candidates) > 1:
            return "", "unresolved", "MODEL_AMBIGUOUS"
        if tail and re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]+", tail):
            return tail, "canonical_filename", "CLASSIFIED"
    matches = {model for model in known if _exact_in_stem(stem, model)}
    if len(matches) == 1:
        return next(iter(matches)), "exact_model_match", "CLASSIFIED"
    if len(matches) > 1:
        longest = max(len(_plain(model)) for model in matches)
        finalists = {model for model in matches if len(_plain(model)) == longest}
        if len(finalists) == 1:
            return next(iter(finalists)), "exact_model_match", "CLASSIFIED"
        return "", "unresolved", "MODEL_AMBIGUOUS"
    return "", "unresolved", "MODEL_UNKNOWN"


def scan(root: Path, write: bool = True) -> tuple[list[dict], list[dict]]:
    root = root.resolve()
    excluded = {"inventario.csv", "pendientes-revision.csv", "fuentes.csv", "modelos.csv", "checksums.csv"}
    files = sorted((p for p in root.rglob("*") if p.is_file() and not p.is_symlink()
                    and p.name not in excluded and "_control" not in p.relative_to(root).parts),
                   key=lambda p: p.relative_to(root).as_posix().casefold())
    aliases = read_model_aliases(safe_path(root, "_control/modelos.csv"))
    known = _known_models(root, files, aliases)
    rows, pending, first_by_hash = [], [], {}
    for path in files:
        relative, data = path.relative_to(root), path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        brand, location = _brand_and_location(relative)
        model, method, classification = _associate(brand, path.stem, known.get(brand, set()), aliases)
        integrity, observation, info = "VALID", "", None
        try:
            info = detect_binary(data)
        except ValueError:
            integrity, observation = "INVALID_BINARY", "firma binaria no admitida o truncada"
        if info and path.suffix.lower() != info.extension and not (path.suffix.lower() == ".jpeg" and info.extension == ".jpg"):
            integrity, observation = "MIME_CONFLICT", "extensión no coincide con el contenido"
        duplicate_of = first_by_hash.get(digest)
        if duplicate_of:
            classification = "DUPLICATE" if classification == "CLASSIFIED" else classification
            observation = f"duplica {duplicate_of}"
        else:
            first_by_hash[digest] = relative.as_posix()
        state = integrity if integrity != "VALID" else ("VALID" if classification == "CLASSIFIED" else classification)
        row = {field: "" for field in INVENTORY_FIELDS}
        row.update(marca=brand, modelo=model, tipo=info.kind if info else "", archivo=path.name,
                   ruta_relativa=relative.as_posix(), ubicacion=location, metodo_asociacion=method,
                   estado_integridad=integrity, estado_clasificacion=classification,
                   nombre_original=path.name, sha256=digest, bytes=str(len(data)),
                   mime_detectado=info.mime if info else "", estado=state, observacion=observation)
        rows.append(row)
        reasons = []
        if integrity != "VALID": reasons.append(integrity)
        if classification != "CLASSIFIED": reasons.append(classification)
        for reason in reasons:
            item = {field: "" for field in PENDING_FIELDS}
            item.update(id=f"existing-{len(pending)+1:04d}", marca_sugerida=brand,
                        modelo_sugerido=model, tipo=info.kind if info else "", motivo=reason,
                        ruta_relativa=relative.as_posix(), accion_sugerida="revisar sin mover el archivo")
            pending.append(item)
    if write:
        write_csv(safe_path(root, "inventario.csv"), INVENTORY_FIELDS, rows, root)
        write_csv(safe_path(root, "pendientes-revision.csv"), PENDING_FIELDS, pending, root)
        write_csv(safe_path(root, "_control/checksums.csv"), ("ruta_relativa", "sha256", "bytes"),
                  ({k: r[k] for k in ("ruta_relativa", "sha256", "bytes")} for r in rows), root)
        manifest_path = safe_path(root, "_control/manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["associations"] = [{"brand": r["marca"], "model": r["modelo"], "path": r["ruta_relativa"],
                                     "method": r["metodo_asociacion"]} for r in rows if r["modelo"]]
        write_json(manifest_path, manifest, root)
    return rows, pending
