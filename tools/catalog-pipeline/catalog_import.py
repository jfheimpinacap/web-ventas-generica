#!/usr/bin/env python3
"""Offline/read-only JEM importer phase one. There is intentionally no apply command."""
import argparse,hashlib,json,sys
from pathlib import Path
from catalog_pipeline_common.serialization import canonical_bytes,content_fingerprint
from catalog_acquisition.packaging import verify_package
from jem_nexus_import.local_client import LocalJemJsonReader,LocalReadError,READ_PATHS
from jem_nexus_import.snapshot import validate_snapshot,semantic_fingerprint,SnapshotError
from jem_nexus_import.package_input import read_verified_package,ImportInputError
from jem_nexus_import.reconciliation import build_operations
from jem_nexus_import.planning import build_plan,simulate
from jem_nexus_import.output import write_output_set

def parser():
    root=argparse.ArgumentParser(); commands=root.add_subparsers(dest="command",required=True)
    snap=commands.add_parser("snapshot-local"); snap.add_argument("--base-url",required=True); snap.add_argument("--contract-fingerprint",required=True); snap.add_argument("--output",required=True)
    plan=commands.add_parser("plan"); plan.add_argument("--package",required=True); plan.add_argument("--receipt",required=True); plan.add_argument("--snapshot",required=True); plan.add_argument("--policy",required=True); plan.add_argument("--output",required=True)
    dry=commands.add_parser("dry-run"); dry.add_argument("--plan",required=True); dry.add_argument("--output",required=True)
    return root
def _read(path): return json.loads(Path(path).read_text(encoding="utf-8",errors="strict"))
def capture_snapshot(reader,contract_fingerprint,classification="local_development"):
    collections={}; evidence=[]
    for name in sorted(READ_PATHS):
        body=reader.read_collection(name); collections[name]=body if isinstance(body,list) else body.get("items",[])
        raw=canonical_bytes(body); evidence.append({"collection":name,"path":READ_PATHS[name],"status":200,"mime":"application/json","response_sha256":hashlib.sha256(raw).hexdigest(),"pages_received":1,"pages_expected":1,"complete":True})
    value={"schema_version":"1.0.0","complete":True,"classification":classification,"contract_fingerprint":contract_fingerprint,"collections":collections,"endpoints":evidence}
    value["semantic_fingerprint"]=semantic_fingerprint(value); return validate_snapshot(value,contract_fingerprint)
def create_plan(package_path,receipt_path,snapshot_path,policy_path,verifier=verify_package):
    policy=_read(policy_path); snap=validate_snapshot(_read(snapshot_path),policy["contract_fingerprint"])
    view=read_verified_package(package_path,receipt_path,policy.get("package_policy",{}),verifier)
    graph=build_operations(view,snap,policy); plan=build_plan(view,snap,policy,policy["contract_fingerprint"],graph["operations"],graph["external_bindings"],graph["reviews"])
    plan["reconciliations"]=graph["reconciliations"]; plan["retained_documents"]=graph["retained_documents"]
    plan.pop("plan_fingerprint",None)
    plan["plan_fingerprint"]=content_fingerprint(plan)
    return plan
def plan_outputs(plan,snapshot):
    operations=b"".join(canonical_bytes(x) for x in plan["operations"]); reviews=b"".join(canonical_bytes(x) for x in plan["reviews"])
    preflight={"state":"manual_review_required" if plan["reviews"] else "dry_run_ready","blocking":bool(plan["reviews"]),"apply_supported":False,"mutation_supported":False,"mutations_attempted":0,"mutations_completed":0}
    return {"jem-state-snapshot.json":snapshot,"import-preflight.json":preflight,"import-bindings.json":{"external":plan["external_bindings"],"produced":[b for op in plan["operations"] for b in op["produced_bindings"]]},"import-operations.jsonl":operations,"import-plan.json":plan,"import-reviews.jsonl":reviews}
def main(argv=None,reader_factory=LocalJemJsonReader,verifier=verify_package):
    args=parser().parse_args(argv)
    try:
        if args.command=="snapshot-local":
            # Capture orchestration is deliberately explicit; callers provide real contract metadata in Prompt 285.
            reader=reader_factory(args.base_url); result=capture_snapshot(reader,args.contract_fingerprint)
            write_output_set(args.output,{"jem-state-snapshot.json":result}); return 0
        if args.command=="plan":
            result=create_plan(args.package,args.receipt,args.snapshot,args.policy,verifier); write_output_set(args.output,plan_outputs(result,_read(args.snapshot)))
            return 3 if result["reviews"] else 0
        plan=_read(args.plan); result=simulate(plan)
        write_output_set(args.output,{"import-dry-run-manifest.json":result,"import-dry-run-report.txt":canonical_bytes(result)})
        return 0 if result["state"]=="dry_run_ready" else 3
    except (ImportInputError,LocalReadError,SnapshotError,json.JSONDecodeError) as error:
        code=getattr(error,"code","INPUT_INVALID"); sys.stdout.buffer.write(canonical_bytes({"error":code}))
        if isinstance(error,LocalReadError): return 5
        return 4 if "FINGERPRINT" in code else 2
if __name__=="__main__": raise SystemExit(main())
