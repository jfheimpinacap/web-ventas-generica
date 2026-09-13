"""Canonical, tamper-evident local apply checkpoints and JSONL receipts."""
import os,tempfile
from pathlib import Path
from catalog_pipeline_common.serialization import canonical_bytes,content_fingerprint
from .output import write_output_set

class CheckpointError(ValueError): pass

def seal(value):
    result=dict(value); result.pop("checkpoint_fingerprint",None)
    result["checkpoint_fingerprint"]=content_fingerprint(result); return result

def validate(value):
    if value.get("checkpoint_fingerprint")!=content_fingerprint({k:v for k,v in value.items() if k!="checkpoint_fingerprint"}): raise CheckpointError("CHECKPOINT_TAMPERED")
    order=value["operation_order"]; completed=value["completed_operation_ids"]
    if completed!=order[:len(completed)]: raise CheckpointError("COMPLETED_NOT_PREFIX")
    if value.get("next_operation")!=len(completed) or len(value.get("receipts",[]))!=len(completed): raise CheckpointError("CHECKPOINT_PROGRESS_INVALID")
    counters=value.get("counters",{})
    if counters.get("operations_completed")!=len(completed) or counters.get("mutations_confirmed")!=len(completed): raise CheckpointError("CHECKPOINT_COUNTERS_INVALID")
    return value

def initial(bundle):
    return seal({"schema_version":"1.0.0","rules_version":"jem-local-apply-v1","package_sha256":bundle["package_sha256"],"plan_fingerprint":bundle["plan_fingerprint"],"dry_run_fingerprint":bundle["dry_run_fingerprint"],"authorization_fingerprint":bundle["authorization_fingerprint"],"snapshot_fingerprint":bundle["snapshot_fingerprint"],"target_fingerprint":bundle["target_fingerprint"],"operation_set_fingerprint":bundle["operation_set_fingerprint"],"fixture_only":bundle.get("classification")=="fixture_only","operation_order":[x["operation_id"] for x in bundle["operations"]],"external_bindings":bundle["external_bindings"],"produced_bindings":[],"completed_operation_ids":[],"receipts":[],"next_operation":0,"in_flight":None,"counters":{"intents_registered":0,"requests_dispatched":0,"mutations_confirmed":0,"operations_completed":0,"operations_reconciled":0},"state":"local_apply_ready"})

def write_checkpoint(directory,value):
    target=Path(directory); target.mkdir(parents=True,exist_ok=True); sealed=seal(value)
    documents={"local-operation-receipts.jsonl":b"".join(canonical_bytes(item) for item in sealed["receipts"]),"local-apply-checkpoint.json":canonical_bytes(sealed)}; staged=[]
    try:
        for filename,data in documents.items():
            fd,name=tempfile.mkstemp(prefix="."+filename+".writing-",suffix=".tmp",dir=target)
            with os.fdopen(fd,"wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            staged.append((Path(name),target/filename))
        for temporary,path in staged: os.replace(temporary,path)
        from .output import _fsync_directory_if_supported
        _fsync_directory_if_supported(target)
    finally:
        for temporary,_ in staged: temporary.unlink(missing_ok=True)

def append_receipts(directory,receipts):
    data=b"".join(canonical_bytes(item) for item in receipts)
    write_output_set(directory,{"local-operation-receipts.jsonl":data})
