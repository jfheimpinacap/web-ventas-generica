#!/usr/bin/env python3
"""Separate acquisition CLI. Authorization is consumed, never created or approved."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from catalog_acquisition.acquisition import AcquisitionSession,verify_outputs
from catalog_acquisition.acquisition_plan import build_plan
from catalog_acquisition.asset_http_transport import SafeAssetHttpTransport
from catalog_acquisition.discovery import SOURCES
from catalog_acquisition.serialization import canonical_bytes

def _json(path): return json.loads(Path(path).read_text(encoding="utf-8",errors="strict"))
def parser():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    for command in ("plan","acquire","resume"):
        c=sub.add_parser(command); c.add_argument("--authorization",required=True); c.add_argument("--input-root",required=True); c.add_argument("--source",choices=sorted(SOURCES),required=True)
        if command!="plan": c.add_argument("--output-root",required=True); c.add_argument("--authorization-fingerprint",required=True)
        if command=="resume": c.add_argument("--checkpoint",required=True)
    v=sub.add_parser("verify"); v.add_argument("--output-root",required=True)
    return p
def _inputs(args):
    root=Path(args.input_root); auth=_json(args.authorization); source=SOURCES[args.source]
    candidates=_json(root/"acquisition-candidates.json")["candidates"]; bindings=_json(root/"acquisition-inputs.json")
    plan=build_plan(authorization=auth,authorization_root=Path(args.authorization).parent,source=source,
      source_definition_fingerprint=bindings["source_definition_fingerprint"],extraction_fingerprint=bindings["extraction_manifest_fingerprint"],asset_fingerprint=bindings["asset_manifest_fingerprint"],candidates=candidates)
    return auth,plan
def main(argv=None):
    args=parser().parse_args(argv)
    if args.command=="verify": result=verify_outputs(Path(args.output_root)); print(canonical_bytes(result).decode(),end=""); return 0 if result["valid"] else 3
    auth,plan=_inputs(args)
    if args.command=="plan": print(canonical_bytes(plan).decode(),end=""); return 0 if plan["transport_allowed"] else 3
    if not plan["transport_allowed"] or args.authorization_fingerprint!=plan["authorization_fingerprint"]: print("acquisition blocked before transport",file=sys.stderr); return 3
    if auth["fixture_only"]: print("fixture-only authorization cannot activate CLI transport",file=sys.stderr); return 3
    transport=SafeAssetHttpTransport(user_agent=auth["user_agent"],timeout=auth["limits"]["timeout_seconds"],max_header_bytes=auth["limits"]["max_headers_bytes"],max_chunk_bytes=auth["limits"]["max_chunk_bytes"])
    session=AcquisitionSession(plan=plan,authorization=auth,transport=transport,output_root=Path(args.output_root),clock=lambda:"operational",pause=lambda host:None)
    result=session.resume(args.checkpoint) if args.command=="resume" else session.acquire_all(); print(canonical_bytes(result).decode(),end=""); return 0
if __name__=="__main__": raise SystemExit(main())
