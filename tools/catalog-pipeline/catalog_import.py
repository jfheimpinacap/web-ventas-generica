#!/usr/bin/env python3
"""Composition root for offline planning and explicitly local-only execution."""
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
from jem_nexus_local_transport import get_json_bytes
from jem_nexus_import.authorization import AuthorizationError
from jem_nexus_import.execution import ExecutionError,execute,persist_reconciliation,prepare_execution_bundle,reconcile_in_flight,validate_resume_checkpoint,validate_resume_snapshot
from jem_nexus_import.verification import SnapshotObserver,verify_managed
from jem_nexus_import.checkpoint import CheckpointError,write_checkpoint
from jem_nexus_local_mutation_transport import LocalMutationTransport,MutationTransportError,target_fingerprint

def parser():
    root=argparse.ArgumentParser(); commands=root.add_subparsers(dest="command",required=True)
    snap=commands.add_parser("snapshot-local"); snap.add_argument("--base-url",required=True); snap.add_argument("--contract-fingerprint",required=True); snap.add_argument("--output",required=True)
    plan=commands.add_parser("plan"); plan.add_argument("--package",required=True); plan.add_argument("--receipt",required=True); plan.add_argument("--snapshot",required=True); plan.add_argument("--policy",required=True); plan.add_argument("--output",required=True)
    dry=commands.add_parser("dry-run"); dry.add_argument("--plan",required=True); dry.add_argument("--output",required=True)
    required=("package","receipt","plan","dry-run-manifest","snapshot","policy","authorization","base-url","checkpoint-dir","confirm-plan-fingerprint","confirm-dry-run-fingerprint")
    for command in ("apply-local","resume-local"):
        item=commands.add_parser(command)
        for name in required: item.add_argument("--"+name,required=True)
    verify=commands.add_parser("verify-local")
    for name in ("plan","checkpoint","base-url","output"): verify.add_argument("--"+name,required=True)
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
def main(argv=None,reader_factory=None,verifier=verify_package,mutator_factory=None):
    args=parser().parse_args(argv)
    try:
        if args.command=="snapshot-local":
            # Capture orchestration is deliberately explicit; callers provide real contract metadata in Prompt 285.
            reader=reader_factory(args.base_url) if reader_factory is not None else LocalJemJsonReader(args.base_url,transport=get_json_bytes)
            result=capture_snapshot(reader,args.contract_fingerprint)
            write_output_set(args.output,{"jem-state-snapshot.json":result}); return 0
        if args.command=="plan":
            result=create_plan(args.package,args.receipt,args.snapshot,args.policy,verifier); write_output_set(args.output,plan_outputs(result,_read(args.snapshot)))
            return 3 if result["reviews"] else 0
        if args.command=="dry-run":
            plan=_read(args.plan); result=simulate(plan)
            write_output_set(args.output,{"import-dry-run-manifest.json":result,"import-dry-run-report.txt":canonical_bytes(result)})
            return 0 if result["state"]=="dry_run_ready" else 3
        if args.command=="verify-local":
            plan=_read(args.plan); checkpoint=_read(args.checkpoint)
            reader=reader_factory(args.base_url) if reader_factory else LocalJemJsonReader(args.base_url,transport=get_json_bytes)
            snapshot=capture_snapshot(reader,plan["inputs"]["contract_fingerprint"])
            report=verify_managed(plan,checkpoint,SnapshotObserver(snapshot))
            if report["result"]=="verified":
                checkpoint["state"]="local_apply_verified"; write_checkpoint(Path(args.checkpoint).parent,checkpoint)
            write_output_set(args.output,{"local-verification-report.json":report,"local-verification-report.txt":canonical_bytes(report)})
            return 0 if report["result"]=="verified" else 8
        plan=_read(args.plan); dry=_read(args.dry_run_manifest)
        if args.confirm_plan_fingerprint!=plan.get("plan_fingerprint") or args.confirm_dry_run_fingerprint!=dry.get("dry_run_fingerprint"): raise AuthorizationError("CLI_CONFIRMATION_MISMATCH")
        policy=_read(args.policy); authorization=_read(args.authorization)
        package=read_verified_package(args.package,args.receipt,policy.get("package_policy",{}),verifier)
        baseline=validate_snapshot(_read(args.snapshot),policy["contract_fingerprint"])
        reader=reader_factory(args.base_url) if reader_factory else LocalJemJsonReader(args.base_url,transport=get_json_bytes)
        current=capture_snapshot(reader,policy["contract_fingerprint"])
        target=target_fingerprint(args.base_url)
        destination=Path(args.checkpoint_dir)
        checkpoint=_read(destination/"local-apply-checkpoint.json") if args.command=="resume-local" else None
        bundle=prepare_execution_bundle(package,plan,dry,current,policy,authorization,target,real_transport=mutator_factory is None,resume=checkpoint is not None)
        preflight={key:value for key,value in bundle.items() if key not in ("package_entries","operations")}
        preflight["operation_order"]=[item["operation_id"] for item in bundle["operations"]]
        write_output_set(destination,{"local-apply-preflight.json":preflight})
        def persist(value): write_checkpoint(destination,value)
        if checkpoint is not None:
            checkpoint=validate_resume_checkpoint(bundle,checkpoint)
            validate_resume_snapshot(bundle,checkpoint,baseline,current)
            if checkpoint.get("in_flight") is not None:
                checkpoint=persist_reconciliation(bundle,checkpoint,reconcile_in_flight(bundle,checkpoint,current),persist)
        expected={key:authorization[key] for key in authorization if key not in ("authorization_fingerprint","schema_version","rules_version","classification","fixture_only","local_only","production_allowed","publication_allowed","allow_apply","allow_resume","allow_verify")}
        if checkpoint is not None and checkpoint["state"]=="local_apply_completed_pending_verify": result=checkpoint
        else:
            mutator=mutator_factory(bundle) if mutator_factory else LocalMutationTransport(args.base_url,authorization,expected)
            result=execute(bundle,mutator,persist,checkpoint)
        manifest={"schema_version":"1.0.0","fixture_only":authorization["classification"]=="fixture_only","state":result["state"],"counters":result["counters"],"publication_allowed":False,"target_fingerprint":target,"classification":authorization["classification"]}
        write_output_set(destination,{"local-apply-manifest.json":manifest,"local-apply-report.txt":canonical_bytes(manifest)})
        return 0
    except (ImportInputError,LocalReadError,SnapshotError,AuthorizationError,ExecutionError,CheckpointError,MutationTransportError,json.JSONDecodeError) as error:
        code=getattr(error,"code","INPUT_INVALID"); sys.stdout.buffer.write(canonical_bytes({"error":code}))
        if isinstance(error,LocalReadError): return 5
        return 4 if "FINGERPRINT" in code else 2
if __name__=="__main__": raise SystemExit(main())
