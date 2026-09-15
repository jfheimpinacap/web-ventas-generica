from __future__ import annotations

import os
from pathlib import Path

BRANDS = ("LGMG", "EP")
DIRECTORIES = (
    "LGMG/Imagenes modelos LGMG", "LGMG/fichas-tecnicas LGMG",
    "EP/Imagenes modelos EP", "EP/fichas-tecnicas EP",
    "_pendientes/imagenes", "_pendientes/fichas-tecnicas",
    "_control/logs", "_control/parciales",
)
FILES = ("_control/fuentes.csv", "_control/candidatos.json", "_control/manifest.json",
         "_control/checksums.csv", "inventario.csv", "pendientes-revision.csv")

def safe_path(root: Path, relative: str | Path) -> Path:
    root = root.expanduser().resolve()
    candidate = root.joinpath(relative)
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError("la ruta sale de --root")
    # Existing symlink parents are covered by resolve(); reject the final symlink too.
    if candidate.is_symlink():
        raise ValueError("no se permiten escapes mediante symlink")
    return candidate

def initialize(root: Path, initial_files: dict[str, bytes]) -> None:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for directory in DIRECTORIES:
        safe_path(root, directory).mkdir(parents=True, exist_ok=True)
    for relative in FILES:
        path = safe_path(root, relative)
        if not path.exists():
            path.write_bytes(initial_files.get(relative, b""))

def atomic_write(path: Path, data: bytes, root: Path) -> None:
    path = safe_path(root, path.relative_to(root))
    tmp = safe_path(root, path.relative_to(root).as_posix() + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
