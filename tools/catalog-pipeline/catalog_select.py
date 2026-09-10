#!/usr/bin/env python3
"""Offline-only selection CLI; it consumes approvals but cannot create them."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from catalog_acquisition.selection import (build_materialization_plan, materialize,
  select_assets, semantic_fingerprint, verify_tree)
from catalog_acquisition.serialization import canonical_bytes

def read(path): return json.loads(Path(path).read_text(encoding="utf-8",errors="strict"))
def parser():
 p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
 for command in ("plan","select"):
  c=sub.add_parser(command); c.add_argument("--inputs",required=True)
  if command=="select": c.add_argument("--output-root",required=True)
 m=sub.add_parser("materialize"); m.add_argument("--selection-manifest",required=True); m.add_argument("--object-root",required=True); m.add_argument("--destination-root",required=True); m.add_argument("--fingerprint",required=True)
 v=sub.add_parser("verify"); v.add_argument("--selection-manifest",required=True); v.add_argument("--destination-root",required=True)
 return p
def main(argv=None):
 args=parser().parse_args(argv)
 if args.command=="verify": result=verify_tree(Path(args.destination_root),read(args.selection_manifest)); print(canonical_bytes(result).decode(),end=""); return 0 if result["valid"] else 3
 if args.command=="materialize":
  manifest=read(args.selection_manifest); result=materialize(manifest,args.object_root,args.destination_root,args.fingerprint); print(canonical_bytes(result).decode(),end=""); return 0 if result["state"] in {"completed","already_complete"} else 3
 bundle=read(args.inputs); decisions,reviews=select_assets(bundle["candidates"],bundle.get("approvals",[])); plan=build_materialization_plan(decisions,bundle["candidates"],bundle["products"],bundle["object_root"],bundle["destination_root"])
 manifest={"schema_version":"1.0.0","selection_policy_version":"selection-v1","naming_policy_version":"catalog-layout-v1","input_hashes":bundle["input_hashes"],"input_fingerprints":bundle["input_fingerprints"],"decisions":decisions,"reviews":reviews,"operations":plan,"offline":True,"network_requests":0,"api_calls":0,"published":False,"imported":False}
 manifest["fingerprint"]=semantic_fingerprint(manifest)
 if args.command=="plan": print(canonical_bytes(manifest).decode(),end=""); return 0 if not reviews else 3
 out=Path(args.output_root); out.mkdir(parents=True,exist_ok=False)
 for name,values in (("asset-selection-decisions.jsonl",decisions),("asset-selection-reviews.jsonl",reviews),("materialization-plan.jsonl",plan)):
  (out/name).write_bytes(b"".join(canonical_bytes(x) for x in values))
 (out/"materialized-assets.jsonl").write_bytes(b""); (out/"selection-manifest.json").write_bytes(canonical_bytes(manifest))
 (out/"selection-report.txt").write_text(f"offline: true\ndecisions: {len(decisions)}\nreviews: {len(reviews)}\noperations: {len(plan)}\n",encoding="utf-8",newline="\n")
 return 0 if not reviews else 3
if __name__=="__main__": raise SystemExit(main())
