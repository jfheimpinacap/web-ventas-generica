"""Stable consumption of a canonically verified package; never extracts files."""
import hashlib, io, json, os, tempfile, zipfile
from pathlib import Path
from types import MappingProxyType

class ImportInputError(ValueError):
    def __init__(self,code,detail): self.code=code; super().__init__(detail)

def read_verified_package(path,receipt,policy,verifier):
    source=Path(path)
    if not source.is_file() or source.suffix.casefold()!=".zip": raise ImportInputError("INVALID_PACKAGE_INPUT","canonical ZIP required")
    data=source.read_bytes(); digest=hashlib.sha256(data).hexdigest()
    fd,name=tempfile.mkstemp(prefix=".jem-import-verify-",suffix=".zip",dir=source.parent)
    try:
        with os.fdopen(fd,"wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if receipt is None: raise ImportInputError("RECEIPT_REQUIRED","external receipt is required")
        report=verifier(name,receipt,policy)
    finally:
        Path(name).unlink(missing_ok=True)
    if not report["valid"]: raise ImportInputError("INVALID_PACKAGE",",".join(report["errors"]))
    if source.read_bytes()!=data: raise ImportInputError("PACKAGE_CHANGED","package changed while being consumed")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest=json.loads(archive.read("package-manifest.json").decode("utf-8",errors="strict"))
        if manifest.get("blocked_product_count")!=0 or manifest.get("product_count",0)<1: raise ImportInputError("PACKAGE_NOT_IMPORTABLE","package is empty or blocked")
        entries={item["path"]:archive.read(item["path"]) for item in manifest["entries"]}
    if digest!=report["zip_sha256"]: raise ImportInputError("PACKAGE_CHANGED","verified bytes differ")
    return MappingProxyType({"verification":MappingProxyType(report),"manifest":MappingProxyType(manifest),
                             "entries":MappingProxyType(entries),"import_authorized":False})
