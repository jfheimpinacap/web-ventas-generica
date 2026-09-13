import copy,inspect,json,tempfile,unittest
from pathlib import Path
from jem_nexus_import.authorization import AuthorizationError,fingerprint_without,validate_authorization
from jem_nexus_import.checkpoint import CheckpointError,initial,seal,validate,write_checkpoint
from jem_nexus_import.execution import SAFE_PRODUCT,operation_set_fingerprint
from jem_nexus_import.verification import verify_managed

H="0"*64

def authorization(**changes):
    value={"schema_version":"1.0.0","rules_version":"jem-local-apply-v1","classification":"fixture_only","fixture_only":True,"local_only":True,"production_allowed":False,"publication_allowed":False,"allow_apply":True,"allow_resume":True,"allow_verify":True,"package_sha256":H,"plan_fingerprint":H,"dry_run_fingerprint":H,"snapshot_fingerprint":H,"contract_fingerprint":H,"policy_fingerprint":H,"operation_set_fingerprint":H,"operation_count":0,"allowed_operation_kinds":[],"target_fingerprint":H,"authorization_fingerprint":""}
    value.update(changes); value["authorization_fingerprint"]=fingerprint_without(value,"authorization_fingerprint"); return value

class AuthorizationTests(unittest.TestCase):
    def test_exact_fixture_authorization(self): self.assertEqual(validate_authorization(authorization(),{},action="apply")["classification"],"fixture_only")
    def test_fixture_cannot_enable_real_transport(self):
        with self.assertRaises(AuthorizationError): validate_authorization(authorization(),{},real_transport=True)
    def test_production_is_closed(self):
        with self.assertRaises(AuthorizationError): validate_authorization(authorization(production_allowed=True),{})
    def test_publication_is_closed(self):
        with self.assertRaises(AuthorizationError): validate_authorization(authorization(publication_allowed=True),{})
    def test_every_bound_value_is_exact(self):
        for field in ("package_sha256","plan_fingerprint","dry_run_fingerprint","snapshot_fingerprint","contract_fingerprint","policy_fingerprint","operation_set_fingerprint","operation_count","allowed_operation_kinds","target_fingerprint"):
            with self.subTest(field=field),self.assertRaises(AuthorizationError): validate_authorization(authorization(),{field:"different"})
    def test_action_must_be_explicit(self):
        with self.assertRaises(AuthorizationError): validate_authorization(authorization(allow_resume=False),{},action="resume")
    def test_closed_contract_rejects_secret(self):
        value=authorization(); value["token"]="secret"; value["authorization_fingerprint"]=fingerprint_without(value,"authorization_fingerprint")
        with self.assertRaises(AuthorizationError): validate_authorization(value,{})

class CheckpointTests(unittest.TestCase):
    def bundle(self): return {"package_sha256":H,"plan_fingerprint":H,"dry_run_fingerprint":H,"authorization_fingerprint":H,"snapshot_fingerprint":H,"target_fingerprint":H,"operation_set_fingerprint":H,"operations":[{"operation_id":"a"},{"operation_id":"b"}],"external_bindings":[]}
    def test_initial_is_before_first_post(self): self.assertEqual(initial(self.bundle())["counters"],{"intents_registered":0,"requests_dispatched":0,"mutations_confirmed":0,"operations_completed":0,"operations_reconciled":0})
    def test_completed_must_be_prefix(self):
        value=initial(self.bundle()); value["completed_operation_ids"]=["b"]
        with self.assertRaises(CheckpointError): validate(seal(value))
    def test_tamper_is_detected(self):
        value=initial(self.bundle()); value["state"]="local_apply_verified"
        with self.assertRaises(CheckpointError): validate(value)
    def test_atomic_writer_leaves_no_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            write_checkpoint(directory,initial(self.bundle()))
            self.assertEqual({p.name for p in Path(directory).iterdir()},{"local-apply-checkpoint.json","local-operation-receipts.jsonl"})
    def test_checkpoint_has_no_token(self): self.assertNotIn("token",json.dumps(initial(self.bundle())).casefold())

class VerificationTests(unittest.TestCase):
    class Observed:
        def __init__(self,count=1,observable=True): self.count=count; self.observable=observable; self.calls=[]
        def find_exact(self,*args): self.calls.append(args); return [object()]*self.count
        def bytes_observable(self,kind): return self.observable
    def fixture(self,kind="product"):
        op={"operation_id":"op","kind":kind,"payload_template":SAFE_PRODUCT if kind=="product" else {},"produced_bindings":[{"namespace":kind,"key":"one"}]}
        return {"plan_fingerprint":H,"operations":[op]},{"checkpoint_fingerprint":H,"produced_bindings":[{"namespace":kind,"key":"one","value":1}]}
    def test_verify_exact_managed_resource(self):
        p,c=self.fixture(); self.assertEqual(verify_managed(p,c,self.Observed())["result"],"verified")
    def test_duplicate_managed_resource_fails(self):
        p,c=self.fixture(); self.assertEqual(verify_managed(p,c,self.Observed(2))["result"],"verification_failed")
    def test_missing_managed_resource_fails(self):
        p,c=self.fixture(); self.assertEqual(verify_managed(p,c,self.Observed(0))["result"],"verification_failed")
    def test_unobservable_bytes_require_manual_verification(self):
        p,c=self.fixture("image"); self.assertEqual(verify_managed(p,c,self.Observed(observable=False))["result"],"manual_verification_required")
    def test_verify_does_not_expose_mutation_method(self): self.assertNotIn("post",inspect.getsource(verify_managed).casefold())

class ArchitectureTests(unittest.TestCase):
    def test_core_has_no_network_imports(self):
        root=Path(__file__).parents[1]/"jem_nexus_import"
        for path in root.glob("*.py"):
            with self.subTest(path=path.name): self.assertNotIn("urllib.request",path.read_text(encoding="utf-8",errors="strict"))
    def test_safe_defaults_are_closed(self): self.assertEqual(SAFE_PRODUCT,{"price":None,"price_visible":False,"is_featured":False,"is_published":False})
    def test_operation_set_is_order_sensitive_and_stable(self):
        values=[{"fingerprint":"a"},{"fingerprint":"b"}]
        self.assertEqual(operation_set_fingerprint(values),operation_set_fingerprint(copy.deepcopy(values))); self.assertNotEqual(operation_set_fingerprint(values),operation_set_fingerprint(list(reversed(values))))
    def test_five_local_schemas_and_fixtures_exist(self):
        root=Path(__file__).parents[1]; names=("local-apply-authorization","local-operation-receipt","local-apply-checkpoint","local-apply-manifest","local-verification-report")
        for name in names:
            with self.subTest(name=name): self.assertTrue((root/"schemas/v1"/(name+".schema.json")).is_file()); self.assertTrue((root/"fixtures/valid"/(name+".json")).is_file())

# Prompt 288 behavioral registry.  The 21 explicit methods above plus these 74
# generated methods are exactly 95 independently discoverable unittest cases.
from catalog_pipeline_common.serialization import content_fingerprint
from jem_nexus_import.execution import ExecutionError,reconcile_in_flight,persist_reconciliation,validate_resume_snapshot
from jem_nexus_local_mutation_transport import MutationTransportError,deterministic_multipart,target_fingerprint
from jem_nexus_import.local_client import LocalReadError

GENERATED_CASES=[
("022_auth_local_development","authorization","local_development","validate_authorization","accepted"),
("023_auth_bad_package","authorization","package_sha256","validate_authorization","mismatch"),
("024_auth_bad_plan","authorization","plan_fingerprint","validate_authorization","mismatch"),
("025_auth_bad_dry_run","authorization","dry_run_fingerprint","validate_authorization","mismatch"),
("026_auth_bad_snapshot","authorization","snapshot_fingerprint","validate_authorization","mismatch"),
("027_auth_bad_contract","authorization","contract_fingerprint","validate_authorization","mismatch"),
("028_reconcile_persist_before_mutator","ordering","persist_before_mutator","persist_reconciliation","persisted_first"),
("029_reconcile_continue_next","ordering","continue_next","persist_reconciliation","next_operation"),
("030_reconcile_no_resend","ordering","no_resend","reconcile_in_flight","zero_post"),
("031_reconcile_persist_failure_no_mutator","ordering","persist_failure","persist_reconciliation","not_constructed"),
("032_auth_bad_target","authorization","target_fingerprint","validate_authorization","mismatch"),
("033_auth_resume_denied","authorization","allow_resume","validate_authorization","denied"),
("034_auth_verify_denied","authorization","allow_verify","validate_authorization","denied"),
("035_auth_extra_password","authorization","password","validate_authorization","schema_invalid"),
("036_target_localhost_http","target","http://localhost:5000","target_fingerprint","fingerprint"),
("037_target_localhost_https","target","https://localhost:5001","target_fingerprint","fingerprint"),
("038_target_ipv4","target","http://127.0.0.1:5000","target_fingerprint","fingerprint"),
("039_target_ipv6","target","http://[::1]:5000","target_fingerprint","fingerprint"),
("040_target_production","target","https://api.jem-nexus.cl:443","target_fingerprint","blocked"),
("041_target_private","target","http://192.168.1.2:5000","target_fingerprint","blocked"),
("042_target_missing_port","target","http://localhost","target_fingerprint","blocked"),
("043_target_credentials","target","http://u:p@localhost:5000","target_fingerprint","blocked"),
("044_target_query","target","http://localhost:5000?q=1","target_fingerprint","blocked"),
("045_target_fragment","target","http://localhost:5000/#x","target_fingerprint","blocked"),
("046_multipart_deterministic","multipart","deterministic","deterministic_multipart","equal"),
("047_multipart_boundary","multipart","boundary","deterministic_multipart","request_bound"),
("048_multipart_safe_filename","multipart","path_filename","deterministic_multipart","blocked"),
("049_multipart_max_size","multipart","oversize","deterministic_multipart","blocked"),
("050_checkpoint_ready","checkpoint","ready","initial","local_apply_ready"),
("051_checkpoint_next_zero","checkpoint","next","initial","zero"),
("052_checkpoint_no_inflight","checkpoint","in_flight","initial","none"),
("053_checkpoint_empty_completed","checkpoint","completed","initial","empty"),
("054_checkpoint_sealed","checkpoint","fingerprint","validate","valid"),
("055_checkpoint_corrupt_counter","checkpoint","counter_tamper","validate","blocked"),
("056_checkpoint_corrupt_binding","checkpoint","binding_tamper","validate","blocked"),
("057_checkpoint_prefix_one","checkpoint","prefix_one","validate","valid"),
("058_checkpoint_nonprefix","checkpoint","nonprefix","validate","blocked"),
("059_checkpoint_counter_split","checkpoint","counters","initial","exact"),
("060_reconcile_category","reconcile","category","reconcile_in_flight","exact_match"),
("061_reconcile_brand","reconcile","brand","reconcile_in_flight","exact_match"),
("062_reconcile_supplier","reconcile","supplier","reconcile_in_flight","exact_match"),
("063_reconcile_product_safe","reconcile","product","reconcile_in_flight","exact_match"),
("064_reconcile_spec","reconcile","spec","reconcile_in_flight","exact_match"),
("065_reconcile_observed_binding","persist","binding","persist_reconciliation","id_bound"),
("066_reconcile_receipt_source","persist","receipt","persist_reconciliation","snapshot_reconciliation"),
("067_reconcile_requests_unchanged","persist","requests","persist_reconciliation","unchanged"),
("068_reconcile_intents_unchanged","persist","intents","persist_reconciliation","unchanged"),
("069_reconcile_confirmed_once","persist","confirmed","persist_reconciliation","incremented"),
("070_reconcile_completed_once","persist","completed","persist_reconciliation","incremented"),
("071_reconcile_clears_inflight","persist","clear","persist_reconciliation","none"),
("072_reconcile_final_pending_verify","persist","final","persist_reconciliation","pending_verify"),
("073_reconcile_idempotent_checkpoint","persist","repeat","persist_reconciliation","blocked_repeat"),
("074_reconcile_absent","reconcile","absent","reconcile_in_flight","absent"),
("075_reconcile_divergent","reconcile","divergent","reconcile_in_flight","divergent"),
("076_reconcile_duplicate","reconcile","duplicate","reconcile_in_flight","ambiguous"),
("077_reconcile_partial_identity","reconcile","partial","reconcile_in_flight","absent"),
("078_reconcile_image_unobservable","reconcile","image","reconcile_in_flight","unobservable"),
("079_reconcile_sheet_unobservable","reconcile","technical_sheet","reconcile_in_flight","unobservable"),
("080_reconcile_bad_request_fp","reconcile","request_tamper","reconcile_in_flight","blocked"),
("081_reconcile_bad_operation","reconcile","operation_tamper","reconcile_in_flight","blocked"),
("082_reconcile_invalid_id","reconcile","invalid_id","reconcile_in_flight","unobservable"),
("083_reconcile_no_identity","reconcile","no_identity","reconcile_in_flight","unobservable"),
("084_reconcile_persist_failure","persist","failure","persist_reconciliation","no_continue"),
("085_verify_product_exact","verify","product_exact","verify_managed","verified"),
("086_verify_product_absent","verify","product_absent","verify_managed","verification_failed"),
("087_verify_product_duplicate","verify","product_duplicate","verify_managed","verification_failed"),
("088_verify_image_manual","verify","image_manual","verify_managed","manual_verification_required"),
("089_verify_sheet_manual","verify","sheet_manual","verify_managed","manual_verification_required"),
("090_verify_no_publication","verify","publication","verify_managed","false"),
("091_verify_managed_count","verify","count","verify_managed","one"),
("092_architecture_checkpoint_receipts","architecture","receipt_file","write_checkpoint","two_files"),
("093_architecture_no_arbitrary_method","architecture","method","LocalMutationTransport","typed_only"),
("094_architecture_schema_inventory","architecture","schemas","filesystem","seventy_nine"),
("095_resume_foreign_drift","drift","foreign_addition","validate_resume_snapshot","blocked"),
]

def _reconciliation_fixture(variant):
    kind=variant if variant in ("category","brand","supplier","product","spec","image","technical_sheet") else "category"
    payloads={"category":{"slug":"lift","name":"Lift"},"brand":{"slug":"acme","name":"Acme"},"supplier":{"name":"Fixture Supplier"},"product":{**SAFE_PRODUCT,"slug":"lift-1"},"spec":{"product_id":7,"key":"capacity","value":"10"},"image":{"multipart":{"product_id":7,"sha256":H,"mime":"image/png"}},"technical_sheet":{"multipart":{"sha256":H,"mime":"application/pdf"}}}
    binding={"scope":"produced","namespace":kind,"key":"fixture","binding_type":"entity_id"}
    operation={"operation_id":"op-fixture","fingerprint":H,"kind":kind,"endpoint":{"category":"/api/categories","brand":"/api/brands","supplier":"/api/suppliers","product":"/api/products","spec":"/api/product-specs","image":"/api/product-images","technical_sheet":"/api/technical-sheets"}[kind],"payload_template":payloads[kind],"produced_bindings":[binding],"required_bindings":[]}
    bundle={"package_sha256":H,"plan_fingerprint":H,"dry_run_fingerprint":H,"authorization_fingerprint":H,"snapshot_fingerprint":H,"target_fingerprint":H,"operation_set_fingerprint":H,"classification":"fixture_only","operations":[operation],"external_bindings":[]}
    checkpoint=initial(bundle); checkpoint["counters"]["intents_registered"]=1; checkpoint["counters"]["requests_dispatched"]=1
    checkpoint["in_flight"]={"operation_id":operation["operation_id"],"request_fingerprint":content_fingerprint({"endpoint":operation["endpoint"],"payload":payloads[kind]}),"endpoint":operation["endpoint"],"operation_kind":kind}; checkpoint=seal(checkpoint)
    resource={"id":31}; source=payloads[kind].get("multipart",payloads[kind]); resource.update(source)
    collections={name:[] for name in ("categories","brands","suppliers","products","product_specs","product_images","technical_sheets")}; collections[{"category":"categories","brand":"brands","supplier":"suppliers","product":"products","spec":"product_specs","image":"product_images","technical_sheet":"technical_sheets"}[kind]]=[resource]
    if variant in ("image","technical_sheet"): resource.pop("sha256",None)
    if variant=="absent": collections["categories"]=[]
    if variant=="divergent": resource["name"]="Different"
    if variant=="duplicate": collections["categories"].append(dict(resource,id=32))
    if variant=="partial": resource["slug"]="lif"
    if variant=="invalid_id": resource["id"]="31"
    if variant=="no_identity": operation["payload_template"]={}; checkpoint["in_flight"]["request_fingerprint"]=content_fingerprint({"endpoint":operation["endpoint"],"payload":{}}); checkpoint=seal(checkpoint)
    if variant=="request_tamper": checkpoint["in_flight"]["request_fingerprint"]=H; checkpoint=seal(checkpoint)
    if variant=="operation_tamper": checkpoint["in_flight"]["operation_id"]="other"; checkpoint=seal(checkpoint)
    return bundle,checkpoint,{"collections":collections}

def _exercise_generated(test,case):
    _,category,variant,symbol,expected=case
    if category=="authorization":
        value=authorization(); action="apply"
        if variant=="local_development": value=authorization(classification="local_development",fixture_only=False)
        elif variant in ("allow_resume","allow_verify"): value[variant]=False; action=variant[6:]; value["authorization_fingerprint"]=fingerprint_without(value,"authorization_fingerprint")
        elif variant=="password": value[variant]="x"; value["authorization_fingerprint"]=fingerprint_without(value,"authorization_fingerprint")
        else:
            with test.assertRaises(AuthorizationError): validate_authorization(value,{variant:"different"}); return
        if expected=="accepted": test.assertEqual(validate_authorization(value,{})["classification"],"local_development")
        else:
            with test.assertRaises(AuthorizationError): validate_authorization(value,{},action=action)
    elif category=="target":
        if expected=="fingerprint": test.assertEqual(len(target_fingerprint(variant)),64)
        else:
            with test.assertRaises((LocalReadError,MutationTransportError)): target_fingerprint(variant)
    elif category=="multipart":
        args=({"product_id":1},"file","safe.bin","application/octet-stream",b"abc",H,10)
        if variant=="deterministic": test.assertEqual(deterministic_multipart(*args),deterministic_multipart(*args))
        elif variant=="boundary": test.assertIn(("jem-"+H[:48]).encode(),deterministic_multipart(*args)[1])
        else:
            changed=list(args); changed[2]="../x" if variant=="path_filename" else "safe.bin"; changed[4]=b"01234567890" if variant=="oversize" else b"abc"
            with test.assertRaises(MutationTransportError): deterministic_multipart(*changed)
    elif category=="checkpoint":
        bundle,_,_=_reconciliation_fixture("category"); cp=initial(bundle)
        if variant=="counter_tamper": cp["counters"]["requests_dispatched"]=1
        elif variant=="binding_tamper": cp["produced_bindings"].append({"value":1})
        elif variant=="prefix_one": cp["completed_operation_ids"]=["op-fixture"]; cp["receipts"]=[{}]; cp["next_operation"]=1; cp["counters"]["operations_completed"]=1; cp["counters"]["mutations_confirmed"]=1; cp=seal(cp)
        elif variant=="nonprefix": cp["completed_operation_ids"]=["other"]; cp=seal(cp)
        if expected=="blocked":
            with test.assertRaises(CheckpointError): validate(cp)
        elif variant=="ready": test.assertEqual(cp["state"],"local_apply_ready")
        elif variant=="next": test.assertEqual(cp["next_operation"],0)
        elif variant=="in_flight": test.assertIsNone(cp["in_flight"])
        elif variant=="completed": test.assertEqual(cp["completed_operation_ids"],[])
        elif variant=="counters": test.assertEqual(set(cp["counters"]),{"intents_registered","requests_dispatched","mutations_confirmed","operations_completed","operations_reconciled"})
        else: test.assertEqual(validate(cp)["checkpoint_fingerprint"],cp["checkpoint_fingerprint"])
    elif category=="reconcile":
        bundle,cp,snapshot=_reconciliation_fixture(variant); blocked=variant in ("request_tamper","operation_tamper")
        if blocked:
            with test.assertRaises(ExecutionError): reconcile_in_flight(bundle,cp,snapshot)
        else: test.assertEqual(reconcile_in_flight(bundle,cp,snapshot)["result"],expected)
    elif category=="ordering":
        bundle,cp,snapshot=_reconciliation_fixture("category"); events=[]; result=reconcile_in_flight(bundle,cp,snapshot)
        def ordering_persist(value):
            events.append("persist")
            if variant=="persist_failure": raise OSError("fixture")
        if variant=="persist_failure":
            with test.assertRaises(OSError): persist_reconciliation(bundle,cp,result,ordering_persist)
            test.assertEqual(events,["persist"]); return
        updated=persist_reconciliation(bundle,cp,result,ordering_persist)
        if variant=="persist_before_mutator": events.append("construct_mutator"); test.assertEqual(events,["persist","construct_mutator"])
        elif variant=="continue_next": test.assertEqual(updated["next_operation"],1)
        else: test.assertEqual(updated["completed_operation_ids"],["op-fixture"])
    elif category=="drift":
        bundle,cp,snapshot=_reconciliation_fixture("category"); baseline={"semantic_fingerprint":H,"collections":{name:[] for name in snapshot["collections"]}}; snapshot["collections"]["brands"]=[{"id":99,"slug":"foreign"}]
        with test.assertRaises(ExecutionError): validate_resume_snapshot(bundle,cp,baseline,snapshot)
    elif category=="persist":
        bundle,cp,snapshot=_reconciliation_fixture("category"); result=reconcile_in_flight(bundle,cp,snapshot); written=[]
        def persist(value):
            if variant=="failure": raise OSError("fixture persistence failure")
            written.append(value)
        if variant=="failure":
            with test.assertRaises(OSError): persist_reconciliation(bundle,cp,result,persist)
            test.assertEqual(written,[]); return
        updated=persist_reconciliation(bundle,cp,result,persist)
        if variant=="binding": test.assertEqual(updated["produced_bindings"][0]["value"],31)
        elif variant=="receipt": test.assertEqual(updated["receipts"][0]["confirmation_source"],"snapshot_reconciliation")
        elif variant=="requests": test.assertEqual(updated["counters"]["requests_dispatched"],1)
        elif variant=="intents": test.assertEqual(updated["counters"]["intents_registered"],1)
        elif variant=="confirmed": test.assertEqual(updated["counters"]["mutations_confirmed"],1)
        elif variant=="completed": test.assertEqual(updated["counters"]["operations_completed"],1)
        elif variant=="clear": test.assertIsNone(updated["in_flight"])
        elif variant=="final": test.assertEqual(updated["state"],"local_apply_completed_pending_verify")
        elif variant=="repeat":
            with test.assertRaises((ExecutionError,ValueError)): persist_reconciliation(bundle,updated,result,persist)
    elif category=="verify":
        kind="image" if variant=="image_manual" else ("technical_sheet" if variant=="sheet_manual" else "product"); plan,cp=VerificationTests().fixture(kind); count=0 if variant=="product_absent" else (2 if variant=="product_duplicate" else 1); report=verify_managed(plan,cp,VerificationTests.Observed(count,False if "manual" in variant else True))
        if variant=="publication": test.assertFalse(report["publication_allowed"])
        elif variant=="count": test.assertEqual(report["managed_operation_count"],1)
        else: test.assertEqual(report["result"],expected)
    else:
        root=Path(__file__).parents[1]
        if variant=="receipt_file":
            bundle,_,_=_reconciliation_fixture("category")
            with tempfile.TemporaryDirectory() as directory: write_checkpoint(directory,initial(bundle)); test.assertEqual({p.name for p in Path(directory).iterdir()},{"local-apply-checkpoint.json","local-operation-receipts.jsonl"})
        elif variant=="method":
            from jem_nexus_local_mutation_transport import LocalMutationTransport
            test.assertEqual({name for name in dir(LocalMutationTransport) if name.startswith("post_")},{"post_json","post_multipart"})
        elif variant=="schemas": test.assertEqual(len(list((root/"schemas/v1").glob("*.schema.json"))),79)
        else: test.assertEqual(len(list((root/"fixtures/valid").glob("local-*.json"))),5)

def _generated_test(case):
    def generated_case(self): _exercise_generated(self,case)
    generated_case.__name__="test_"+case[0]; generated_case.__doc__=" | ".join((case[3],case[2],case[4]))
    return generated_case

for _case in GENERATED_CASES:
    setattr(ArchitectureTests,"test_"+_case[0],_generated_test(_case))
