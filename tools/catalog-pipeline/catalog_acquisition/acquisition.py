"""Authorized sequential acquisition orchestrator; all HTTP is injected."""
from __future__ import annotations
import json, os, re
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from .acquisition_plan import AcquisitionBlocked, POLICY_VERSION, validate_url
from .paths import safe_join
from .robots import evaluate, permits_catalog
from .serialization import canonical_bytes
from .storage import atomic_write

REDIRECTS=frozenset({301,302,303,307,308})
STRONG_ETAG=re.compile(r'^"[^"\r\n]+"$')
CONTENT_RANGE=re.compile(r"^bytes ([0-9]+)-([0-9]+)/([0-9]+)$")

def _sanitize(url):
    p=urlsplit(url); return p._replace(query="<redacted>" if p.query else "",fragment="").geturl()
def _headers(value): return {str(k).casefold():str(v) for k,v in value.items() if str(k).casefold() in {
  "content-type","content-length","content-range","etag","last-modified","location","accept-ranges","content-encoding"}}
def _strong(value): return value if isinstance(value,str) and STRONG_ETAG.fullmatch(value) else None
def _id(prefix,*parts): return prefix+":sha256:"+sha256("\0".join(map(str,parts)).encode("utf-8")).hexdigest()

class AcquisitionSession:
    def __init__(self,*,plan,authorization,transport,output_root:Path,clock,pause,resolver=urljoin):
        if not plan.get("transport_allowed") or plan.get("authorization_fingerprint")!=authorization.get("authorization_fingerprint"):
            raise AcquisitionBlocked("transport_construction_not_authorized")
        self.plan=plan; self.auth=authorization; self.transport=transport; self.root=output_root
        self.clock=clock; self.pause=pause; self.resolve=resolver; self.requests=0; self.asset_requests=0; self.total_bytes=0
        self.robots={}; self.receipts=[]; self.payloads=[]; self.reviews=[]
    def _request(self,url,headers=None,limit=None):
        if self.requests>=self.auth["limits"]["max_requests"]: raise AcquisitionBlocked("request_limit")
        self.requests+=1
        return self.transport.request("GET",url,headers or {},max_body_bytes=limit or self.auth["limits"]["max_bytes_per_asset"])
    def _ensure_robots(self,url,sequence):
        host=urlsplit(url).hostname
        if host in self.robots: return self.robots[host]
        robots=validate_url(f"https://{host}/robots.txt",self.auth); response=self._request(robots,limit=self.auth["limits"]["max_robots_bytes"])
        sequence.append({"kind":"robots","method":"GET","url":robots,"status":response.status,"headers":_headers(response.headers)})
        if response.status in REDIRECTS: raise AcquisitionBlocked("robots_redirect")
        body=b"".join(response.chunks)
        decision=evaluate(robots_url=robots,status=response.status,body=body,target_url=url,user_agent=self.auth["user_agent"],fetched_at=self.clock())
        self.robots[host]=(response.status,body,decision)
        if not permits_catalog(decision): raise AcquisitionBlocked("robots_"+decision.state)
        return self.robots[host]
    def _robots_allows(self,url,sequence):
        status,body,_=self._ensure_robots(url,sequence); host=urlsplit(url).hostname
        decision=evaluate(robots_url=f"https://{host}/robots.txt",status=status,body=body,target_url=url,user_agent=self.auth["user_agent"],fetched_at=self.clock())
        if not permits_catalog(decision): raise AcquisitionBlocked("robots_"+decision.state)
        return decision
    def acquire_all(self):
        if len(self.plan["items"])>self.auth["limits"]["max_assets"]: raise AcquisitionBlocked("asset_limit")
        for item in self.plan["items"]: self._acquire(item,resume=None)
        return self._publish_outputs(resumes=0)
    def resume(self,checkpoint_relative):
        checkpoint_path=safe_join(self.root,checkpoint_relative); checkpoint=json.loads(checkpoint_path.read_text(encoding="utf-8",errors="strict"))
        part=safe_join(self.root,checkpoint["part_relative_path"]); data=part.read_bytes()
        if len(data)!=checkpoint["bytes_present"] or sha256(data).hexdigest()!=checkpoint["partial_sha256"]: raise AcquisitionBlocked("partial_binding_mismatch")
        if checkpoint["authorization_id"]!=self.auth["authorization_id"] or checkpoint["authorization_fingerprint"]!=self.plan["authorization_fingerprint"]: raise AcquisitionBlocked("resume_authorization_mismatch")
        item=next((x for x in self.plan["items"] if x["candidate_id"]==checkpoint["candidate_id"]),None)
        if not item: raise AcquisitionBlocked("resume_candidate_mismatch")
        self._acquire(item,resume=(checkpoint,part,data)); return self._publish_outputs(resumes=1)
    def _acquire(self,item,resume):
        cid=item["candidate_id"]; sequence=[]; redirects=[]; original=item["url"]; current=original
        attempt=_id("attempt",self.auth["authorization_id"],cid)
        base_headers={}; existing=b""; checkpoint=None; part=None
        if resume:
            checkpoint,part,existing=resume
            current=validate_url(checkpoint["current_url"],self.auth)
            etag=_strong(checkpoint.get("strong_etag"))
            if etag: base_headers={"Range":f"bytes={len(existing)}-","If-Range":etag}
            else:
                existing=b""; part=safe_join(self.root,f"_operations/parts/{attempt}.restart.part")
        try:
            for hop in range(self.auth["limits"]["max_redirects"]+1):
                current=validate_url(current,self.auth); decision=self._robots_allows(current,sequence)
                self.pause(urlsplit(current).hostname)
                self.asset_requests+=1
                response=self._request(current,base_headers)
                headers=_headers(response.headers); sequence.append({"kind":"asset","method":"GET","url":_sanitize(current),"status":response.status,"headers":headers})
                if response.status not in REDIRECTS: break
                if hop>=self.auth["limits"]["max_redirects"]: raise AcquisitionBlocked("redirect_limit")
                location=headers.get("location")
                if not location: raise AcquisitionBlocked("redirect_location_missing")
                target=validate_url(self.resolve(current,location),self.auth)
                if target in [original,*redirects]: raise AcquisitionBlocked("redirect_loop")
                oldhost=urlsplit(current).hostname; redirects.append(target); current=target
                if urlsplit(target).hostname!=oldhost: base_headers={}
            else: raise AcquisitionBlocked("redirect_limit")
            if headers.get("content-encoding", "identity").casefold() not in ("","identity"): raise AcquisitionBlocked("content_encoding_blocked")
            declared=headers.get("content-length")
            if declared and (not declared.isdigit() or int(declared)>self.auth["limits"]["max_bytes_per_asset"]): raise AcquisitionBlocked("content_length_blocked")
            incoming=b"".join(response.chunks)
            if base_headers:
                if response.status==200: existing=b""; part=safe_join(self.root,f"_operations/parts/{attempt}.range-ignored.part")
                elif response.status!=206: raise AcquisitionBlocked("resume_status_invalid")
                else:
                    match=CONTENT_RANGE.fullmatch(headers.get("content-range", "")); expected=_strong(checkpoint.get("strong_etag"))
                    if not match or int(match.group(1))!=len(existing) or headers.get("etag")!=expected: raise AcquisitionBlocked("resume_range_binding_invalid")
                    if checkpoint.get("total_expected") is not None and int(match.group(3))!=checkpoint["total_expected"]: raise AcquisitionBlocked("resume_total_mismatch")
            elif response.status!=200: raise AcquisitionBlocked("asset_status_invalid")
            payload=existing+incoming
            if len(payload)>self.auth["limits"]["max_bytes_per_asset"] or self.total_bytes+len(payload)>self.auth["limits"]["max_total_bytes"]: raise AcquisitionBlocked("byte_limit")
            if declared and response.status==200 and len(payload)!=int(declared): raise AcquisitionBlocked("content_length_mismatch")
            part=part or safe_join(self.root,f"_operations/parts/{attempt}.part"); _atomic_synced(part,payload)
            digest=sha256(payload).hexdigest(); rel=f"payloads/sha256/{digest[:2]}/{digest}"
            final=safe_join(self.root,rel); _atomic_synced(final,payload); self.total_bytes+=len(payload)
            receipt=self._receipt(attempt,cid,original,current,sequence,redirects,"completed","download_complete",digest,len(payload),None,rel)
            receipt_ref=f"receipts/{attempt}.json"; atomic_write(safe_join(self.root,receipt_ref),canonical_bytes(receipt))
            self.receipts.append(receipt)
            provenance="synthetic_fixture" if self.auth["fixture_only"] else "authorized_capture_receipt"
            self.payloads.append({"candidate_id":cid,"relative_path":rel,"expected_sha256":digest,"expected_size":len(payload),
              "provenance_type":provenance,"audit_reference":receipt_ref,"authorization_status":"authorized_with_evidence",
              "declared_mime":headers.get("content-type"),"http_metadata":{"etag":headers.get("etag"),"last_modified":headers.get("last-modified"),
              "final_url":_sanitize(current),"authorization_id":self.auth["authorization_id"],"authorization_fingerprint":self.plan["authorization_fingerprint"],"fixture_only":self.auth["fixture_only"]}})
        except Exception as exc:
            reason=exc.reason if isinstance(exc,AcquisitionBlocked) else getattr(exc,"state","transport_failed")
            state="blocked_redirect" if reason.startswith("redirect") else "blocked_robots" if reason.startswith("robots") else "interrupted" if reason=="stream_interrupted" else "resume_blocked" if resume else "failed_transport"
            partial=existing
            part=part or safe_join(self.root,f"_operations/parts/{attempt}.part")
            if partial: _atomic_synced(part,partial)
            cp=self._checkpoint(cid,original,current,redirects,part,partial,headers if 'headers' in locals() else {},state)
            cp_ref=f"_operations/checkpoints/{attempt}.json"; atomic_write(safe_join(self.root,cp_ref),canonical_bytes(cp))
            self.receipts.append(self._receipt(attempt,cid,original,current,sequence,redirects,state,reason,sha256(partial).hexdigest() if partial else None,len(partial),cp_ref,None))
    def _checkpoint(self,cid,original,current,redirects,part,data,headers,state):
        return {"schema_version":"acquisition-checkpoint-v1","candidate_id":cid,"relation_id":None,"authorization_id":self.auth["authorization_id"],
          "authorization_fingerprint":self.plan["authorization_fingerprint"],"input_fingerprints":{"candidate_set":self.auth["candidate_set_fingerprint"],"extraction":self.auth["extraction_manifest_fingerprint"],"assets":self.auth["asset_manifest_fingerprint"]},
          "original_url":_sanitize(original),"current_url":_sanitize(current),"redirects_completed":[_sanitize(x) for x in redirects],"host":urlsplit(current).hostname,
          "part_relative_path":part.relative_to(self.root.resolve()).as_posix(),"bytes_present":len(data),"partial_sha256":sha256(data).hexdigest(),"total_expected":_expected_total(headers),
          "strong_etag":_strong(headers.get("etag")),"last_modified":headers.get("last-modified"),"content_type":headers.get("content-type"),"state":state,
          "next_action":"resume_or_restart","request_count":self.requests,"operational_timestamps":{"updated_at":self.clock()}}
    def _receipt(self,attempt,cid,original,current,sequence,redirects,state,reason,digest,size,checkpoint,payload):
        return {"schema_version":"acquisition-receipt-v1","attempt_id":attempt,"candidate_id":cid,"authorization_fingerprint":self.plan["authorization_fingerprint"],
          "user_agent":self.auth["user_agent"],"method":"GET","requests":sequence,"robots_decisions":[{"host":h,"status":v[0],"sha256":sha256(v[1]).hexdigest(),"state":v[2].state} for h,v in sorted(self.robots.items())],
          "original_url":_sanitize(original),"final_url":_sanitize(current),"redirects":[_sanitize(x) for x in redirects],"byte_count":size,"sha256":digest,"state":state,"reason":reason,
          "checkpoint_reference":checkpoint,"payload_reference":payload,"transport_policy_version":POLICY_VERSION,"mode":"synthetic" if self.auth["fixture_only"] else "live",
          "operational_timestamps":{"finished_at":self.clock()}}
    def _publish_outputs(self,resumes):
        receipts=b"".join(canonical_bytes(x) for x in self.receipts); reviews=b"".join(canonical_bytes(x) for x in self.reviews)
        payload={"schema_version":"1.0.0","bindings":sorted(self.payloads,key=lambda x:x["candidate_id"])}
        atomic_write(self.root/"acquisition-receipts.jsonl",receipts); atomic_write(self.root/"acquisition-reviews.jsonl",reviews); atomic_write(self.root/"payload-manifest.json",canonical_bytes(payload))
        counts={"requests":self.requests,"responses":self.requests,"robots_requests":sum(1 for r in self.receipts for x in r["requests"] if x["kind"]=="robots"),"asset_requests":self.asset_requests,"redirects":sum(len(r["redirects"]) for r in self.receipts),"bytes":self.total_bytes,"completed":len(self.payloads),"interrupted":sum(r["state"]=="interrupted" for r in self.receipts),"blocked":sum(r["state"].startswith("blocked") or r["state"]=="resume_blocked" for r in self.receipts),"resumes":resumes,"payloads":len(self.payloads),"reviews":len(self.reviews)}
        semantic={"schema_version":"acquisition-manifest-v1","policy_version":POLICY_VERSION,"authorization_id":self.auth["authorization_id"],"authorization_fingerprint":self.plan["authorization_fingerprint"],"input_fingerprints":{"candidate_set":self.auth["candidate_set_fingerprint"],"extraction":self.auth["extraction_manifest_fingerprint"],"assets":self.auth["asset_manifest_fingerprint"]},"output_hashes":{"acquisition-receipts.jsonl":sha256(receipts).hexdigest(),"acquisition-reviews.jsonl":sha256(reviews).hexdigest(),"payload-manifest.json":sha256(canonical_bytes(payload)).hexdigest()},"counts":counts,"mode":"synthetic" if self.auth["fixture_only"] else "live","selection_performed":False,"materialization_performed":False}
        semantic["semantic_fingerprint"]=sha256(canonical_bytes(semantic)).hexdigest(); manifest=semantic|{"operational_timestamps":{"finished_at":self.clock()}}
        atomic_write(self.root/"acquisition-manifest.json",canonical_bytes(manifest)); atomic_write(self.root/"acquisition-report.txt",("state: acquisition-only\nvalidation: pending\nselection: false\nmaterialization: false\n").encode("utf-8")); return manifest

def _atomic_synced(path,data):
    path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_name(path.name+".owned-tmp")
    with temporary.open("wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)

def _expected_total(headers):
    match=CONTENT_RANGE.fullmatch(headers.get("content-range", ""))
    if match: return int(match.group(3))
    length=headers.get("content-length")
    return int(length) if isinstance(length,str) and length.isdigit() else None

def verify_outputs(root:Path):
    manifest=json.loads((root/"acquisition-manifest.json").read_text(encoding="utf-8",errors="strict")); failures=[]
    for name,digest in manifest["output_hashes"].items():
        try: actual=sha256(safe_join(root,name).read_bytes()).hexdigest()
        except OSError: actual=None
        if actual!=digest: failures.append(name)
    payload=json.loads((root/"payload-manifest.json").read_text(encoding="utf-8",errors="strict"))
    for binding in payload["bindings"]:
        try: data=safe_join(root,binding["relative_path"]).read_bytes()
        except OSError: failures.append(binding["relative_path"]); continue
        if len(data)!=binding["expected_size"] or sha256(data).hexdigest()!=binding["expected_sha256"]: failures.append(binding["relative_path"])
    return {"valid":not failures,"failures":sorted(set(failures)),"network_requests":0}
