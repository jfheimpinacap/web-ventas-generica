from __future__ import annotations

import re
from pathlib import Path

RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

def normalize_model(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())

def sanitize(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value).strip(" .")
    if not value or value.upper() in RESERVED:
        value = "_" + (value or "modelo")
    return value

def asset_basename(brand: str, model: str, kind: str, extension: str, position: int = 1) -> str:
    if brand not in {"LGMG", "EP", "JLG"}:
        raise ValueError("marca de destino inválida")
    stem = f"{brand}-{sanitize(model)}" if kind == "image" else f"Ficha-tecnica-{brand}-{sanitize(model)}"
    return f"{stem}{'' if position == 1 else f'-{position}'}{extension.lower()}"

def next_path(directory: Path, brand: str, model: str, kind: str, extension: str) -> Path:
    position = 1
    while True:
        candidate = directory / asset_basename(brand, model, kind, extension, position)
        if not candidate.exists():
            return candidate
        position += 1
