"""Deterministic future-operation graph and mutation-free simulation."""
from __future__ import annotations
import hashlib, json
from catalog_acquisition.serialization import canonical_bytes, content_fingerprint
from .bindings import BindingResolver, MissingBindingError

def _hash(value): return hashlib.sha256(canonical_bytes(value)).hexdigest()
def operation(kind,action,identity,endpoint,payload,requires=(),produces=(),depends_on=(),sources=()):
    core={"kind":kind,"action":action,"entity_identity":identity,"endpoint":endpoint,"future_method":"POST" if action=="create" else "NONE","payload_template":payload,
          "required_bindings":list(requires),"produced_bindings":list(produces),"dependencies":sorted(depends_on),"source_references":sorted(sources),"reconciliation_status":action,"blocking_reasons":[],"rules_version":"jem-import-v1"}
    core["operation_id"]="op-"+_hash(core)[:20]; core["fingerprint"]=_hash(core); return core

def topological(operations):
    by_id={x["operation_id"]:x for x in operations}
    if len(by_id)!=len(operations): raise ValueError("DUPLICATE_OPERATION")
    result=[]; pending=set(by_id)
    while pending:
        ready=sorted(x for x in pending if set(by_id[x]["dependencies"])<=set(y["operation_id"] for y in result))
        if not ready: raise ValueError("DEPENDENCY_CYCLE_OR_MISSING")
        for key in ready: result.append(by_id[key]); pending.remove(key)
    return result

def build_plan(package,snapshot,policy,contract_fingerprint,operations,external_bindings,reviews=()):
    ordered=topological(operations)
    inputs={"package_sha256":package["verification"]["zip_sha256"],"package_content_fingerprint":package["manifest"]["content_fingerprint"],"audit_fingerprint":package["manifest"]["audit_manifest_fingerprint"],"decision_fingerprint":package["manifest"]["decision_fingerprint"],"snapshot_semantic_fingerprint":snapshot["semantic_fingerprint"],"contract_fingerprint":contract_fingerprint,"import_policy_fingerprint":content_fingerprint(policy)}
    value={"schema_version":"1.0.0","rules_version":"jem-import-v1","inputs":inputs,"operations":ordered,"external_bindings":sorted(external_bindings,key=lambda x:(x["namespace"],x["key"])),"reviews":list(reviews),"apply_supported":False,"mutation_supported":False,"import_authorized":False,"publication_authorized":False}
    value["plan_fingerprint"]=content_fingerprint(value); return value

def simulate(plan):
    resolver=BindingResolver(plan["external_bindings"])
    errors=[]; simulated=[]
    try:
        for item in topological(plan["operations"]):
            for reference in item["required_bindings"]: resolver.resolve(reference)
            for produced in item["produced_bindings"]:
                symbolic="<symbolic:"+produced["namespace"]+":"+produced["key"]+">"
                resolver.produce(produced,symbolic); simulated.append({**produced,"value":symbolic,"status":"simulated"})
    except MissingBindingError as error: errors.append(error.as_dict())
    except ValueError as error: errors.append({"code":str(error).split(":",1)[0],"detail":str(error)})
    state="preflight_failed" if errors else ("manual_review_required" if plan["reviews"] else "dry_run_ready")
    result={"schema_version":"1.0.0","rules_version":"jem-dry-run-v1","plan_fingerprint":plan["plan_fingerprint"],"state":state,"errors":errors,"simulated_bindings":simulated,"dry_run_allowed":not errors,"apply_supported":False,"mutation_supported":False,"mutations_attempted":0,"mutations_completed":0,"import_authorized":False,"publication_authorized":False,"network_requests":0,"mutating_network_requests":0}
    result["dry_run_fingerprint"]=content_fingerprint(result); return result
