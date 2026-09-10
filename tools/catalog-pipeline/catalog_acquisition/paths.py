"""Host-independent Windows-safe filesystem materialization."""
from __future__ import annotations
import hashlib, os, re, unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath
from .errors import PathCollisionError, UnsafePathError

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.I)
MAX_SEGMENT = 100

def _reject_pathlike(value: str) -> None:
    if not value or value in {".", ".."} or PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute():
        raise UnsafePathError("A label, not a path, is required", value=value)
    if value.startswith(("\\\\", "//")) or re.match(r"^[A-Za-z]:", value):
        raise UnsafePathError("Absolute, UNC and drive paths are forbidden", value=value)

def category_slug(label: str) -> str:
    _reject_pathlike(label)
    ascii_value = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii").lower()
    result = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not result: raise UnsafePathError("Category has no materializable ASCII characters", value=label)
    return result

def model_key(model: str) -> str:
    _reject_pathlike(model)
    value = unicodedata.normalize("NFC", model)
    value = _INVALID.sub("_", value).rstrip(" .")
    if not value or value in {".", ".."}: raise UnsafePathError("Model produces an empty or traversal segment", value=model)
    if _RESERVED.match(value): value = f"_{value}"
    if len(value.encode("utf-8")) > MAX_SEGMENT:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
        while len(value.encode("utf-8")) > MAX_SEGMENT - 18: value = value[:-1]
        value = f"{value}--{digest}"
    return value

def windows_collision_key(segment: str) -> str:
    return unicodedata.normalize("NFC", segment).rstrip(" .").casefold()

def safe_join(root: Path, relative: str | PurePosixPath) -> Path:
    """Resolve an untrusted canonical POSIX manifest path below ``root``."""
    try:
        value = os.fspath(relative)
    except TypeError as exc:
        raise UnsafePathError("Portable path must be text") from exc
    if not isinstance(value, str):
        raise UnsafePathError("Portable path must be text")
    if not value or any(unicodedata.category(character) == "Cc" for character in value):
        raise UnsafePathError("Portable path is empty or contains control characters")

    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (posix_path.is_absolute() or windows_path.drive or windows_path.root
            or windows_path.anchor):
        raise UnsafePathError("Portable path must be relative and must not name a drive or share")
    if "\\" in value:
        raise UnsafePathError("Portable paths must use '/' separators")

    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise UnsafePathError("Portable path contains an empty or traversal segment")
    for segment in segments:
        if ":" in segment:
            raise UnsafePathError("Portable path segments must not contain ':'")
        if segment.endswith((" ", ".")):
            raise UnsafePathError("Portable path segments must not end in a space or dot")
        if _RESERVED.fullmatch(segment):
            raise UnsafePathError("Portable path contains a reserved Windows name")

    try:
        root_resolved = root.resolve()
        target = root_resolved.joinpath(*segments).resolve()
        target.relative_to(root_resolved)
    except (OSError, RuntimeError, ValueError) as exc:
        raise UnsafePathError("Portable path cannot be confined to the configured root") from exc
    return target

class LayoutRegistry:
    """Collision registry also serving as reversible original->materialized manifest."""
    def __init__(self) -> None: self.entries: list[dict[str, str | None]] = []; self._keys: dict[str, str] = {}
    def add(self, kind: str, original: str, materialized: str, *, resolved_canonical_identity_value: str | None=None) -> dict[str, str | None]:
        key = f"{kind}:{windows_collision_key(materialized)}"
        owner=resolved_canonical_identity_value or original
        if key in self._keys and self._keys[key] != owner:
            raise PathCollisionError("Distinct owners collide under Windows comparison", first=self._keys[key], second=owner)
        self._keys[key] = owner
        entry = {"kind": kind, "resolved_canonical_identity_value": resolved_canonical_identity_value, "original_name": original, "materialized_name": materialized}
        if entry not in self.entries: self.entries.append(entry)
        return entry

def create_layout(root: Path, brand: str, category: str, model: str, *, resolved_canonical_identity_value: str,
                  registry: LayoutRegistry) -> dict[str, str]:
    """Create only the controlled empty directory layout and return portable paths."""
    brand_key=model_key(brand); category_key=category_slug(category); product_key=model_key(model)
    registry.add("brand",brand,brand_key); registry.add("category",category,category_key)
    registry.add("model",model,product_key,resolved_canonical_identity_value=resolved_canonical_identity_value)
    relatives=[f"{brand_key}/catalogo/{category_key}/{product_key}/{leaf}" for leaf in ("imagenes","fichas-tecnicas","documentos")]
    relatives += [f"{brand_key}/_pipeline/{leaf}" for leaf in ("snapshots","cache","manifests","mappings","reports","packages")]
    for relative in relatives: safe_join(root,relative).mkdir(parents=True,exist_ok=True)
    return {"brand_key":brand_key,"category_key":category_key,"model_key":product_key,"resolved_canonical_identity_value":resolved_canonical_identity_value,"product_path":f"{brand_key}/catalogo/{category_key}/{product_key}"}

def image_filename(brand: str, model: str, order: int, extension: str, main: bool=False) -> str:
    if order < 0 or not re.fullmatch(r"[A-Za-z0-9]+",extension): raise UnsafePathError("Invalid image order or extension")
    return f"{model_key(brand)}-{model_key(model)}-{order}{'-principal' if main else ''}.{extension.lower()}"

def technical_sheet_filename(brand: str, model: str, language: str, revision: str | None=None) -> str:
    if not re.fullmatch(r"[A-Za-z0-9-]+",language): raise UnsafePathError("Invalid language")
    suffix=f"-{model_key(revision)}" if revision else ""
    return f"{model_key(brand)}-{model_key(model)}-ficha-tecnica-{language.lower()}{suffix}.pdf"

def document_filename(brand: str, model: str, document_type: str, language: str | None=None,
                      revision: str | None=None, ordinal: int | None=None) -> str:
    """Return an evidence-based, generic PDF name (never a collision suffix)."""
    if document_type not in {"technical_sheet", "brochure", "manual", "additional_document"}:
        raise UnsafePathError("Unsupported document type")
    parts = [model_key(brand), model_key(model), document_type.replace("_", "-")]
    if language:
        if not re.fullmatch(r"[A-Za-z0-9-]+", language): raise UnsafePathError("Invalid language")
        parts.append(language.lower())
    if revision: parts.append(model_key(revision))
    if ordinal is not None:
        if ordinal < 1: raise UnsafePathError("Invalid document ordinal")
        parts.append(str(ordinal))
    return "-".join(parts) + ".pdf"
