from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlsplit

COLUMNS = ("target_brand", "model", "source_name", "source_role", "page_url", "asset_type",
           "asset_url", "priority", "expected_language", "enabled", "notes")

@dataclass(frozen=True)
class Source:
    target_brand: str; model: str; source_name: str; source_role: str; page_url: str
    asset_type: str; asset_url: str; priority: int; expected_language: str; enabled: bool; notes: str

def _url_syntax(value: str) -> bool:
    p = urlsplit(value)
    return p.scheme in {"http", "https"} and bool(p.hostname) and not p.username and not p.password

def read_sources(path: Path) -> list[Source]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("columnas de fuentes.csv inválidas")
        rows = []
        for number, raw in enumerate(reader, 2):
            brand, role, source = raw["target_brand"].strip().upper(), raw["source_role"].strip().lower(), raw["source_name"].strip().upper()
            enabled_raw = raw["enabled"].strip().lower()
            if brand not in {"LGMG", "EP", "JLG"} or role not in {"primary", "fallback"} or raw["asset_type"] not in {"image", "technical_sheet", "auto"}:
                raise ValueError(f"fila {number}: enum inválido")
            if enabled_raw not in {"true", "false"}:
                raise ValueError(f"fila {number}: enabled debe ser true o false")
            try: priority = int(raw["priority"])
            except ValueError: raise ValueError(f"fila {number}: priority inválida") from None
            if priority < 0: raise ValueError(f"fila {number}: priority negativa")
            if source == "GAM" and (brand != "EP" or role != "fallback"):
                raise ValueError(f"fila {number}: GAM solo es fallback de EP")
            if enabled_raw == "true" and not (raw["page_url"].strip() or raw["asset_url"].strip()):
                raise ValueError(f"fila {number}: SOURCE_MISSING")
            for value in (raw["page_url"].strip(), raw["asset_url"].strip()):
                if value and not _url_syntax(value): raise ValueError(f"fila {number}: URL inválida")
            rows.append(Source(brand, raw["model"].strip(), source, role, raw["page_url"].strip(), raw["asset_type"], raw["asset_url"].strip(), priority, raw["expected_language"].strip(), enabled_raw == "true", raw["notes"].strip()))
    return sorted(rows, key=lambda r: (r.priority, r.target_brand, r.model.casefold(), r.source_name, r.page_url, r.asset_url))

def serializable(source: Source) -> dict:
    return asdict(source)
