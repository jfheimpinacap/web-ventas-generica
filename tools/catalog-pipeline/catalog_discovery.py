#!/usr/bin/env python3
"""CLI for safe EP/GAM discovery. Capture is sequential and opt-in."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from catalog_acquisition.discovery import SOURCES
from catalog_acquisition.discovery_adapters import ADAPTERS
from catalog_acquisition.http_transport import HttpPolicy,SafeHttpTransport
from catalog_acquisition.orchestrator import (capture_source,compare,replay,semantic_config,
 config_fingerprint,structure_gate,validate_resume_preflight)
from catalog_acquisition.paths import safe_join
from catalog_acquisition.serialization import canonical_bytes
from catalog_acquisition.storage import atomic_write

EXIT_OK=0; EXIT_ERROR=1; EXIT_INCOMPLETE=2; EXIT_BLOCKED=3; EXIT_INCOMPATIBLE=4
def parser():
 p=argparse.ArgumentParser(description="Safe, bounded catalog discovery")
 s=p.add_subparsers(dest="command",required=True)
 def sources(x): x.add_argument("--source",choices=("ep","gam","all"),default="all"); x.add_argument("--max-pages",type=int,default=100); x.add_argument("--max-depth",type=int,default=5)
 q=s.add_parser("plan"); sources(q); q.add_argument("--output-root")
 q=s.add_parser("capture"); sources(q); q.add_argument("--output-root",required=True); q.add_argument("--allow-network",action="store_true"); q.add_argument("--run-id",required=True); q.add_argument("--continue-run",action="store_true")
 q=s.add_parser("replay"); q.add_argument("--snapshot-manifest",required=True); q.add_argument("--snapshot-root",required=True); q.add_argument("--output-dir",required=True)
 q=s.add_parser("compare"); q.add_argument("--old-manifest",required=True); q.add_argument("--new-manifest",required=True); q.add_argument("--output")
 return p
def _selected(v): return ("ep","gam") if v=="all" else (v,)
def _root(value):
 if not value: raise ValueError("--output-root is required for live capture")
 p=Path(value).expanduser().resolve()
 if p==Path(p.anchor) or p==Path.cwd().resolve(): raise ValueError("dangerous output root refused")
 return p
def main(argv=None):
 a=parser().parse_args(argv)
 try:
  if a.command=="plan":
   selected=_selected(a.source); cfg=semantic_config(selected,a.output_root or "<required-for-live>",a.max_pages,a.max_depth,HttpPolicy().user_agent)
   gates={key:{"source":key,"adapter":ADAPTERS[key].adapter_id,
    "adapter_version":ADAPTERS[key].adapter_version,"structure_verified":SOURCES[key].structure_verified,
    "state":"blocked" if structure_gate(SOURCES[key],ADAPTERS[key]) else "planned",
    "reason":structure_gate(SOURCES[key],ADAPTERS[key]),"requests_attempted":0,
    "origin_responses":0,"snapshots_persisted":0} for key in selected}
   print(json.dumps({"network_requests":0,"snapshots":0,"source_preflight":gates,
    "configuration":cfg,"config_fingerprint":config_fingerprint(cfg)},indent=2,sort_keys=True)); return EXIT_OK
  if a.command=="replay":
   manifest=json.loads(Path(a.snapshot_manifest).read_text(encoding="utf-8")); replay(manifest,Path(a.snapshot_root),Path(a.output_dir),ADAPTERS); return EXIT_OK
  if a.command=="compare":
   old=json.loads(Path(a.old_manifest).read_text(encoding="utf-8")); new=json.loads(Path(a.new_manifest).read_text(encoding="utf-8")); result=compare(old,new,a.old_manifest,a.new_manifest)
   if a.output: atomic_write(Path(a.output),canonical_bytes(result))
   else: print(json.dumps(result,indent=2,sort_keys=True))
   return EXIT_INCOMPATIBLE if result["status"]=="comparison_blocked" else EXIT_OK
  if not a.allow_network: raise ValueError("capture requires explicit --allow-network")
  root=_root(a.output_root); selected=_selected(a.source); cfg=semantic_config(selected,root,a.max_pages,a.max_depth,HttpPolicy().user_agent); manifest_path=safe_join(root,f"_pipeline/manifests/{a.run_id}.json")
  if a.continue_run:
   if not manifest_path.exists(): raise ValueError("continued run manifest does not exist")
   validate_resume_preflight(json.loads(manifest_path.read_text(encoding="utf-8")),cfg,
    {k:SOURCES[k] for k in selected},{k:ADAPTERS[k] for k in selected},HttpPolicy().user_agent)
  transport=SafeHttpTransport(); robots={}; states={}; source_results={}
  for key in selected:
   result=capture_source(SOURCES[key],ADAPTERS[key],transport,
    config_fingerprint_value=config_fingerprint(cfg),max_pages=a.max_pages,max_depth=a.max_depth)
   source_results[key]={k:v for k,v in result.__dict__.items() if k!="responses"}
   robots[key]=result.robots; states[key]=result.state
  manifest={"schema_version":"discovery-run-state-v1","run_id":a.run_id,"configuration":cfg,
   "config_fingerprint":config_fingerprint(cfg),"robots":robots,"states":states,
   "source_results":source_results,"snapshots":[],"start_urls":{k:SOURCES[k].start_url for k in selected}}
  atomic_write(manifest_path,canonical_bytes(manifest)); return EXIT_BLOCKED if "blocked" in states.values() else EXIT_INCOMPLETE
 except Exception as exc:
  print(json.dumps({"error":{"type":type(exc).__name__,"message":str(exc)}},sort_keys=True),file=sys.stderr); return EXIT_ERROR
if __name__=="__main__": raise SystemExit(main())
