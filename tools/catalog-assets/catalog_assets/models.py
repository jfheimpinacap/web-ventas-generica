from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

MODEL_COLUMNS = ("brand", "canonical_model", "alias", "enabled", "notes")


@dataclass(frozen=True)
class ModelAlias:
    brand: str
    canonical_model: str
    alias: str


def read_model_aliases(path: Path) -> list[ModelAlias]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MODEL_COLUMNS:
            raise ValueError("columnas de modelos.csv inválidas")
        aliases: dict[tuple[str, str], str] = {}
        result = []
        for number, row in enumerate(reader, 2):
            brand = row["brand"].strip().upper()
            enabled = row["enabled"].strip().lower()
            canonical, alias = row["canonical_model"].strip(), row["alias"].strip()
            if brand not in {"LGMG", "EP", "JLG"}:
                raise ValueError(f"fila {number}: marca inválida")
            if enabled not in {"true", "false"}:
                raise ValueError(f"fila {number}: enabled debe ser true o false")
            if not canonical or not alias:
                raise ValueError(f"fila {number}: modelo y alias son obligatorios")
            if enabled == "false":
                continue
            key = (brand, alias.casefold())
            if key in aliases:
                raise ValueError(f"fila {number}: alias duplicado o contradictorio")
            aliases[key] = canonical
            result.append(ModelAlias(brand, canonical, alias))
    return sorted(result, key=lambda x: (x.brand, x.alias.casefold(), x.canonical_model.casefold()))
