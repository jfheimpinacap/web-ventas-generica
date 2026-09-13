"""Read-only comparison of the plan-managed resources."""
from catalog_pipeline_common.serialization import content_fingerprint

class SnapshotObserver:
    """Expose deterministic exact-match queries over a complete GET snapshot."""
    COLLECTIONS={"category":"categories","brand":"brands","supplier":"suppliers","product":"products","spec":"product_specs","image":"product_images","technical_sheet":"technical_sheets"}
    def __init__(self,snapshot): self.collections=snapshot["collections"]
    def find_exact(self,kind,resource_id,payload):
        candidates=[item for item in self.collections[self.COLLECTIONS[kind]] if item.get("id")==resource_id]
        comparable={key:value for key,value in payload.items() if not isinstance(value,(dict,list))}
        # ProductSpecWriteDto accepts ``key`` while ProductSpecReadDto exposes it
        # as ``name``.  Preserve the inspected API asymmetry without weakening
        # any other managed-field comparison.
        aliases={"spec":{"key":"name"}}
        return [item for item in candidates if all(item.get(key,item.get(aliases.get(kind,{}).get(key)))==value for key,value in comparable.items())]
    def binary_sha256(self,kind,resource_id):
        """Real GET DTOs expose neither bytes nor a digest for binary resources."""
        return None

def verify_managed(plan,checkpoint,observed):
    failures=[]; manual=[]
    resource_ids={receipt["operation_id"]:receipt["resource_id"] for receipt in checkpoint.get("receipts",[])}
    for op in plan["operations"]:
        resource_id=resource_ids.get(op["operation_id"])
        matches=observed.find_exact(op["kind"],resource_id,op["payload_template"])
        if len(matches)!=1: failures.append({"operation_id":op["operation_id"],"code":"MISSING_DUPLICATE_OR_DIVERGENT"})
        if op["kind"] in ("image","technical_sheet"):
            expected=op["payload_template"].get("multipart",{}).get("sha256")
            actual=observed.binary_sha256(op["kind"],resource_id)
            if actual is None: manual.append(op["operation_id"])
            elif actual!=expected: failures.append({"operation_id":op["operation_id"],"code":"BINARY_CONTENT_DIVERGENT"})
    result="verification_failed" if failures else ("manual_verification_required" if manual else "verified")
    report={"schema_version":"1.0.0","fixture_only":checkpoint.get("fixture_only",False),"rules_version":"jem-local-verify-v1","result":result,"plan_fingerprint":plan["plan_fingerprint"],"checkpoint_fingerprint":checkpoint["checkpoint_fingerprint"],"failures":failures,"manual_verification_operation_ids":manual,"publication_allowed":False,"publication_performed":False,"managed_operation_count":len(plan["operations"])}
    report["verification_fingerprint"]=content_fingerprint(report); return report
