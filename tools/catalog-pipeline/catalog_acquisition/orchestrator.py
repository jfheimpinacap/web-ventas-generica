"""Deterministic frontier, replay artifacts, resume validation and comparison."""
from __future__ import annotations
import json
import re
from dataclasses import asdict,dataclass,field
from hashlib import sha256
from pathlib import Path
from .discovery import MANIFEST_VERSION,SOURCES,SourceDefinition,candidate_record
from .robots import evaluate,permits_catalog
from .serialization import canonical_bytes
from .storage import atomic_write,verify_hash
from .paths import safe_join

@dataclass(order=True)
class FrontierItem:
    canonical_url:str; kind:str="listing"; origin:str|None=None; state:str="planned"; reason:str=""; depth:int=0; attempts:int=0; snapshot_reference:str|None=None; locator:str|None=None

class Frontier:
    def __init__(self,items=()): self.items={x.canonical_url:x for x in items}; self.content_hashes={}
    def add(self,item):
        if item.canonical_url not in self.items:self.items[item.canonical_url]=item; return True
        return False
    def next(self):
        pending=sorted(x for x in self.items.values() if x.state in ("planned","failed"))
        return pending[0] if pending else None
    def mark_hash(self,url,digest):
        duplicate=self.content_hashes.get(digest); self.content_hashes.setdefault(digest,url); return duplicate
    def records(self): return [asdict(x) for x in sorted(self.items.values())]

def semantic_config(selected,output_root,max_pages,max_depth,user_agent):
    return {"schema_version":"discovery-config-v1","sources":[asdict(SOURCES[x]) for x in sorted(selected)],"output_root":str(Path(output_root).resolve()),"max_pages":max_pages,"max_depth":max_depth,"user_agent":user_agent}
def config_fingerprint(config): return sha256(canonical_bytes(config)).hexdigest()
def validate_resume(previous,config):
    if previous.get("config_fingerprint")!=config_fingerprint(config): raise ValueError("incompatible discovery run; abort before network")

@dataclass
class CaptureResult:
    source:str; adapter:str; adapter_version:str; structure_verified:bool
    state:str; reason:str; requests_attempted:int=0; origin_responses:int=0
    urls_blocked:int=0; snapshots_persisted:int=0; robots:dict|None=None
    responses:list=field(default_factory=list)

def structure_gate(source:SourceDefinition,adapter)->str|None:
    """Return a stable blocking reason; a boolean alone can never enable live."""
    if not source.structure_verified: return "source_structure_unverified"
    if not source.structure_evidence_reference: return "source_structure_evidence_missing"
    if not re.fullmatch(r"[0-9a-f]{64}",source.structure_evidence_sha256 or ""):
        return "source_structure_evidence_hash_invalid"
    if source.structure_evidence_rule_version != adapter.adapter_version:
        return "source_structure_evidence_version_mismatch"
    if source.adapter_version != adapter.adapter_version:
        return "source_adapter_version_mismatch"
    return None

def capture_source(source:SourceDefinition,adapter,transport,*,config_fingerprint_value:str,
                   max_pages:int=100,max_depth:int=5)->CaptureResult:
    """The sole live-source orchestrator: structure -> robots -> per-URL robots -> transport.

    Callers cannot provide a pre-authorized frontier, cached robots decision, or old snapshot.
    Each invocation obtains and binds fresh robots evidence to source, UA and configuration.
    """
    result=CaptureResult(source.source,adapter.adapter_id,adapter.adapter_version,source.structure_verified,
                         "blocked","source_structure_unverified")
    reason=structure_gate(source,adapter)
    if reason: result.reason=reason; return result
    robots_url=f"https://{source.hosts[0]}/robots.txt"
    result.requests_attempted=1
    try: response=transport.fetch(robots_url,source,method="GET")
    except Exception as exc:
        result.reason="robots_fetch_failed"; result.robots={"source":source.source,"state":"fetch_failed",
            "user_agent":transport.policy.user_agent,"config_fingerprint":config_fingerprint_value,
            "detail":type(exc).__name__}; return result
    result.origin_responses=1
    decision=evaluate(robots_url=robots_url,status=response.status,body=response.body,
        target_url=source.start_url,user_agent=transport.policy.user_agent,fetched_at=response.fetched_at)
    result.robots=decision.__dict__|{"source":source.source,"config_fingerprint":config_fingerprint_value}
    if not permits_catalog(decision): result.reason=f"robots_{decision.state}"; result.urls_blocked=1; return result
    pending=[(source.start_url,0)]; visited=set(); result.state="running"; result.reason=""
    while pending and len(visited)<max_pages:
        url,depth=pending.pop(0)
        if url in visited: continue
        per_url=evaluate(robots_url=robots_url,status=response.status,body=response.body,
            target_url=url,user_agent=transport.policy.user_agent,fetched_at=response.fetched_at)
        if not permits_catalog(per_url): result.urls_blocked+=1; visited.add(url); continue
        result.requests_attempted+=1
        try: page=transport.fetch(url,source,method="GET")
        except Exception:
            result.state="blocked"; result.reason="catalog_transport_failed"; result.urls_blocked+=len(pending); return result
        result.origin_responses+=1; result.responses.append(page); visited.add(url)
        try: parsed=adapter.parse(page.body,base_url=page.final_url,content_type=page.content_type,
            encoding=page.encoding,snapshot_reference="pending-persistence")
        except Exception:
            result.state="blocked"; result.reason="catalog_parse_failed"; return result
        if depth<max_depth:
            crawl=sorted({x.canonical_url for x in parsed.links if x.canonical_url and x.kind in ("category","listing","pagination")})
            for discovered in crawl:
                allowed=evaluate(robots_url=robots_url,status=response.status,body=response.body,
                    target_url=discovered,user_agent=transport.policy.user_agent,fetched_at=response.fetched_at)
                if permits_catalog(allowed): pending.append((discovered,depth+1))
                else: result.urls_blocked+=1
        for sitemap in decision.sitemaps:
            # Sitemaps never bypass URL scope or per-URL robots; adapters must explicitly classify them later.
            result.urls_blocked+=1
    if pending: result.state="incomplete"; result.reason="page_or_depth_limit_reached"
    else: result.state="incomplete"; result.reason="capture_requires_snapshot_persistence"
    return result

def validate_resume_preflight(previous:dict,config:dict,sources:dict,adapters:dict,user_agent:str)->None:
    validate_resume(previous,config)
    for key in sorted(sources):
        reason=structure_gate(sources[key],adapters[key])
        if reason: raise ValueError(f"{key}:{reason}; abort before network")
        old=(previous.get("robots") or {}).get(key)
        if not old:
            raise ValueError(f"{key}:missing robots evidence; abort before network")
        if (old.get("source")!=key or old.get("user_agent")!=user_agent or
                    old.get("config_fingerprint")!=config_fingerprint(config) or
                    old.get("state") not in {"allowed","not_found","disallowed","unknown",
                                             "fetch_failed","parse_failed"}):
            raise ValueError(f"{key}:incompatible robots evidence; abort before network")

def replay(snapshot_manifest:dict,root:Path,output_dir:Path,adapters)->dict:
    categories=[]; candidates=[]; frontier=[]; snapshot_hashes=[]; warnings=[]
    for snap in sorted(snapshot_manifest["snapshots"],key=lambda x:(x["source"],x["canonical_url"])):
        body=safe_join(root,snap["relative_path"]).read_bytes(); verify_hash(body,snap["sha256"]); snapshot_hashes.append(snap["sha256"])
        parsed=adapters[snap["source"]].parse(body,base_url=snap["canonical_url"],content_type=snap["content_type"],encoding=snap.get("encoding"),snapshot_reference=snap["relative_path"])
        categories.extend(parsed.categories); candidates.extend(candidate_record(SOURCES[snap["source"]],x) for x in parsed.links if x.kind=="product_candidate")
        warnings.extend(parsed.warnings)
        frontier.extend({"url":x.canonical_url or x.original_url,"type":x.kind,"origin":x.evidence.origin_url,"state":"accepted" if x.kind in ("category","listing","pagination","product_candidate") else "excluded","reason":x.reason,"depth":1,"attempts":0,"snapshot_reference":snap["relative_path"]} for x in parsed.links)
    categories=sorted(categories,key=lambda x:(x["source"],x["url"])); candidates=sorted(candidates,key=lambda x:(x["source"],x["canonical_url"])); frontier=sorted(frontier,key=lambda x:(x["url"],x["type"]));
    payload={"schema_version":MANIFEST_VERSION,"run_id":snapshot_manifest["run_id"],"sources":sorted({x["source"] for x in snapshot_manifest["snapshots"]}),"adapters":{k:v.adapter_version for k,v in sorted(adapters.items())},"configuration":snapshot_manifest["configuration"],"start_urls":snapshot_manifest["start_urls"],"robots":snapshot_manifest["robots"],"counts":{"categories":len(categories),"candidates":len(candidates),"frontier":len(frontier)},"states":snapshot_manifest["states"],"snapshot_hashes":sorted(snapshot_hashes),"warnings":sorted(set(warnings))}
    payload["content_fingerprint"]=sha256(canonical_bytes(payload)).hexdigest(); output_dir.mkdir(parents=True,exist_ok=True)
    _jsonl(output_dir/"categories.jsonl",categories); _jsonl(output_dir/"product-candidates.jsonl",candidates); _jsonl(output_dir/"frontier.jsonl",frontier); atomic_write(output_dir/"discovery-manifest.json",canonical_bytes(payload)); atomic_write(output_dir/"discovery-report.txt",_report(payload).encode())
    return payload
def _jsonl(path,rows): atomic_write(path,b"".join(canonical_bytes(x)+b"\n" for x in rows))
def _report(m): return "Catalog discovery (audit report)\n"+"\n".join(f"{k}: {v}" for k,v in sorted(m["counts"].items()))+"\nStates: "+json.dumps(m["states"],sort_keys=True)+"\nWarnings: "+json.dumps(m["warnings"],sort_keys=True)+"\n"

def compare(old,new,old_ref,new_ref):
    if old.get("states")!=dict.fromkeys(old.get("sources",[]),"complete") or new.get("states")!=dict.fromkeys(new.get("sources",[]),"complete"): return {"status":"comparison_blocked","reason":"both discoveries must be complete","old_manifest":old_ref,"new_manifest":new_ref,"differences":[]}
    if old.get("adapters")!=new.get("adapters"): return {"status":"comparison_blocked","reason":"adapter/rule versions differ","old_manifest":old_ref,"new_manifest":new_ref,"differences":[{"classification":"source_structure_changed"}]}
    a={x["source_key"]:x for x in old.get("product_candidates",[])}; b={x["source_key"]:x for x in new.get("product_candidates",[])}; diff=[]
    for key in sorted(a.keys()|b.keys()):
        classification="new" if key not in a else "not_observed_in_latest" if key not in b else "url_changed" if a[key]["canonical_url"]!=b[key]["canonical_url"] else "unchanged"
        diff.append({"classification":classification,"source_key":key,"old":a.get(key),"new":b.get(key),"old_manifest":old_ref,"new_manifest":new_ref})
    return {"status":"complete","differences":diff,"old_manifest":old_ref,"new_manifest":new_ref}
