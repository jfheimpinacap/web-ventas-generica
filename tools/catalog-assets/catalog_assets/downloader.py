from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib.parse import urlsplit
from .naming import next_path, sanitize
from .paths import safe_path, atomic_write
from .validation import detect_binary, validate_public_url

def target_dir(root: Path, brand: str, kind: str) -> Path:
    if brand not in {"LGMG", "EP"}: raise ValueError("marca de destino inválida")
    folder = f"{brand}/{'Imagenes modelos '+brand if kind == 'image' else 'fichas-tecnicas '+brand}"
    return safe_path(root, folder)

def download_one(root: Path, candidate: dict, transport, max_bytes=50_000_000, timeout=30, retries=2, pause=0.0, pending=False):
    url=candidate["url"]; validate_public_url(url, transport.resolve)
    partial=safe_path(root, "_control/parciales/"+hashlib.sha256(url.encode()).hexdigest()+".part")
    for attempt in range(retries+1):
        offset=partial.stat().st_size if partial.exists() else 0
        headers={"Range":f"bytes={offset}-"} if offset else {}
        try:
            response=transport.get(url,headers=headers,timeout=timeout,max_bytes=max_bytes)
            validate_public_url(response.final_url, transport.resolve)
            if response.status not in ({206} if offset else {200}):
                if offset and response.status == 200: partial.write_bytes(b""); offset=0
                elif response.status >= 400: raise OSError(f"HTTP {response.status}")
            mode="ab" if offset and response.status==206 else "wb"
            with partial.open(mode) as out: out.write(response.body)
            if partial.stat().st_size > max_bytes: raise ValueError("límite de tamaño excedido")
            data=partial.read_bytes(); info=detect_binary(data)
            headers={str(key).lower():value for key,value in response.headers.items()}
            declared=(headers.get("content-type") or "").split(";",1)[0].lower()
            if declared and declared not in {info.mime,"application/octet-stream","binary/octet-stream"}: raise ValueError("MIME_CONFLICT")
            digest=hashlib.sha256(data).hexdigest()
            for existing in root.rglob("*"):
                if existing.is_file() and "_control" not in existing.parts and hashlib.sha256(existing.read_bytes()).hexdigest()==digest:
                    partial.unlink(missing_ok=True); return {"state":"DUPLICATE","path":existing.relative_to(root).as_posix(),"sha256":digest}
            if pending:
                directory=safe_path(root,"_pendientes/"+("imagenes" if info.kind=="image" else "fichas-tecnicas"))
                original=sanitize(Path(urlsplit(url).path).stem or hashlib.sha256(url.encode()).hexdigest()[:16])
                destination=directory/(original+info.extension); index=2
                while destination.exists(): destination=directory/f"{original}-{index}{info.extension}"; index+=1
            else:
                destination=next_path(target_dir(root,candidate["target_brand"],info.kind),candidate["target_brand"],candidate["model"],info.kind,info.extension)
            atomic_write(destination,data,root); partial.unlink(missing_ok=True)
            return {"state":"VALID","path":destination.relative_to(root).as_posix(),"sha256":digest,"bytes":len(data),"mime":info.mime,"status":response.status,"final_url":response.final_url,"original_name":Path(urlsplit(url).path).name}
        except (OSError, TimeoutError) as error:
            if attempt == retries: return {"state":"DOWNLOAD_FAILED","error":str(error)}
            time.sleep(pause)
