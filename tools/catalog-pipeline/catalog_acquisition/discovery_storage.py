"""Immutable raw snapshots and hash-verified conditional cache."""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from .paths import safe_join
from .serialization import canonical_bytes
from .storage import atomic_write, verify_hash, write_once

@dataclass(frozen=True)
class SnapshotMetadata:
    requested_url:str; canonical_url:str; final_url:str; source:str; source_role:str
    http_status:int; network_status:int; content_type:str; encoding:str|None; size:int
    sha256:str; etag:str|None; last_modified:str|None; timestamp_utc:str
    adapter_version:str; request_policy_version:str; robots_decision:dict[str,object]
    relative_path:str; parsing_status:str; reused_cache_reference:str|None=None

class SnapshotStore:
    def __init__(self,root:Path): self.root=root.resolve()
    def persist(self,run_id:str,source:str,body:bytes,metadata:dict[str,object])->SnapshotMetadata:
        digest=sha256(body).hexdigest(); rel=f"_pipeline/snapshots/{run_id}/{source}/{digest}.raw"
        write_once(safe_join(self.root,rel),body,digest)
        value=SnapshotMetadata(**metadata,size=len(body),sha256=digest,relative_path=rel)
        write_once(safe_join(self.root,rel+".json"),canonical_bytes(asdict(value)))
        return value

class VerifiedCache:
    def __init__(self,root:Path): self.root=root.resolve()
    def key(self,source,url,variant="identity"): return sha256(f"cache-v1\0{source}\0{url}\0{variant}".encode("utf-8")).hexdigest()
    def load(self,key):
        meta_path=safe_join(self.root,f"_pipeline/cache/{key}.json"); body_path=safe_join(self.root,f"_pipeline/cache/{key}.raw")
        if not meta_path.exists() or not body_path.exists(): return None
        meta=json.loads(meta_path.read_text(encoding="utf-8")); verify_hash(body_path.read_bytes(),meta["sha256"]); return body_path.read_bytes(),meta
    def store(self,key,body,*,etag=None,last_modified=None):
        digest=sha256(body).hexdigest(); write_once(safe_join(self.root,f"_pipeline/cache/{key}.raw"),body,digest)
        atomic_write(safe_join(self.root,f"_pipeline/cache/{key}.json"),canonical_bytes({"schema_version":"cache-v1","sha256":digest,"etag":etag,"last_modified":last_modified}))
