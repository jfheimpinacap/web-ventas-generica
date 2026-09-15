from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from .paths import atomic_write

INVENTORY_FIELDS = ("marca", "modelo", "tipo", "posicion", "archivo", "ruta_relativa", "ubicacion", "metodo_asociacion", "estado_integridad", "estado_clasificacion", "fuente", "source_role", "pagina_origen", "url_original", "nombre_original", "sha256", "bytes", "mime_detectado", "estado", "observacion")
PENDING_FIELDS = ("id", "marca_sugerida", "modelo_sugerido", "tipo", "motivo", "fuente", "pagina_origen", "url_original", "ruta_relativa", "accion_sugerida")

def csv_bytes(fields, rows) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader(); writer.writerows(sorted(rows, key=lambda r: tuple(str(r.get(f, "")) for f in fields)))
    return stream.getvalue().encode("utf-8-sig")

def write_csv(path: Path, fields, rows, root: Path) -> None:
    atomic_write(path, csv_bytes(fields, rows), root)

def write_json(path: Path, value, root: Path) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(), root)
