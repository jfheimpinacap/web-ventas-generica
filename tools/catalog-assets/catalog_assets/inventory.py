from __future__ import annotations

import hashlib
import re
from pathlib import Path
from .paths import safe_path
from .reports import INVENTORY_FIELDS, PENDING_FIELDS, write_csv
from .validation import detect_binary

def _association(relative: Path) -> tuple[str, str]:
    parts = relative.parts
    brand = parts[0] if parts and parts[0] in {"LGMG", "EP"} else ""
    stem = relative.stem
    patterns = ([r"^LGMG-(.+?)(?:-\d+)?$", r"^Ficha-tecnica-LGMG-(.+?)(?:-\d+)?$"],
                [r"^EP-(.+?)(?:-\d+)?$", r"^Ficha-tecnica-EP-(.+?)(?:-\d+)?$"])
    if brand:
        for pattern in patterns[0 if brand == "LGMG" else 1]:
            match = re.match(pattern, stem, re.I)
            if match: return brand, match.group(1)
    return brand, ""

def scan(root: Path, write: bool = True) -> tuple[list[dict], list[dict]]:
    root = root.resolve(); rows, pending, hashes = [], [], {}
    excluded = {"inventario.csv", "pendientes-revision.csv", "fuentes.csv", "checksums.csv"}
    for path in sorted((p for p in root.rglob("*") if p.is_file() and not p.is_symlink()), key=lambda p: p.relative_to(root).as_posix().casefold()):
        if path.name in excluded or "_control" in path.relative_to(root).parts: continue
        relative = path.relative_to(root); data = path.read_bytes(); digest = hashlib.sha256(data).hexdigest()
        brand, model = _association(relative); state, observation, info = "VALID", "", None
        try: info = detect_binary(data)
        except ValueError: state, observation = "INVALID_BINARY", "firma binaria no admitida o truncada"
        if info and path.suffix.lower() != info.extension and not (path.suffix.lower() == ".jpeg" and info.extension == ".jpg"):
            state, observation = "MIME_CONFLICT", "extensión no coincide con el contenido"
        if digest in hashes:
            state, observation = "DUPLICATE", f"duplica {hashes[digest]}"
        else: hashes[digest] = relative.as_posix()
        if not model and state == "VALID": state, observation = "MODEL_UNKNOWN", "modelo no inferible con seguridad"
        row = {field: "" for field in INVENTORY_FIELDS}
        row.update(marca=brand, modelo=model, tipo=info.kind if info else "", archivo=path.name,
                   ruta_relativa=relative.as_posix(), nombre_original=path.name, sha256=digest,
                   bytes=str(len(data)), mime_detectado=info.mime if info else "", estado=state, observacion=observation)
        rows.append(row)
        if state != "VALID":
            item = {field: "" for field in PENDING_FIELDS}
            item.update(id=f"existing-{len(pending)+1:04d}", marca_sugerida=brand, modelo_sugerido=model,
                        tipo=info.kind if info else "", motivo=state, ruta_relativa=relative.as_posix(), accion_sugerida="revisar sin mover el archivo")
            pending.append(item)
    if write:
        write_csv(safe_path(root, "inventario.csv"), INVENTORY_FIELDS, rows, root)
        write_csv(safe_path(root, "pendientes-revision.csv"), PENDING_FIELDS, pending, root)
        checks = ({"ruta_relativa": r["ruta_relativa"], "sha256": r["sha256"], "bytes": r["bytes"]} for r in rows)
        write_csv(safe_path(root, "_control/checksums.csv"), ("ruta_relativa", "sha256", "bytes"), checks, root)
    return rows, pending
