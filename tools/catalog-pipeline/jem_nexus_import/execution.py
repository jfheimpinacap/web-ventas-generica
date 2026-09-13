"""Network-free preflight and serial execution over an injected typed mutator."""
import hashlib
from copy import deepcopy
from catalog_pipeline_common.serialization import canonical_bytes,content_fingerprint
from .authorization import validate_authorization
from .bindings import BindingResolver
from .planning import simulate,topological
from .checkpoint import initial,seal,validate

SAFE_PRODUCT={"price":None,"price_visible":False,"is_featured":False,"is_published":False}
ALLOWED_ENDPOINTS={"category":"/api/categories","brand":"/api/brands","supplier":"/api/suppliers","product":"/api/products","spec":"/api/product-specs","image":"/api/product-images","technical_sheet":"/api/technical-sheets"}
class ExecutionError(ValueError):
    def __init__(self,code): self.code=code; super().__init__(code)

def operation_set_fingerprint(operations): return content_fingerprint([x["fingerprint"] for x in operations])
def prepare_execution_bundle(package,plan,dry_run,snapshot,policy,authorization,target_fingerprint,real_transport=False,resume=False):
    ordered=topological(plan["operations"]); operation_set=operation_set_fingerprint(ordered)
    if plan.get("reviews") or dry_run.get("errors") or dry_run.get("state")!="dry_run_ready": raise ExecutionError("DRY_RUN_NOT_READY")
    if dry_run.get("apply_supported") is not False: raise ExecutionError("DRY_RUN_CONTRACT_INVALID")
    if not resume and snapshot["semantic_fingerprint"]!=plan["inputs"]["snapshot_semantic_fingerprint"]: raise ExecutionError("LOCAL_STATE_CHANGED")
    if simulate(plan)["state"]!="dry_run_ready": raise ExecutionError("GRAPH_INVALID")
    expected={"package_sha256":package["verification"]["zip_sha256"],"plan_fingerprint":plan["plan_fingerprint"],"dry_run_fingerprint":dry_run["dry_run_fingerprint"],"snapshot_fingerprint":plan["inputs"]["snapshot_semantic_fingerprint"] if resume else snapshot["semantic_fingerprint"],"contract_fingerprint":plan["inputs"]["contract_fingerprint"],"policy_fingerprint":plan["inputs"]["import_policy_fingerprint"],"operation_set_fingerprint":operation_set,"operation_count":len(ordered),"allowed_operation_kinds":sorted({x["kind"] for x in ordered}),"target_fingerprint":target_fingerprint}
    auth=validate_authorization(authorization,expected,real_transport=real_transport)
    for op in ordered:
        if op["future_method"]!="POST" or ALLOWED_ENDPOINTS.get(op["kind"])!=op["endpoint"]: raise ExecutionError("ENDPOINT_NOT_ALLOWED")
        if op["kind"]=="product" and any(op["payload_template"].get(k)!=v for k,v in SAFE_PRODUCT.items()): raise ExecutionError("UNSAFE_PRODUCT_DEFAULTS")
    return {**expected,"authorization_fingerprint":auth["authorization_fingerprint"],"classification":auth["classification"],"operations":deepcopy(ordered),"external_bindings":deepcopy(plan["external_bindings"]),"package_entries":dict(package["entries"]),"state":"local_apply_ready"}

def _materialize(value,resolver):
    if isinstance(value,dict) and set(("scope","namespace","key","binding_type"))<=set(value): return resolver.resolve(value)
    if isinstance(value,dict): return {key:_materialize(item,resolver) for key,item in value.items()}
    if isinstance(value,list): return [_materialize(item,resolver) for item in value]
    return value

COLLECTIONS={"category":"categories","brand":"brands","supplier":"suppliers","product":"products","spec":"product_specs","image":"product_images","technical_sheet":"technical_sheets"}
BINARY_KINDS=frozenset(("image","technical_sheet"))
RECONCILIATION_RESULTS=frozenset(("exact_match","absent","divergent","ambiguous","unobservable"))

def _identity_fields(operation,payload):
    by_kind={"category":("slug",),"brand":("slug",),"supplier":("name",),"product":("slug",),"spec":("product_id","key"),"image":("product_id",),"technical_sheet":("name",)}
    fields=by_kind[operation["kind"]]; source=payload.get("multipart",{}) if operation["kind"] in BINARY_KINDS else payload
    return {key:source.get(key) for key in fields if source.get(key) is not None}

def validate_resume_checkpoint(bundle,checkpoint):
    cp=validate(checkpoint)
    expected={"package_sha256":bundle["package_sha256"],"plan_fingerprint":bundle["plan_fingerprint"],"dry_run_fingerprint":bundle["dry_run_fingerprint"],"authorization_fingerprint":bundle["authorization_fingerprint"],"snapshot_fingerprint":bundle["snapshot_fingerprint"],"target_fingerprint":bundle["target_fingerprint"],"operation_set_fingerprint":bundle["operation_set_fingerprint"],"operation_order":[item["operation_id"] for item in bundle["operations"]]}
    for key,value in expected.items():
        if cp.get(key)!=value: raise ExecutionError("CHECKPOINT_MISMATCH:"+key)
    return cp

def validate_resume_snapshot(bundle,checkpoint,baseline,current):
    """Allow only exact effects of the completed prefix and current intent."""
    cp=validate_resume_checkpoint(bundle,checkpoint)
    if baseline.get("semantic_fingerprint")!=cp["snapshot_fingerprint"]: raise ExecutionError("BASE_SNAPSHOT_MISMATCH")
    allowed_ids={}
    for receipt in cp["receipts"]:
        allowed_ids.setdefault(COLLECTIONS[receipt["kind"]],set()).add(receipt["resource_id"])
        operation=next((item for item in bundle["operations"] if item["operation_id"]==receipt["operation_id"]),None)
        if operation is None: raise ExecutionError("RECEIPT_OPERATION_MISSING")
        resolver=BindingResolver(cp["external_bindings"],cp["produced_bindings"]); payload=_materialize(deepcopy(operation["payload_template"]),resolver)
        observed=[item for item in current["collections"][COLLECTIONS[operation["kind"]]] if item.get("id")==receipt["resource_id"]]
        managed={key:value for key,value in payload.items() if key!="multipart" and not isinstance(value,(dict,list))}
        if operation["kind"] in BINARY_KINDS:
            expected_hash=payload["multipart"].get("sha256")
            if not expected_hash or len(observed)!=1 or observed[0].get("sha256")!=expected_hash: raise ExecutionError("COMPLETED_RESOURCE_UNOBSERVABLE_OR_CHANGED")
        elif len(observed)!=1 or any(observed[0].get(key)!=value for key,value in managed.items()): raise ExecutionError("COMPLETED_RESOURCE_CHANGED")
    for name,base_items in baseline["collections"].items():
        now=current["collections"][name]; base_by_id={item.get("id"):item for item in base_items}
        now_by_id={item.get("id"):item for item in now if item.get("id") in base_by_id}
        if len(now_by_id)!=len(base_by_id) or any(now_by_id.get(key)!=value for key,value in base_by_id.items()): raise ExecutionError("LOCAL_STATE_CHANGED")
        unexplained=[item for item in now if item.get("id") not in base_by_id and item.get("id") not in allowed_ids.get(name,set())]
        if cp.get("in_flight") is not None and name==COLLECTIONS[cp["in_flight"]["operation_kind"]]:
            operation=bundle["operations"][len(cp["completed_operation_ids"])]
            resolver=BindingResolver(cp["external_bindings"],cp["produced_bindings"]); payload=_materialize(deepcopy(operation["payload_template"]),resolver); identity=_identity_fields(operation,payload)
            unexplained=[item for item in unexplained if not identity or not all(item.get(key)==value for key,value in identity.items())]
        if unexplained: raise ExecutionError("LOCAL_STATE_CHANGED")
    return current

def reconcile_in_flight(bundle,checkpoint,snapshot):
    """Classify an uncertain POST strictly from complete snapshot evidence."""
    cp=validate_resume_checkpoint(bundle,checkpoint); intent=cp.get("in_flight")
    if intent is None: raise ExecutionError("IN_FLIGHT_REQUIRED")
    index=len(cp["completed_operation_ids"])
    if index>=len(bundle["operations"]): raise ExecutionError("IN_FLIGHT_AFTER_COMPLETION")
    operation=bundle["operations"][index]
    if intent!={"operation_id":operation["operation_id"],"request_fingerprint":intent.get("request_fingerprint"),"endpoint":operation["endpoint"],"operation_kind":operation["kind"]}: raise ExecutionError("IN_FLIGHT_OPERATION_MISMATCH")
    resolver=BindingResolver(cp["external_bindings"],cp["produced_bindings"])
    payload=_materialize(deepcopy(operation["payload_template"]),resolver)
    request_fp=content_fingerprint({"endpoint":operation["endpoint"],"payload":payload})
    if request_fp!=intent["request_fingerprint"]: raise ExecutionError("IN_FLIGHT_REQUEST_MISMATCH")
    collection=snapshot["collections"][COLLECTIONS[operation["kind"]]]
    identity=_identity_fields(operation,payload)
    if not identity: return {"result":"unobservable","operation":operation}
    candidates=[item for item in collection if all(item.get(key)==value for key,value in identity.items())]
    if not candidates: return {"result":"absent","operation":operation}
    if operation["kind"] in BINARY_KINDS:
        expected=payload["multipart"].get("sha256")
        if not expected or any(item.get("sha256") is None for item in candidates): return {"result":"unobservable","operation":operation}
    managed={key:value for key,value in payload.items() if key!="multipart" and not isinstance(value,(dict,list))}
    if operation["kind"] in BINARY_KINDS: managed["sha256"]=payload["multipart"]["sha256"]
    exact=[item for item in candidates if all(item.get(key)==value for key,value in managed.items())]
    if len(exact)>1: return {"result":"ambiguous","operation":operation}
    if not exact: return {"result":"divergent","operation":operation}
    resource=exact[0]
    if type(resource.get("id")) is not int or resource["id"]<1: return {"result":"unobservable","operation":operation}
    return {"result":"exact_match","operation":operation,"resource_id":resource["id"],"evidence":{"id":resource["id"],"identity":identity,"managed_fields":managed}}

def persist_reconciliation(bundle,checkpoint,reconciliation,persist_checkpoint):
    if reconciliation["result"]!="exact_match": raise ExecutionError("MANUAL_RECONCILIATION_REQUIRED" if reconciliation["result"]=="unobservable" else "IN_FLIGHT_"+reconciliation["result"].upper())
    cp=deepcopy(validate(checkpoint)); operation=reconciliation["operation"]; rid=reconciliation["resource_id"]
    resolver=BindingResolver(cp["external_bindings"],cp["produced_bindings"]); produced=[]
    for binding in operation["produced_bindings"]: resolver.produce(binding,rid); produced.append({**binding,"value":rid})
    receipt={"schema_version":"1.0.0","fixture_only":bundle.get("classification")=="fixture_only","operation_id":operation["operation_id"],"request_fingerprint":cp["in_flight"]["request_fingerprint"],"endpoint":operation["endpoint"],"kind":operation["kind"],"status":200,"response_body_sha256":content_fingerprint(reconciliation["evidence"]),"resource_id":rid,"produced_bindings":produced,"outcome":"reconciled","confirmation_source":"snapshot_reconciliation","previous_checkpoint_fingerprint":cp["checkpoint_fingerprint"],"evidence":reconciliation["evidence"]}
    cp["receipts"].append(receipt); cp["produced_bindings"].extend(produced); cp["completed_operation_ids"].append(operation["operation_id"]); cp["next_operation"]+=1
    cp["counters"]["mutations_confirmed"]+=1; cp["counters"]["operations_completed"]+=1; cp["counters"]["operations_reconciled"]=cp["counters"].get("operations_reconciled",0)+1
    cp["in_flight"]=None; cp["state"]="local_apply_completed_pending_verify" if cp["next_operation"]==len(bundle["operations"]) else "local_apply_in_progress"; cp=seal(cp)
    persist_checkpoint(cp); return cp

def execute(bundle,mutator,persist_checkpoint,checkpoint=None):
    cp=validate(checkpoint) if checkpoint else initial(bundle); persist_checkpoint(cp)
    if cp["in_flight"] is not None:
        cp["state"]="local_apply_reconciliation_required"; persist_checkpoint(seal(cp))
        raise ExecutionError("IN_FLIGHT_RECONCILIATION_REQUIRED")
    if cp["state"] in ("local_apply_completed_pending_verify","local_apply_verified","already_complete"):
        cp["state"]="already_complete" if cp["state"] in ("local_apply_verified","already_complete") else cp["state"]
        return seal(cp)
    resolver=BindingResolver(cp["external_bindings"],cp["produced_bindings"])
    for op in bundle["operations"][len(cp["completed_operation_ids"]):]:
        payload=_materialize(deepcopy(op["payload_template"]),resolver)
        for ref in op["required_bindings"]: resolver.resolve(ref)
        if op["kind"]=="product" and any(payload.get(k)!=v for k,v in SAFE_PRODUCT.items()): raise ExecutionError("UNSAFE_PRODUCT_DEFAULTS")
        request_fp=content_fingerprint({"endpoint":op["endpoint"],"payload":payload})
        cp["in_flight"]={"operation_id":op["operation_id"],"request_fingerprint":request_fp,"endpoint":op["endpoint"],"operation_kind":op["kind"]}; cp["state"]="local_apply_in_progress"; cp["counters"]["intents_registered"]+=1; cp=seal(cp); persist_checkpoint(cp)
        try:
            if op["kind"] in ("image","technical_sheet"):
                part=payload["multipart"]; entry=part.pop("file_entry"); data=bundle["package_entries"][entry]
                expected_size=part.pop("size",len(data)); expected_hash=part.pop("sha256"); mime=part.pop("mime")
                filename=("upload"+({"image":".bin","technical_sheet":".pdf"}[op["kind"]]))
                response=mutator.post_multipart(op["kind"],part,filename,mime,data,expected_hash,expected_size,request_fp)
            else: response=mutator.post_json(op["kind"],payload)
        except Exception:
            cp["counters"]["requests_dispatched"]+=1; cp["state"]="local_apply_reconciliation_required"; cp=seal(cp); persist_checkpoint(cp); raise
        cp["counters"]["requests_dispatched"]+=1
        if response.get("status")!=201 or type(response.get("body",{}).get("id")) is not int or response["body"]["id"]<1: raise ExecutionError("INVALID_MUTATION_RESPONSE")
        rid=response["body"]["id"]; produced=[]
        for binding in op["produced_bindings"]: resolver.produce(binding,rid); produced.append({**binding,"value":rid})
        receipt={"schema_version":"1.0.0","fixture_only":bundle.get("classification")=="fixture_only","operation_id":op["operation_id"],"request_fingerprint":request_fp,"endpoint":op["endpoint"],"kind":op["kind"],"status":201,"response_body_sha256":hashlib.sha256(canonical_bytes(response["body"])).hexdigest(),"resource_id":rid,"produced_bindings":produced,"outcome":"applied","confirmation_source":"response_201","previous_checkpoint_fingerprint":cp["checkpoint_fingerprint"],"evidence":{"id":rid}}
        cp["receipts"].append(receipt); cp["produced_bindings"].extend(produced); cp["completed_operation_ids"].append(op["operation_id"]); cp["in_flight"]=None; cp["next_operation"]+=1; cp["counters"]["mutations_confirmed"]+=1; cp["counters"]["operations_completed"]+=1; cp["state"]="local_apply_completed_pending_verify" if cp["next_operation"]==len(bundle["operations"]) else "local_apply_in_progress"; cp=seal(cp); persist_checkpoint(cp)
    return cp
