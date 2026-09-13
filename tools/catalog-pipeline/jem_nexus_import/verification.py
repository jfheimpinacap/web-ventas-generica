"""Read-only comparison of the plan-managed resources."""
from catalog_pipeline_common.serialization import content_fingerprint

class SnapshotObserver:
    """Expose deterministic exact-match queries over a complete GET snapshot."""
    COLLECTIONS={"category":"categories","brand":"brands","supplier":"suppliers","product":"products","spec":"product_specs","image":"product_images","technical_sheet":"technical_sheets"}
    def __init__(self,snapshot): self.collections=snapshot["collections"]
    def find_exact(self,kind,resource_id,payload):
        candidates=[item for item in self.collections[self.COLLECTIONS[kind]] if item.get("id")==resource_id]
        comparable={key:value for key,value in payload.items() if not isinstance(value,(dict,list))}
        return [item for item in candidates if all(item.get(key)==value for key,value in comparable.items())]
    def bytes_observable(self,kind): return False

def verify_managed(plan,checkpoint,observed):
    failures=[]; manual=[]
    by_binding={(x["namespace"],x["key"]):x["value"] for x in checkpoint["produced_bindings"]}
    for op in plan["operations"]:
        for binding in op["produced_bindings"]:
            resource_id=by_binding.get((binding["namespace"],binding["key"]))
            matches=observed.find_exact(op["kind"],resource_id,op["payload_template"])
            if len(matches)!=1: failures.append({"operation_id":op["operation_id"],"code":"MISSING_DUPLICATE_OR_DIVERGENT"})
            if op["kind"] in ("image","technical_sheet") and not observed.bytes_observable(op["kind"]): manual.append(op["operation_id"])
    result="verification_failed" if failures else ("manual_verification_required" if manual else "verified")
    report={"schema_version":"1.0.0","fixture_only":checkpoint.get("fixture_only",False),"rules_version":"jem-local-verify-v1","result":result,"plan_fingerprint":plan["plan_fingerprint"],"checkpoint_fingerprint":checkpoint["checkpoint_fingerprint"],"failures":failures,"manual_verification_operation_ids":manual,"publication_allowed":False,"publication_performed":False,"managed_operation_count":len(plan["operations"])}
    report["verification_fingerprint"]=content_fingerprint(report); return report
