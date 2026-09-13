"""Pure validation for externally-created, local-only apply authorizations."""
from catalog_pipeline_common.serialization import content_fingerprint

AUTHORIZATION_FIELDS=frozenset({"schema_version","rules_version","classification","fixture_only","local_only","production_allowed","publication_allowed","allow_apply","allow_resume","allow_verify","package_sha256","plan_fingerprint","dry_run_fingerprint","snapshot_fingerprint","contract_fingerprint","policy_fingerprint","operation_set_fingerprint","operation_count","allowed_operation_kinds","target_fingerprint","authorization_fingerprint"})

class AuthorizationError(ValueError):
    def __init__(self,code): self.code=code; super().__init__(code)

def fingerprint_without(document,field):
    return content_fingerprint({key:value for key,value in document.items() if key!=field})

def validate_authorization(value,expected,action="apply",real_transport=False):
    if not isinstance(value,dict) or set(value)!=AUTHORIZATION_FIELDS: raise AuthorizationError("AUTHORIZATION_SCHEMA_INVALID")
    if value["schema_version"]!="1.0.0" or value["rules_version"]!="jem-local-apply-v1": raise AuthorizationError("AUTHORIZATION_VERSION_INVALID")
    if value["local_only"] is not True or value["production_allowed"] is not False or value["publication_allowed"] is not False: raise AuthorizationError("UNSAFE_AUTHORIZATION")
    classification=value["classification"]
    if classification not in ("fixture_only","local_development") or value["fixture_only"] != (classification=="fixture_only"): raise AuthorizationError("AUTHORIZATION_CLASSIFICATION_INVALID")
    if real_transport and classification!="local_development": raise AuthorizationError("FIXTURE_AUTHORIZATION_FORBIDDEN")
    if value.get("allow_"+action) is not True: raise AuthorizationError("ACTION_NOT_AUTHORIZED")
    for key,wanted in expected.items():
        if value.get(key)!=wanted: raise AuthorizationError("AUTHORIZATION_MISMATCH:"+key)
    if value["authorization_fingerprint"]!=fingerprint_without(value,"authorization_fingerprint"): raise AuthorizationError("AUTHORIZATION_FINGERPRINT_INVALID")
    return dict(value)
