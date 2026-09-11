"""Offline behavioral tests for Prompt 284. No test in this module opens a socket."""
import copy,errno,hashlib,inspect,json,os,pathlib,sys,tempfile,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from jem_nexus_import.bindings import BindingResolver,MissingBindingError
from jem_nexus_import.local_client import LocalJemJsonReader,LocalReadError,validate_base_url
from jem_nexus_import.output import _fsync_directory_if_supported,write_output_set
from jem_nexus_import.planning import operation,simulate,topological
from jem_nexus_import.projection import build_safe_product_payload,project_candidate
from jem_nexus_import.snapshot import COLLECTIONS,semantic_fingerprint,validate_snapshot,SnapshotError
from catalog_acquisition.packaging import build_package,fingerprint,PackageError
from catalog_acquisition.serialization import canonical_bytes
from catalog_acquisition.schema_validation import validate,SchemaValidationError
from catalog_import import create_plan,plan_outputs,capture_snapshot
from jem_nexus_import.package_input import read_verified_package,ImportInputError
from jem_nexus_import.reconciliation import build_operations,reconcile_category,reconcile_brand,reconcile_supplier,reconcile_product,reconcile_assets
from jem_nexus_local_transport import _NoRedirect,get_json_bytes

def ref(scope,namespace,key): return {"scope":scope,"namespace":namespace,"key":key,"binding_type":"entity_id"}
def binding(namespace,key,value=1): return {**ref("external",namespace,key),"value":value}
def snapshot():
 value={"schema_version":"1.0.0","complete":True,"classification":"fixture_only","contract_fingerprint":"c"*64,
  "collections":{name:[] for name in COLLECTIONS},"endpoints":[{"collection":name,"path":"/api/"+name,"status":200,"mime":"application/json","response_sha256":"a"*64,"pages_received":1,"pages_expected":1,"complete":True} for name in COLLECTIONS]}
 value["collections"]["categories"]=[{"id":1,"name":"Maquinarias","slug":"maquinarias","parent_id":None}]
 value["semantic_fingerprint"]=semantic_fingerprint(value); return value
def plan(ops,external=(),reviews=()): return {"operations":ops,"external_bindings":list(external),"reviews":list(reviews),"plan_fingerprint":"a"*64}
def canonical_package(directory,blocked=0,excluded=0):
 root=pathlib.Path(directory)/"source"; root.mkdir(); image1=b"primary"; image2=b"secondary"; sheet=b"%PDF-sheet"; extra=b"%PDF-extra"
 def asset(path,data,role,mime,ordinal=0): return {"entry_path":path,"sha256":hashlib.sha256(data).hexdigest(),"size":len(data),"mime":mime,"role":role,"ordinal":ordinal,"source_filename":"ignored.bin"}
 product={"schema_version":"1.0.0","document_kind":"normalized_for_audit_not_api_payload","canonical_identity":"synthetic-model-1","brand_code":"SYN","canonical_model":"MODEL-1","category_mapping":{"name":"Elevadores","slug":"elevadores","product_type":"machinery"},"structured_fields":{"condition":"new"},"product_specs":[{"key":"capacity","value":"200","unit":"kg"}],"media":[asset("products/p/primary.png",image1,"primary","image/png"),asset("products/p/secondary.png",image2,"secondary","image/png",1)],"technical_sheet":asset("products/p/sheet.pdf",sheet,"technical_sheet","application/pdf"),"additional_documents":[asset("products/p/extra.pdf",extra,"additional_document","application/pdf")],"commercial":{"price":None,"price_visible":False,"is_featured":False,"is_published":False}}
 files={"producto.json":canonical_bytes(product),"primary.png":image1,"secondary.png":image2,"sheet.pdf":sheet,"extra.pdf":extra}; entries=[]
 roles={"producto.json":"normalized_product","primary.png":"primary","secondary.png":"secondary","sheet.pdf":"technical_sheet","extra.pdf":"additional_document"}
 paths={"producto.json":"products/p/producto.json","primary.png":"products/p/primary.png","secondary.png":"products/p/secondary.png","sheet.pdf":"products/p/sheet.pdf","extra.pdf":"products/p/extra.pdf"}
 for name,data in files.items():
  (root/name).write_bytes(data); entries.append({"path":paths[name],"role":roles[name],"source_reference":name,"source_sha256":hashlib.sha256(data).hexdigest(),"source_size":len(data),"destination_sha256":hashlib.sha256(data).hexdigest(),"destination_size":len(data),"mime":"application/json" if name.endswith("json") else ("image/png" if name.endswith("png") else "application/pdf"),"product_identity":"synthetic-model-1"})
 policy={"policy_version":"1","fingerprint":"1"*64}; descriptors=[{"path":x["path"],"role":x["role"],"sha256":x["destination_sha256"],"size":x["destination_size"],"mime":x["mime"],"product_identity":x["product_identity"]} for x in entries]
 package_plan={"schema_version":"1.0.0","package_schema_version":"1.0.0","producer":"catalog-package","package_policy":policy,"audit_manifest_fingerprint":"a"*64,"included_products":[] if blocked else ["synthetic-model-1"],"excluded_product_count":excluded,"blocked_product_count":blocked,"decision_fingerprint":"d"*64,"entries":entries,"content_fingerprint":fingerprint({"entries":descriptors,"policy_fingerprint":policy["fingerprint"],"audit_fingerprint":"a"*64,"decision_fingerprint":"d"*64}),"entry_count":len(entries)+1,"total_uncompressed_size":sum(len(x) for x in files.values()),"blocking":bool(blocked),"fixture_only":True,"source_root":".","upstream_fingerprints":{}}
 package_plan["plan_fingerprint"]=fingerprint(package_plan); package=pathlib.Path(directory)/"catalog.zip"; receipt=pathlib.Path(directory)/"receipt.json"; build_package(package_plan,package_plan["plan_fingerprint"],package,root,receipt); return package,receipt,product
def complete_snapshot():
 value=snapshot(); value["collections"]["categories"][0].update(product_type="machinery"); value["semantic_fingerprint"]=semantic_fingerprint(value); return value

class LocalClientTests(unittest.TestCase):
 def test_exact_loopback_hosts_are_allowed(self):
  for url in ("http://localhost:5000","https://127.0.0.1:1","http://[::1]:8080"): self.assertEqual(url,validate_base_url(url))
 def test_unsafe_targets_are_rejected(self):
  for url in ("https://api.jem-nexus.cl:443","http://10.0.0.2:80","//localhost:80","http://u:p@localhost:80","http://localhost:80?x=1","http://localhost:80/#x","http://localhost"):
   with self.subTest(url=url),self.assertRaises(LocalReadError): validate_base_url(url)
 def test_fake_transport_observes_get_contract_and_json(self):
  calls=[]
  reader=LocalJemJsonReader("http://localhost:5000",transport=lambda url,headers,timeout,limit:(calls.append(url) or (200,"application/json",b'{"items":[]}')),requires_auth=False)
  self.assertEqual({"items":[]},reader.read_collection("products")); self.assertEqual(1,len(calls)); self.assertEqual("http://localhost:5000/api/products",calls[0])
 def test_non_json_and_oversize_fail_closed(self):
  for mime,body,code in (("text/html",b"{}","READ_MIME"),("application/json",b"{}x","READ_TOO_LARGE")):
   reader=LocalJemJsonReader("http://localhost:1",transport=lambda *unused:(200,mime,body),requires_auth=False,max_bytes=2)
   with self.assertRaises(LocalReadError) as caught: reader.read_collection("brands")
   self.assertEqual(code,caught.exception.code)
  reader=LocalJemJsonReader("http://localhost:1",transport=lambda *unused:(200,"application/json",b'\xff'),requires_auth=False,max_bytes=20)
  with self.assertRaises(LocalReadError) as caught: reader.read_collection("brands")
  self.assertEqual("READ_INVALID_JSON",caught.exception.code)
 def test_redirect_status_is_rejected_without_following(self):
  calls=[]; reader=LocalJemJsonReader("http://localhost:1",transport=lambda *args:(calls.append(args) or (302,"application/json",b"{}")),requires_auth=False)
  with self.assertRaises(LocalReadError) as caught: reader.read_collection("categories")
  self.assertEqual("READ_STATUS",caught.exception.code); self.assertEqual(1,len(calls))
 def test_token_absence_is_structured_and_never_disclosed(self):
  with self.assertRaises(LocalReadError) as caught: LocalJemJsonReader("http://localhost:1",transport=lambda *unused:None)
  self.assertEqual("LOCAL_TOKEN_MISSING",caught.exception.code); self.assertNotIn("Bearer",str(caught.exception))
 def test_reader_requires_an_explicit_get_transport(self):
  with self.assertRaises(LocalReadError) as caught: LocalJemJsonReader("http://localhost:1",requires_auth=False)
  self.assertEqual("LOCAL_TRANSPORT_MISSING",caught.exception.code)

class LocalTransportTests(unittest.TestCase):
 class Response:
  status=200
  class Headers:
   def get_content_type(self): return "application/json"
  headers=Headers()
  def __init__(self,body): self.body=body; self.read_limit=None; self.closed=False
  def __enter__(self): return self
  def __exit__(self,*unused): self.closed=True
  def read(self,limit): self.read_limit=limit; return self.body[:limit]
 def test_interface_is_get_specific_and_request_is_always_get(self):
  self.assertEqual(("url","headers","timeout","max_bytes"),tuple(inspect.signature(get_json_bytes).parameters))
  response=self.Response(b"{}")
  opener=mock.Mock(); opener.open.return_value=response
  with mock.patch("jem_nexus_local_transport.build_opener",return_value=opener),mock.patch("jem_nexus_local_transport.Request") as request:
   self.assertEqual((200,"application/json",b"{}"),get_json_bytes("http://localhost:1/api/products",{"Authorization":"Bearer secret"},3,8))
  self.assertEqual("GET",request.call_args.kwargs["method"]); self.assertNotIn("method",inspect.signature(get_json_bytes).parameters)
  self.assertEqual(9,response.read_limit); self.assertTrue(response.closed)
 def test_redirects_and_proxies_are_disabled(self):
  self.assertIsNone(_NoRedirect().redirect_request(None,None,None,None,None,None))
  response=self.Response(b"[]"); opener=mock.Mock(); opener.open.return_value=response
  with mock.patch("jem_nexus_local_transport.build_opener",return_value=opener) as builder: get_json_bytes("http://127.0.0.1:2/api/brands",{},1,2)
  handlers=builder.call_args.args; self.assertEqual({},handlers[0].proxies); self.assertIsInstance(handlers[1],_NoRedirect)
 def test_direct_calls_reject_external_or_unapproved_targets_before_open(self):
  targets=("https://api.jem-nexus.cl:443/api/products","http://localhost/api/products","//localhost:1/api/products","http://u:p@localhost:1/api/products","http://localhost:1/api/products?x=1","http://localhost:1/other")
  with mock.patch("jem_nexus_local_transport.build_opener") as builder:
   for target in targets:
    with self.subTest(target=target),self.assertRaises(LocalReadError): get_json_bytes(target,{},1,1)
   builder.assert_not_called()
 def test_direct_calls_allow_each_exact_loopback_form_without_network(self):
  for target in ("http://localhost:1/api/categories","http://127.0.0.1:2/api/products","http://[::1]:3/api/technical-sheets/"):
   response=self.Response(b"[]"); opener=mock.Mock(); opener.open.return_value=response
   with self.subTest(target=target),mock.patch("jem_nexus_local_transport.build_opener",return_value=opener):
    self.assertEqual(b"[]",get_json_bytes(target,{},1,2)[2])

class SnapshotTests(unittest.TestCase):
 def test_complete_snapshot_validates(self): self.assertIsNotNone(validate_snapshot(snapshot(),"c"*64))
 def test_order_and_capture_time_do_not_change_semantics(self):
  first=snapshot(); second=copy.deepcopy(first); second["captured_at"]="2099-01-01T00:00:00Z"; second["endpoints"].reverse()
  self.assertEqual(semantic_fingerprint(first),semantic_fingerprint(second))
 def test_missing_endpoint_and_truncated_page_are_rejected(self):
  for mutate in (lambda x:x["endpoints"].pop(),lambda x:x["endpoints"][0].update(pages_expected=2)):
   value=snapshot(); mutate(value); value["semantic_fingerprint"]=semantic_fingerprint(value)
   with self.assertRaises(SnapshotError): validate_snapshot(value)
 def test_duplicate_and_casefold_collision_are_rejected(self):
  for extra in ({"id":1,"name":"Other","slug":"other","parent_id":None},{"id":2,"name":"MAQUINARIAS","slug":"MAQUINARIAS","parent_id":None}):
   value=snapshot(); value["collections"]["categories"].append(extra); value["semantic_fingerprint"]=semantic_fingerprint(value)
   with self.assertRaises(SnapshotError): validate_snapshot(value)
 def test_orphan_relations_are_rejected(self):
  value=snapshot(); value["collections"]["products"]=[{"id":2,"name":"P","slug":"p","category_id":999}]; value["semantic_fingerprint"]=semantic_fingerprint(value)
  with self.assertRaises(SnapshotError) as caught: validate_snapshot(value)
  self.assertEqual("ORPHAN_RELATION",caught.exception.code)

class ProjectionTests(unittest.TestCase):
 def test_safe_commercial_defaults_cannot_be_overridden(self):
  value=project_candidate({"name":"Synthetic","price":99,"is_published":True})
  self.assertEqual(99,value["structured_fields"]["price"]); self.assertTrue(value["structured_fields"]["is_published"]); self.assertFalse(value["ready"])
 def test_projection_does_not_invent_absent_fields(self):
  self.assertEqual({"name":"x"},project_candidate({"name":"x"})["structured_fields"])
 def test_safe_payload_defaults_are_separate_and_input_is_immutable(self):
  projected=project_candidate({"name":"x"}); before=copy.deepcopy(projected); safe=build_safe_product_payload(projected)
  self.assertEqual(before,projected); self.assertEqual({"name":"x","price":None,"price_visible":False,"is_featured":False,"is_published":False},safe["payload"])
  self.assertEqual(4,len(safe["safety_evidence"])); self.assertTrue(all(x["rule_version"]=="jem-import-safety-v1" for x in safe["safety_evidence"]))
 def test_explicit_safe_values_are_accepted_and_unsafe_values_rejected(self):
  safe={"price":None,"price_visible":False,"is_featured":False,"is_published":False}
  self.assertEqual(safe,build_safe_product_payload(project_candidate(safe))["payload"])
  for field,value in (("price",1),("price_visible",True),("is_featured",True),("is_published",True)):
   with self.subTest(field=field),self.assertRaises(ValueError): build_safe_product_payload(project_candidate({field:value}))
 def test_lift_height_remains_a_spec(self):
  value=project_candidate({"maximum_lift_height_mm":8000}); self.assertEqual("maximum_lift_height_mm",value["product_specs"][0]["key"]); self.assertNotIn("working_height_m",value["structured_fields"])
 def test_unknown_enum_is_a_blocker(self): self.assertEqual("UNKNOWN_ENUM",project_candidate({"condition":"almost_new"})["issues"][0]["code"])
 def test_field_evidence_is_traceable(self):
  evidence=project_candidate({"model":"S1"})["field_evidence"][0]; self.assertEqual("/model",evidence["source_pointer"]); self.assertEqual("audited_package",evidence["provenance"])

class GraphTests(unittest.TestCase):
 def test_root_maquinarias_resolves_child(self):
  required=ref("external","root","maquinarias"); produced=ref("produced","category","scissor-lifts")
  child=operation("category","create","scissor-lifts","/api/categories",{"parent_id":required},[required],[produced])
  result=simulate(plan([child],[binding("root","maquinarias")]))
  self.assertEqual("dry_run_ready",result["state"]); self.assertEqual(0,result["mutations_attempted"])
 def test_missing_root_is_typed_not_key_error(self):
  required=ref("external","root","maquinarias"); child=operation("category","create","child","/api/categories",{},[required])
  result=simulate(plan([child])); self.assertEqual("preflight_failed",result["state"]); self.assertEqual("MISSING_BINDING",result["errors"][0]["code"]); self.assertNotEqual("partial",result["state"])
 def test_duplicate_external_and_produced_binding_is_rejected(self):
  with self.assertRaises(ValueError): BindingResolver([binding("brand","jem")],[binding("brand","jem")])
 def test_type_mismatch_is_missing_binding(self):
  resolver=BindingResolver([binding("brand","jem")])
  with self.assertRaises(MissingBindingError): resolver.resolve({**ref("external","brand","jem"),"binding_type":"entity_slug"})
 def test_cycle_and_missing_dependency_are_rejected(self):
  a=operation("brand","create","a","/api/brands",{}); b=operation("product","create","b","/api/products",{},depends_on=[a["operation_id"]]); a["dependencies"]=[b["operation_id"]]
  with self.assertRaises(ValueError): topological([a,b])
 def test_stable_topology_places_dependencies_first(self):
  category=operation("category","create","c","/api/categories",{}); product=operation("product","create","p","/api/products",{},depends_on=[category["operation_id"]]); image=operation("image","create","i","/api/product-images",{},depends_on=[product["operation_id"]])
  self.assertEqual([category["operation_id"],product["operation_id"],image["operation_id"]],[x["operation_id"] for x in topological([image,product,category])])
 def test_operation_ids_are_deterministic(self): self.assertEqual(operation("brand","create","x","/api/brands",{})["operation_id"],operation("brand","create","x","/api/brands",{})["operation_id"])
 def test_symbolic_results_never_look_like_database_ids(self):
  produced=ref("produced","brand","jem"); result=simulate(plan([operation("brand","create","jem","/api/brands",{},produces=[produced])]))
  self.assertTrue(result["simulated_bindings"][0]["value"].startswith("<symbolic:")); self.assertEqual(0,result["mutating_network_requests"])
 def test_reviews_prevent_ready_state(self):
  result=simulate(plan([],reviews=[{"code":"UNREPRESENTABLE"}])); self.assertEqual("manual_review_required",result["state"]); self.assertFalse(result["publication_authorized"])

class OutputTests(unittest.TestCase):
 def test_output_is_atomic_idempotent_and_conflicts_fail(self):
  with tempfile.TemporaryDirectory() as directory:
   write_output_set(directory,{"import-plan.json":{"x":1}}); first=(pathlib.Path(directory)/"import-plan.json").read_bytes(); write_output_set(directory,{"import-plan.json":{"x":1}})
   self.assertEqual(first,(pathlib.Path(directory)/"import-plan.json").read_bytes())
   with self.assertRaises(FileExistsError): write_output_set(directory,{"import-plan.json":{"x":2}})
   self.assertFalse(any(pathlib.Path(directory).glob("*.tmp")))
 def test_directory_sync_supported_closes_handle(self):
  with mock.patch("jem_nexus_import.output.os.open",return_value=71),mock.patch("jem_nexus_import.output.os.fsync") as sync,mock.patch("jem_nexus_import.output.os.close") as close:
   _fsync_directory_if_supported("destination"); sync.assert_called_once_with(71); close.assert_called_once_with(71)
 def test_directory_sync_unsupported_is_ignored_but_unexpected_is_propagated(self):
  with mock.patch("jem_nexus_import.output.os.open",side_effect=PermissionError(errno.EACCES,"denied")): _fsync_directory_if_supported("destination")
  with mock.patch("jem_nexus_import.output.os.open",return_value=72),mock.patch("jem_nexus_import.output.os.fsync",side_effect=OSError(errno.EIO,"broken")),mock.patch("jem_nexus_import.output.os.close") as close:
   with self.assertRaises(OSError): _fsync_directory_if_supported("destination")
   close.assert_called_once_with(72)
 def test_intermediate_publish_failure_rolls_back_only_new_files(self):
  real_replace=os.replace
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); existing=root/"existing.json"; existing.write_bytes(b"same"); foreign=root/"foreign.tmp"; foreign.write_bytes(b"foreign"); calls=[]
   def fail_second(source,target):
    calls.append(target)
    if len(calls)==2: raise OSError(errno.EIO,"injected")
    return real_replace(source,target)
   with mock.patch("jem_nexus_import.output.os.replace",side_effect=fail_second):
    with self.assertRaises(OSError): write_output_set(root,{"existing.json":b"same","a.json":b"a","import-plan.json":b"plan"})
   self.assertEqual(b"same",existing.read_bytes()); self.assertEqual(b"foreign",foreign.read_bytes()); self.assertFalse((root/"a.json").exists()); self.assertFalse((root/"import-plan.json").exists()); self.assertFalse(any(root.glob(".*.writing-*.tmp")))
 def test_file_fsync_remains_mandatory(self):
  with tempfile.TemporaryDirectory() as directory,mock.patch("jem_nexus_import.output.os.fsync",side_effect=OSError(errno.EIO,"file sync failed")):
   with self.assertRaises(OSError): write_output_set(directory,{"import-plan.json":b"value"})
   self.assertFalse((pathlib.Path(directory)/"import-plan.json").exists())
 def test_cli_surface_contains_only_read_only_commands(self):
  source=(ROOT/"catalog_import.py").read_text(encoding="utf-8")
  for command in ('"snapshot-local"','"plan"','"dry-run"'): self.assertIn(command,source)
  for unsafe in ('add_parser("apply")','--token','--jwt','--force','--overwrite'): self.assertNotIn(unsafe,source)

class FunctionalFlowTests(unittest.TestCase):
 def test_case_a_real_package_to_complete_graph_and_outputs(self):
  with tempfile.TemporaryDirectory() as directory:
   package,receipt,product=canonical_package(directory); snap=complete_snapshot(); policy={"schema_version":"1.0.0","rules_version":"policy-v1","contract_fingerprint":"c"*64,"supplier_optional":True,"package_policy":{}}
   sp=pathlib.Path(directory)/"snapshot.json"; pp=pathlib.Path(directory)/"policy.json"; sp.write_bytes(canonical_bytes(snap)); pp.write_bytes(canonical_bytes(policy))
   value=create_plan(package,receipt,sp,pp); kinds=[x["kind"] for x in value["operations"]]
   self.assertEqual(["brand","category"],sorted(kinds[:2])); self.assertIn("product",kinds); self.assertEqual(2,kinds.count("image")); self.assertIn("spec",kinds); self.assertIn("technical_sheet",kinds)
   product_payload=next(x for x in value["operations"] if x["kind"]=="product")["payload_template"]
   self.assertEqual({"price":None,"price_visible":False,"is_featured":False,"is_published":False},{key:product_payload[key] for key in ("price","price_visible","is_featured","is_published")})
   self.assertEqual("retained_not_imported",value["retained_documents"][0]["state"]); self.assertEqual("dry_run_ready",simulate(value)["state"])
   images=sorted((x for x in value["operations"] if x["kind"]=="image"),key=lambda x:x["payload_template"]["multipart"]["order"]); self.assertEqual([True,False],[x["payload_template"]["multipart"]["is_main"] for x in images]); self.assertEqual({"product_id","file_entry","sha256","size","mime","alt_text","is_main","order","source_filename"},set(images[0]["payload_template"]["multipart"]))
   outputs=plan_outputs(value,snap); outputs.update({"import-dry-run-manifest.json":simulate(value),"import-dry-run-report.txt":b"synthetic\n"}); self.assertEqual({"jem-state-snapshot.json","import-preflight.json","import-bindings.json","import-operations.jsonl","import-plan.json","import-reviews.jsonl","import-dry-run-manifest.json","import-dry-run-report.txt"},set(outputs))
 def test_package_requires_zip_receipt_and_stable_verified_bytes(self):
  with tempfile.TemporaryDirectory() as directory:
   folder=pathlib.Path(directory); loose=folder/"producto.json"; loose.write_text("{}",encoding="utf-8")
   for candidate in (loose,folder):
    with self.assertRaises(ImportInputError) as caught: read_verified_package(candidate,None,{},lambda *x:None)
    self.assertEqual("INVALID_PACKAGE_INPUT",caught.exception.code)
   package,receipt,_=canonical_package(directory); calls=[]
   def verifier(path,receipt_value,policy): calls.append(path); package.write_bytes(package.read_bytes()+b"changed"); return {"valid":True,"zip_sha256":hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()}
   with self.assertRaises(ImportInputError) as caught: read_verified_package(package,receipt,{},verifier)
   self.assertEqual("PACKAGE_CHANGED",caught.exception.code); self.assertEqual(1,len(calls))
 def test_receipt_and_package_corruption_are_rejected_by_real_verifier(self):
  from catalog_acquisition.packaging import verify_package
  with tempfile.TemporaryDirectory() as directory:
   package,receipt,_=canonical_package(directory); bad=pathlib.Path(directory)/"bad-receipt.json"; value=json.loads(receipt.read_text()); value["zip_size"]+=1; bad.write_bytes(canonical_bytes(value))
   with self.assertRaises(ImportInputError) as caught: read_verified_package(package,bad,{},verify_package)
   self.assertEqual("INVALID_PACKAGE",caught.exception.code)
 def test_blocked_or_empty_package_cannot_be_built_but_exclusions_can(self):
  with tempfile.TemporaryDirectory() as directory:
   with self.assertRaises(PackageError) as caught: canonical_package(directory,blocked=1)
   self.assertEqual("PLAN_BLOCKED",caught.exception.code)
  with tempfile.TemporaryDirectory() as directory:
   package,receipt,_=canonical_package(directory,excluded=2); self.assertTrue(package.is_file()); self.assertTrue(receipt.is_file())
 def test_existing_entities_reuse_and_product_exact_or_divergent(self):
  desired={"canonical_identity":"p","product_type":"machinery","slug":"p","model":"M","sku":None,"payload":{"name":"M"}}
  exact={"id":9,"product_type":"machinery","slug":"p","model":"M","sku":None,"name":"M","relations_complete":True}; self.assertEqual("noop_exact",reconcile_product(desired,[exact])["state"])
  divergent={**exact,"name":"different"}; review=reconcile_product(desired,[divergent]); self.assertEqual("manual_review_required",review["state"]); self.assertEqual("PRODUCT_DIVERGED",review["reason"])
 def test_ambiguous_and_parent_conflicts_block_without_selection(self):
  category={"slug":"child","parent_id":1}; candidates=[{"id":2,"slug":"child","parent_id":1},{"id":3,"slug":"child","parent_id":1}]
  self.assertEqual("AMBIGUOUS_CATEGORY",reconcile_category(category,candidates)["reason"]); self.assertEqual("PARENT_MISMATCH",reconcile_category(category,[{"id":2,"slug":"child","parent_id":9}])["reason"])
  self.assertEqual("AMBIGUOUS_BRAND",reconcile_brand({"slug":"x"},[{"id":1,"slug":"x"},{"id":2,"slug":"x"}])["reason"]); self.assertEqual("AMBIGUOUS_OR_MISSING_SUPPLIER",reconcile_supplier("S",[{"id":1,"name":"S"},{"id":2,"name":"S"}])["reason"])
  desired={"canonical_identity":"p","product_type":"machinery","slug":"p","model":"M","sku":None,"payload":{}}
  ambiguous=reconcile_product(desired,[{"id":1,"product_type":"machinery","slug":"p","model":"M","sku":None},{"id":2,"product_type":"machinery","slug":"p","model":"M","sku":None}]); self.assertEqual("AMBIGUOUS_NATURAL_KEY",ambiguous["reason"]); self.assertEqual(2,len(ambiguous["evidence"]))
 def test_asset_contract_blocks_count_hash_and_missing_entry(self):
  product={"canonical_identity":"p","media":[{"role":"primary","sha256":"0"*64,"size":1,"entry_path":"missing","mime":"image/png"}]}; rec,_=reconcile_assets(product,{})
  self.assertEqual("blocked",rec["state"]); self.assertEqual("ASSET_ENTRY_MISMATCH",rec["reason"])
 def test_snapshot_capture_uses_every_real_endpoint_without_queries(self):
  class Reader:
   def __init__(self): self.calls=[]
   def read_collection(self,name): self.calls.append(name); return []
  reader=Reader(); value=capture_snapshot(reader,"c"*64,"fixture_only"); self.assertEqual(set(COLLECTIONS),set(reader.calls)); self.assertTrue(all("?" not in x["path"] for x in value["endpoints"])); self.assertTrue(value["complete"])
 def test_semantic_snapshot_change_changes_fingerprint(self):
  first=complete_snapshot(); second=copy.deepcopy(first); second["collections"]["categories"][0]["name"]="Changed"
  self.assertNotEqual(semantic_fingerprint(first),semantic_fingerprint(second))
 def test_all_dry_run_guarantees_remain_false_and_zero(self):
  value=simulate(plan([])); self.assertFalse(value["apply_supported"]); self.assertFalse(value["mutation_supported"]); self.assertFalse(value["publication_authorized"]); self.assertFalse(value["import_authorized"]); self.assertEqual((0,0,0),(value["mutations_attempted"],value["mutations_completed"],value["mutating_network_requests"]))
 def test_seven_import_schemas_reject_unsafe_mutations(self):
  names=("jem-state-snapshot","import-policy","import-operation","import-plan","import-preflight-report","import-review","import-dry-run-manifest")
  mutations=(("schema_version","2.0.0"),("state","partial"),("fingerprint","bad"),("apply_supported",True),("mutation_supported",True),("publication_authorized",True),("mutations_attempted",1))
  for name in names:
   original=json.loads((ROOT/"fixtures/valid"/(name+".json")).read_text(encoding="utf-8")); schema=ROOT/"schemas/v1"/(name+".schema.json")
   for field,bad in mutations:
    candidate={**original,field:bad}
    with self.subTest(schema=name,field=field),self.assertRaises(SchemaValidationError): validate(candidate,schema)
   candidate=dict(original); candidate["unexpected"]=True
   with self.assertRaises(SchemaValidationError): validate(candidate,schema)
 def test_architecture_import_direction_and_frozen_sources(self):
  importer="\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT/"jem_nexus_import").glob("*.py")))
  acquisition="\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT/"catalog_acquisition").glob("*.py")))
  self.assertNotIn("catalog_acquisition.packaging",importer); self.assertNotIn("jem_nexus_import",acquisition)
  for forbidden in ("adapters.ep","adapters.gam","jem docs\\temp","LGMG"): self.assertNotIn(forbidden,importer)
 def test_cli_main_runs_snapshot_with_injected_reader_and_exact_exit(self):
  from catalog_import import main
  class Reader:
   def __init__(self,url): self.url=url
   def read_collection(self,name): return []
  with tempfile.TemporaryDirectory() as directory:
   self.assertEqual(0,main(["snapshot-local","--base-url","http://localhost:1","--contract-fingerprint","c"*64,"--output",directory],reader_factory=Reader)); self.assertTrue((pathlib.Path(directory)/"jem-state-snapshot.json").exists())
 def test_cli_normal_path_composes_the_dedicated_transport(self):
  from catalog_import import main
  reader=mock.Mock(); reader.read_collection.return_value=[]
  with tempfile.TemporaryDirectory() as directory,mock.patch("catalog_import.LocalJemJsonReader",return_value=reader) as factory:
   self.assertEqual(0,main(["snapshot-local","--base-url","http://localhost:1","--contract-fingerprint","c"*64,"--output",directory]))
  self.assertIs(get_json_bytes,factory.call_args.kwargs["transport"])
 def test_cli_does_not_disguise_unexpected_filesystem_errors(self):
  from catalog_import import main
  class Reader:
   def __init__(self,url): pass
   def read_collection(self,name): return []
  with mock.patch("catalog_import.write_output_set",side_effect=OSError(errno.EIO,"unexpected")):
   with self.assertRaises(OSError): main(["snapshot-local","--base-url","http://localhost:1","--contract-fingerprint","c"*64,"--output","unused"],reader_factory=Reader)

if __name__=="__main__": unittest.main()
