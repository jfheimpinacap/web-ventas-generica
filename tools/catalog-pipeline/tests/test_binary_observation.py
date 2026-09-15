import ast, contextlib, copy, hashlib, io, json, pathlib, sys, tempfile, unittest
from unittest import mock

ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_binary_observation import BinaryCliError, OUTPUTS, main, parser, write_new_output
from catalog_pipeline_common.serialization import canonical_bytes
from jem_nexus_import.binary_observation import CAPTURE_POLICY, BinaryObservationError, build_plan, capture_plan, normalize_base_url, normalize_reference, validate_plan
from catalog_pipeline_common.binary_validation import validate_observed_binary
from catalog_acquisition.schema_validation import validate
from jem_nexus_import.readiness import assess, contract_fingerprint
from jem_nexus_import.snapshot import COLLECTIONS, READ_TARGETS, semantic_fingerprint
from jem_nexus_local_binary_transport import BinaryTransportError, LocalBinaryTransport


def contract(): return json.loads((ROOT/"schemas/v1/jem-nexus-contract.json").read_text(encoding="utf-8"))
def snapshot():
 c=contract(); value={"schema_version":"1.0.0","complete":True,"classification":"local_development","contract_fingerprint":contract_fingerprint(c),"collections":{
  "categories":[{"id":1,"name":"Maquinaria","slug":"maquinaria","parent_id":None,"product_type":"machinery"},{"id":2,"name":"Sintética","slug":"sintetica","parent_id":1,"product_type":"machinery"}],
  "brands":[{"id":3,"name":"Marca","slug":"marca"}],"suppliers":[{"id":4,"name":"Proveedor"}],
  "products":[{"id":5,"name":"Producto","slug":"producto","category_id":2,"brand_id":3,"supplier_id":4,"technical_sheet_id":8,"relations_complete":True,"model":"S","sku":None,"product_type":"machinery","condition":"used","short_description":"s","description":"d","working_height_m":1.0,"terrain_type":"outdoor","year":2020,"hours_meter":1,"maximum_load_capacity_kg":2.0,"machine_weight_kg":3.0,"power_source":"diesel","includes_technical_review":True,"includes_commercial_technical_advice":True,"includes_coordinated_delivery":True,"price":4.0,"price_currency":"CLP","price_tax_mode":"plus_vat","price_visible":True,"stock_status":"available","is_featured":False,"is_published":False,"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}],
  "product_images":[{"id":6,"product_id":5,"image":"/media/synthetic.jpg","file_url":"/api/product-images/6/file","alt_text":"x","is_main":True,"order":0}],
  "product_specs":[{"id":7,"product_id":5,"key":"altura","value":"1","unit":"m","order":0}],
  "technical_sheets":[{"id":8,"name":"Ficha","original_file_name":"unrelated-name.pdf","content_type":"application/pdf","size_bytes":9,"file_url":"/api/technical-sheets/8/file"}]},
  "endpoints":[{"collection":name,"path":READ_TARGETS[name],"status":200,"mime":"application/json","response_sha256":"a"*64,"pages_received":1,"pages_expected":1,"complete":True} for name in COLLECTIONS]}
 value["semantic_fingerprint"]=semantic_fingerprint(value); return value
def inputs():
 s=snapshot(); r=assess(s,contract()); return s,r,contract(),"a"*64,"b"*64
def plan(value=None, report=None, c=None):
 s,r,base,sh,rh=inputs(); return build_plan(value or s,report or r,c or base,"http://localhost:5000",sh,rh)


FORBIDDEN_MODULES=("urllib.request","http.client","requests","httpx","aiohttp","socket",
                   "jem_nexus_local_transport","jem_nexus_local_mutation_transport")
def architectural_violations(source):
 tree=ast.parse(source); violations=[]; module_aliases={}; os_names=set(); import_module_names=set()
 def forbidden(module): return any(module==name or module.startswith(name+".") for name in FORBIDDEN_MODULES)
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):
   for alias in node.names:
    if forbidden(alias.name): violations.append((node.lineno,"forbidden import",alias.name))
    module_aliases[alias.asname or alias.name.split(".")[0]]=alias.name
  elif isinstance(node,ast.ImportFrom):
   module=node.module or ""
   for alias in node.names:
    imported=module+("." if module else "")+alias.name
    if forbidden(module) or forbidden(imported): violations.append((node.lineno,"forbidden import",imported))
    local=alias.asname or alias.name
    if module=="os" and alias.name in ("environ","getenv"): os_names.add(local)
    if module=="importlib" and alias.name=="import_module": import_module_names.add(local)
 for node in ast.walk(tree):
  if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name):
   if module_aliases.get(node.value.id)=="os" and node.attr in ("environ","getenv"):
    violations.append((node.lineno,"environment access",node.attr))
  if isinstance(node,ast.Name) and node.id in os_names:
   violations.append((node.lineno,"environment access",node.id))
  if not isinstance(node,ast.Call): continue
  dynamic=(isinstance(node.func,ast.Name) and (node.func.id=="__import__" or node.func.id in import_module_names))
  dynamic=dynamic or (isinstance(node.func,ast.Attribute) and node.func.attr=="import_module"
                      and isinstance(node.func.value,ast.Name)
                      and module_aliases.get(node.func.value.id)=="importlib")
  if dynamic and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str) and forbidden(node.args[0].value):
   violations.append((node.lineno,"forbidden dynamic import",node.args[0].value))
 return violations


class BinaryObservationTests(unittest.TestCase):
 def test_01_valid_inputs_and_productive_contract_fingerprint(self):
  value=plan(); self.assertEqual(contract_fingerprint(contract()),value["contract_fingerprint"]); self.assertEqual("planned",value["state"])
 def test_02_snapshot_gates(self):
  for mutation in ("incomplete","fixture"):
   s,r,c,sh,rh=inputs()
   if mutation=="incomplete": s["complete"]=False
   else: s["classification"]="fixture_only"; s["semantic_fingerprint"]=semantic_fingerprint(s)
   with self.subTest(mutation=mutation), self.assertRaises((BinaryObservationError,ValueError)): build_plan(s,r,c,"http://localhost:1",sh,rh)
 def test_03_readiness_result_blocker_and_mutation_gates(self):
  for mutation in ("result","blocker","mutation"):
   s,r,c,sh,rh=inputs()
   if mutation=="result": r["result"]="read_incompatible"
   elif mutation=="blocker": r["blockers"]=[{"code":"SYNTHETIC"}]
   else: r["mutation_authorized"]=True
   semantic=dict(r); semantic.pop("report_fingerprint"); from catalog_pipeline_common.serialization import content_fingerprint; r["report_fingerprint"]=content_fingerprint(semantic)
   with self.subTest(mutation=mutation), self.assertRaises(BinaryObservationError): build_plan(s,r,c,"http://localhost:1",sh,rh)
 def test_04_contradictory_contract_and_snapshot_links(self):
  for field in ("contract_fingerprint","snapshot_fingerprint"):
   s,r,c,sh,rh=inputs(); r[field]="0"*64; semantic=dict(r); semantic.pop("report_fingerprint"); from catalog_pipeline_common.serialization import content_fingerprint; r["report_fingerprint"]=content_fingerprint(semantic)
   with self.subTest(field=field), self.assertRaises(BinaryObservationError): build_plan(s,r,c,"http://localhost:1",sh,rh)
 def test_05_loopback_base_urls(self):
  for value in ("http://localhost:5000","http://127.0.0.1:1","http://[::1]:8080"):
   with self.subTest(value=value): self.assertEqual(value,normalize_base_url(value))
 def test_06_unsafe_base_urls(self):
  values=("https://localhost:1","http://example.invalid:1","http://localhost","http://u:p@localhost:1","http://localhost:1?x=1","http://localhost:1/#x","//localhost:1")
  for value in values:
   with self.subTest(value=value), self.assertRaises(BinaryObservationError): normalize_base_url(value)
 def test_07_safe_root_relative_references(self):
  for value in ("/uploads/example.jpg","/files/example"):
   with self.subTest(value=value): self.assertEqual(value,normalize_reference(value))
 def test_08_unsafe_reference_matrix(self):
  values=("","relative","http://x/a","//x/a","/a?x=1","/a#x","/a\\b","/../a","/a/./b","/%2e%2e/a","/a%2fb","/a%5cb","/a%252fb","/C:/a","C:\\a","\\\\host\\a","/a\0b","/a\x1fb","/a//b","/a./")
  for value in values:
   with self.subTest(value=repr(value)), self.assertRaises(BinaryObservationError): normalize_reference(value)
 def test_09_image_binding_is_relational_and_declared_only(self):
  target=next(target for target in plan()["targets"] if target["media_class"]=="image"); binding=target["bindings"][0]
  self.assertTrue(binding["relation_observable"]); self.assertEqual((5,None,None),(binding["product_id"],binding["declared_extension"],binding["declared_content_type"]))
  self.assertEqual("/api/product-images/6/file",target["root_relative_path"]); self.assertNotEqual("/media/synthetic.jpg",target["root_relative_path"])
 def test_10_extensionless_pdf_relation_is_derived_from_product(self):
  value=next(target for target in plan()["targets"] if target["media_class"]=="technical_sheet")["bindings"][0]
  self.assertEqual((None,"application/pdf",9),(value["declared_extension"],value["declared_content_type"],value["declared_size_bytes"])); self.assertEqual(5,value["product_id"]); self.assertFalse(value["manual_relation_verification_required"])
 def test_11_unassociated_sheet_remains_manual(self):
  s=snapshot(); s["collections"]["products"][0]["technical_sheet_id"]=None; s["collections"]["product_images"]=[]; s["semantic_fingerprint"]=semantic_fingerprint(s); value=plan(s,assess(s,contract()))
  target=next(t for t in value["targets"] if t["media_class"]=="technical_sheet"); self.assertIsNone(target["bindings"][0]["product_id"])
  pdf=b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nstartxref\n9\n%%EOF\n"
  s["collections"]["technical_sheets"][0]["size_bytes"]=len(pdf); s["semantic_fingerprint"]=semantic_fingerprint(s); value=plan(s,assess(s,contract()))
  report=capture_plan(value,value["plan_fingerprint"],"c"*64,lambda base,path,headers,timeout,limit:{"status":200,"mime":"application/pdf","body":pdf,"content_length":str(len(pdf))})
  receipt=report["receipts"][0]; self.assertEqual("observed_manual_relation_verification_required",report["state"]); self.assertTrue(receipt["manual_relation_verification_required"]); self.assertFalse(receipt["relation_observable"]); self.assertEqual("/api/technical-sheets/8/file",receipt["bindings"][0]["root_relative_path"])
 def test_12_duplicates_group_and_preserve_sorted_bindings(self):
  s=snapshot(); duplicate=copy.deepcopy(s["collections"]["product_images"][0]); duplicate["id"]=9; s["collections"]["product_images"].append(duplicate); s["semantic_fingerprint"]=semantic_fingerprint(s); value=plan(s,assess(s,contract())); target=next(t for t in value["targets"] if t["media_class"]=="image")
  self.assertEqual([6,9],[x["row_id"] for x in target["bindings"]]); self.assertEqual(2,value["counts"]["targets_total"])
 def test_12b_shared_sheet_has_one_literal_target_and_two_product_bindings(self):
  s=snapshot(); second=copy.deepcopy(s["collections"]["products"][0]); second.update(id=9,name="Segundo",slug="segundo"); s["collections"]["products"].append(second); s["semantic_fingerprint"]=semantic_fingerprint(s)
  target=next(t for t in plan(s,assess(s,contract()))["targets"] if t["media_class"]=="technical_sheet")
  self.assertEqual("/api/technical-sheets/8/file",target["root_relative_path"]); self.assertEqual([5,9],[b["product_id"] for b in target["bindings"]])
 def test_13_media_class_conflict_blocks(self):
  s=snapshot(); shared=s["collections"]["product_images"][0]["file_url"]; s["collections"]["technical_sheets"][0]["file_url"]=shared; s["semantic_fingerprint"]=semantic_fingerprint(s)
  with self.assertRaisesRegex(BinaryObservationError,shared): plan(s,assess(s,contract()))
 def test_14_order_independent_and_reproducible(self):
  first=plan(); s=snapshot()
  for values in s["collections"].values(): values.reverse()
  s["endpoints"].reverse(); s["semantic_fingerprint"]=semantic_fingerprint(s); second=plan(s,assess(s,contract()))
  self.assertEqual(canonical_bytes(first),canonical_bytes(second))
 def test_15_exact_counters_and_manual_state(self):
  value=plan(); self.assertEqual({"targets_total":2,"image_targets":1,"technical_sheet_targets":1,"bindings_total":2,"relations_observable":2,"manual_relations":0,"blockers":0,"warnings":1},value["counts"])
 def test_16_safety_flags_and_capture_authorization(self):
  value=plan(); self.assertTrue(value["capture_supported"]); self.assertEqual(CAPTURE_POLICY,value["capture_policy"]); self.assertTrue(all(value[key] is False for key in ("network_executed","bytes_observed","mutation_authorized","content_published")))
 def test_17_cli_has_exact_commands_and_no_unsafe_flags(self):
  source=(ROOT/"catalog_binary_observation.py").read_text(encoding="utf-8"); self.assertEqual("plan",parser().parse_args(["plan","--snapshot","s","--readiness","r","--contract","c","--base-url","http://localhost:1","--output-dir","o"]).command); self.assertEqual("capture-local",parser().parse_args(["capture-local","--plan","p","--plan-fingerprint","a"*64,"--output-dir","o"]).command)
  self.assertFalse(any(flag in source for flag in ("--token","--force","--overwrite","--skip",'add_parser("capture")','add_parser("fetch")','add_parser("apply")')))
 def test_18_core_has_no_transport_or_environment(self):
  for path in (ROOT/"jem_nexus_import/binary_observation.py",):
   with self.subTest(path=path): self.assertEqual([],architectural_violations(path.read_text(encoding="utf-8")))
  rejected={
   "import requests":"import requests", "from requests import get":"from requests import get",
   "socket alias":"import socket as s", "urllib from import":"from urllib import request",
   "urllib dotted import":"import urllib.request", "os environ":"import os\nvalue = os.environ",
   "os getenv":"import os as operating\nvalue = operating.getenv('TOKEN')",
   "imported getenv":"from os import getenv as read_env\nvalue = read_env('TOKEN')",
   "imported environ":"from os import environ as env\nvalue = env['TOKEN']",
   "dynamic import":"import importlib as loader\nmodule = loader.import_module('http.client')",
   "builtin dynamic import":"module = __import__('jem_nexus_local_transport')"}
  for label,source in rejected.items():
   with self.subTest(rejected=label): self.assertTrue(architectural_violations(source))
  accepted={
   "contract fields":"assessment_network_requests = mutation_requests = network_requests = requests_dispatched = 0",
   "contract string":"message = 'zero requests; network requests were not dispatched'",
   "documentation":'"""Do not import requests, socket, or urllib.request in this module."""'}
  for label,source in accepted.items():
   with self.subTest(accepted=label): self.assertEqual([],architectural_violations(source))
 def test_19_output_is_atomic_new_only_and_altered_destination_blocks(self):
  with tempfile.TemporaryDirectory() as directory:
   target=pathlib.Path(directory)/"out"; docs={name:b"synthetic\n" for name in OUTPUTS}; write_new_output(target,docs); self.assertEqual(set(OUTPUTS),{x.name for x in target.iterdir()})
   with self.assertRaisesRegex(BinaryCliError,"OUTPUT_DIRECTORY_EXISTS"): write_new_output(target,docs)
 def test_20_symlink_destination_blocks(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); target=root/"out"; unrelated=root/"unrelated.txt"; unrelated.write_bytes(b"preserve me")
   with mock.patch.object(pathlib.Path,"is_symlink",autospec=True,side_effect=lambda candidate: candidate==target) as is_symlink:
    with self.assertRaises(BinaryCliError) as raised: write_new_output(target,{name:b"x" for name in OUTPUTS})
   self.assertEqual("OUTPUT_DIRECTORY_EXISTS",raised.exception.code); is_symlink.assert_called_once_with(target)
   self.assertFalse(target.exists()); self.assertEqual(b"preserve me",unrelated.read_bytes())
   self.assertEqual([],list(root.glob(".out.writing-*")))
 def test_21_cli_writes_canonical_json_and_text(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); s=snapshot(); r=assess(s,contract())
   for name,value in (("s",s),("r",r),("c",contract())): (root/name).write_bytes(canonical_bytes(value))
   self.assertEqual(0,main(["plan","--snapshot",str(root/"s"),"--readiness",str(root/"r"),"--contract",str(root/"c"),"--base-url","http://localhost:1","--output-dir",str(root/"out")]))
   self.assertEqual(json.loads((root/"out"/OUTPUTS[0]).read_text(encoding="utf-8"))["network_executed"],False)
   cases=((b"{","INPUT_JSON_INVALID"),(b"\xff","INPUT_UTF8_INVALID"),(b"[]","INPUT_OBJECT_REQUIRED"))
   for raw,expected in cases:
    bad=root/("bad-"+expected); bad.write_bytes(raw); output=io.StringIO()
    with self.subTest(cli_error=expected), contextlib.redirect_stdout(output):
     self.assertEqual(2,main(["capture-local","--plan",str(bad),"--plan-fingerprint","a"*64,"--output-dir",str(root/"never-created")]))
    self.assertEqual('{"error":"'+expected+'"}\n',output.getvalue()); self.assertFalse((root/"never-created").exists())
   missing_output=io.StringIO()
   with contextlib.redirect_stdout(missing_output): self.assertEqual(2,main(["capture-local","--plan",str(root/"missing"),"--plan-fingerprint","a"*64,"--output-dir",str(root/"never-created")]))
   self.assertEqual('{"error":"INPUT_FILE_UNREADABLE"}\n',missing_output.getvalue())
   with mock.patch("catalog_binary_observation._read",side_effect=RuntimeError("programming defect")):
    with self.assertRaisesRegex(RuntimeError,"programming defect"): main(["capture-local","--plan","unused","--plan-fingerprint","a"*64,"--output-dir","unused"])
   capture=plan(); capture_path=root/"capture-plan"; capture_path.write_bytes(canonical_bytes(capture))
   known=((BinaryObservationError("BINARY_SIGNATURE_INVALID","private /path token"),"BINARY_SIGNATURE_INVALID"),(BinaryTransportError("BINARY_READ_STATUS"),"BINARY_READ_STATUS"))
   for error,expected in known:
    output=io.StringIO()
    with self.subTest(domain_error=expected), mock.patch.dict("os.environ",{"JEM_NEXUS_LOCAL_READ_TOKEN":"secret"},clear=True), mock.patch("catalog_binary_observation.capture_plan",side_effect=error), contextlib.redirect_stdout(output):
     self.assertEqual(2,main(["capture-local","--plan",str(capture_path),"--plan-fingerprint",capture["plan_fingerprint"],"--output-dir",str(root/("report-"+expected))]))
    self.assertEqual('{"error":"'+expected+'"}\n',output.getvalue()); self.assertNotIn("private",output.getvalue()); self.assertNotIn("secret",output.getvalue())
   existing=root/"existing"; existing.mkdir(); output=io.StringIO()
   with contextlib.redirect_stdout(output): self.assertEqual(2,main(["capture-local","--plan",str(capture_path),"--plan-fingerprint",capture["plan_fingerprint"],"--output-dir",str(existing)]))
   self.assertEqual('{"error":"OUTPUT_DIRECTORY_EXISTS"}\n',output.getvalue())
   with mock.patch("catalog_binary_observation.tempfile.mkdtemp",side_effect=PermissionError("private /path")), contextlib.redirect_stdout(output:=io.StringIO()):
    self.assertEqual(2,main(["plan","--snapshot",str(root/"s"),"--readiness",str(root/"r"),"--contract",str(root/"c"),"--base-url","http://localhost:1","--output-dir",str(root/"write-failure")]))
   self.assertEqual('{"error":"OUTPUT_WRITE_FAILED"}\n',output.getvalue()); self.assertFalse((root/"write-failure").exists())
 def test_22_schema_fixture_closed_and_synthetic(self):
  schema=json.loads((ROOT/"schemas/v1/local-binary-observation-plan.schema.json").read_text(encoding="utf-8")); fixture=json.loads((ROOT/"fixtures/valid/local-binary-observation-plan.json").read_text(encoding="utf-8"))
  self.assertFalse(schema["additionalProperties"]); self.assertTrue(fixture["fixture_only"]); self.assertNotIn("example.com",canonical_bytes(fixture).decode())
  produced=plan(); validate(produced,ROOT/"schemas/v1/local-binary-observation-plan.schema.json")
  self.assertTrue(produced["capture_supported"]); self.assertEqual("limited_local_get_capture",produced["next_permitted_step"])
 def test_23_exact_schema_and_json_inventory(self):
  self.assertEqual(82,len(list((ROOT/"schemas/v1").glob("*.schema.json")))); self.assertEqual(83,len(list((ROOT/"schemas/v1").glob("*.json"))))
 def test_24_real_evidence_fingerprints_are_not_hardcoded(self):
  source=(ROOT/"jem_nexus_import/binary_observation.py").read_text(encoding="utf-8")+(ROOT/"fixtures/valid/local-binary-observation-plan.json").read_text(encoding="utf-8")
  self.assertNotIn("7a428a6af88979e589f27ec81146c87543904f3b1c2d49072244d171304e5d21",source); self.assertNotIn("090d2fcf9cefd624b84eb60e141db0a994a4b1ba4ff2977dd986238212783341",source)
 def test_25_file_hashes_affect_plan_fingerprint_but_no_timestamp_does(self):
  s,r,c,sh,rh=inputs(); first=build_plan(s,r,c,"http://localhost:1",sh,rh); second=build_plan(s,r,c,"http://localhost:1","c"*64,rh)
  self.assertNotEqual(first["plan_fingerprint"],second["plan_fingerprint"]); self.assertNotIn("timestamp",first)
 def test_26_v1_is_auditable_but_not_capturable(self):
  from catalog_pipeline_common.serialization import content_fingerprint
  old={"schema_version":"1.0.0","rules_version":"jem-local-binary-observation-plan-v1"}; old["plan_fingerprint"]=content_fingerprint(old)
  self.assertIs(old,validate_plan(old))
  calls=[]
  with self.assertRaisesRegex(BinaryObservationError,"CAPTURE_PLAN_VERSION_UNSUPPORTED"): capture_plan(old,old["plan_fingerprint"],"a"*64,lambda *args:calls.append(args))
  self.assertEqual([],calls)
 def test_26b_v2_is_not_capturable(self):
  from catalog_pipeline_common.serialization import content_fingerprint
  old={"schema_version":"2.0.0","rules_version":"jem-local-binary-observation-plan-v2"}; old["plan_fingerprint"]=content_fingerprint(old)
  calls=[]
  with self.assertRaisesRegex(BinaryObservationError,"CAPTURE_PLAN_VERSION_UNSUPPORTED"): capture_plan(old,old["plan_fingerprint"],"a"*64,lambda *args:calls.append(args))
  self.assertEqual([],calls)
 def test_27_capture_fingerprint_fails_before_transport(self):
  calls=[]
  with self.assertRaisesRegex(BinaryObservationError,"CAPTURE_PLAN_FINGERPRINT_MISMATCH"): capture_plan(plan(),"0"*64,"1"*64,lambda *args:calls.append(args))
  self.assertEqual([],calls)
 def test_28_policy_is_fingerprint_sealed_and_closed(self):
  value=plan(); original=value["plan_fingerprint"]; value["capture_policy"]["retries"]=1
  self.assertNotEqual(original,__import__("catalog_pipeline_common.serialization",fromlist=["content_fingerprint"]).content_fingerprint({k:v for k,v in value.items() if k!="plan_fingerprint"}))
  with self.assertRaises(BinaryObservationError): validate_plan(value,capture=True)
 def test_29_synthetic_jpeg_png_pdf_validation_matrix(self):
  import binascii,struct
  def chunk(kind,data): return struct.pack(">I",len(data))+kind+data+struct.pack(">I",binascii.crc32(kind+data)&0xffffffff)
  ihdr=struct.pack(">IIBBBBB",1,1,8,2,0,0,0)
  png=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",ihdr)+chunk(b"IEND",b"")
  def segment(marker,payload): return b"\xff"+bytes([marker])+struct.pack(">H",len(payload)+2)+payload
  def frame(marker=0xc0,width=1,height=1): return segment(marker,b"\x08"+struct.pack(">HHB",height,width,1)+b"\x01\x11\x00")
  def scan(entropy=b"\x01\x02",components=1): return segment(0xda,bytes([components])+b"\x01\x00"*components+b"\x00\x3f\x00")+entropy
  jpeg=b"\xff\xd8"+segment(0xe0,b"")+frame()+scan()+b"\xff\xd9"
  pdf=b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nstartxref\n9\n%%EOF\n"
  jpeg_cases={
   "baseline":jpeg,
   "stuffed":b"\xff\xd8"+frame(width=320,height=240)+scan(b"\x01\xff\x00\x02")+b"\xff\xd9",
   "restart":b"\xff\xd8"+frame()+segment(0xdd,b"\x00\x01")+scan(b"\x01\xff\xd0\x02\xff\xd7")+b"\xff\xd9",
   "fill":b"\xff\xd8"+b"\xff\xff\xe1\x00\x02"+frame()+scan(b"\x01")+b"\xff\xff\xd9",
   "progressive":b"\xff\xd8"+segment(0xfe,b"synthetic")+segment(0xdb,b"\x00")+segment(0xc4,b"\x00")+frame(0xc2,9,7)+scan()+b"\xff\xd9",
   "progressive-multiscan":b"\xff\xd8"+frame(0xc2)+scan(b"\x01")+scan(b"\x02\xff\x00\x03")+b"\xff\xd9",
  }
  for condition,body in jpeg_cases.items():
   for extension in (".jpg",".jpeg"):
    with self.subTest(jpeg=condition,extension=extension): self.assertIsNone(validate_observed_binary(body,"image","image/jpeg",[{"declared_extension":extension}])["code"])
  valid=((jpeg,"image","image/jpeg",{"declared_extension":".jpg"},"bounded_jpeg_container"),(png,"image","image/png",{"declared_extension":".png"},"bounded_png_container"),(pdf,"technical_sheet","application/pdf",{"declared_size_bytes":len(pdf)},"bounded_pdf_structure_and_safety"))
  for body,media,mime,binding,validation_name in valid:
   with self.subTest(valid=mime):
    result=validate_observed_binary(body,media,mime,[binding]); self.assertIsNone(result["code"]); self.assertEqual(validation_name,result["validation"])
  jpeg_negative={
   "soi":jpeg[2:],"eoi":jpeg[:-2],"after_eoi":jpeg+b"x","sof":b"\xff\xd8"+scan()+b"\xff\xd9",
   "sos":b"\xff\xd8"+frame()+b"\xff\xd9","marker_truncated":b"\xff\xd8"+frame()+scan()+b"\xff",
   "length_underflow":b"\xff\xd8\xff\xe0\x00\x01\xff\xd9","length_overflow":b"\xff\xd8\xff\xe0\xff\xff\xff\xd9",
   "sof_truncated":b"\xff\xd8\xff\xc0\x00\x0b\x08\xff\xd9","zero_height":b"\xff\xd8"+frame(height=0)+scan()+b"\xff\xd9",
   "zero_width":b"\xff\xd8"+frame(width=0)+scan()+b"\xff\xd9","zero_components":b"\xff\xd8"+segment(0xc0,b"\x08\x00\x01\x00\x01\x00")+scan()+b"\xff\xd9",
   "sof_length":b"\xff\xd8"+segment(0xc0,b"\x08\x00\x01\x00\x01\x01")+scan()+b"\xff\xd9",
   "sos_truncated":b"\xff\xd8"+frame()+b"\xff\xda\x00\x08\x01\xff\xd9","sos_length":b"\xff\xd8"+frame()+segment(0xda,b"\x01\x01\x00")+b"\xff\xd9",
   "scan_unterminated":b"\xff\xd8"+frame()+scan(b"\x01"),"invalid_marker":b"\xff\xd8"+frame()+b"\xff\x02\x00\x02"+scan()+b"\xff\xd9",
   "second_soi":b"\xff\xd8"+frame()+b"\xff\xd8"+scan()+b"\xff\xd9","restart_outside_scan":b"\xff\xd8"+frame()+b"\xff\xd0"+scan()+b"\xff\xd9",
   "prefix_suffix_only":b"\xff\xd8\xff\xd9"}
  png_negative={"signature":b"X"+png[1:],"ihdr_missing":b"\x89PNG\r\n\x1a\n"+chunk(b"IEND",b""),"ihdr_duplicate":b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",ihdr)*2+chunk(b"IEND",b""),"crc":png[:-1]+bytes([png[-1]^1]),"iend_missing":png[:-12],"after_iend":png+b"x","chunk_truncated":png[:-1]}
  for family,cases,media,mime,binding in (("jpeg",jpeg_negative,"image","image/jpeg",{"declared_extension":".jpg"}),("png",png_negative,"image","image/png",{"declared_extension":".png"})):
   for condition,body in cases.items():
    with self.subTest(family=family,condition=condition): self.assertEqual("BINARY_SIGNATURE_INVALID",validate_observed_binary(body,media,mime,[binding])["code"])
  pdf_negative={"header":b"X"+pdf[1:],"version":pdf.replace(b"PDF-1.4",b"PDF-3.0"),"eof":pdf.replace(b"%%EOF",b""),"startxref_missing":pdf.replace(b"startxref\n9\n",b""),"startxref_invalid":pdf.replace(b"startxref\n9",b"startxref\n9999")}
  for condition,body in pdf_negative.items():
   with self.subTest(pdf=condition): self.assertEqual("BINARY_SIGNATURE_INVALID",validate_observed_binary(body,"technical_sheet","application/pdf",[{"declared_size_bytes":len(body)}])["code"])
  for token in (b"/Encrypt",b"/JavaScript",b"/JS",b"/Launch",b"/EmbeddedFile",b"/OpenAction",b"/AA"):
   body=pdf+token
   with self.subTest(pdf_unsafe=token): self.assertEqual("BINARY_PDF_UNSAFE",validate_observed_binary(body,"technical_sheet","application/pdf",[{"declared_size_bytes":len(body)}])["code"])
  self.assertEqual("BINARY_SIZE_MISMATCH",validate_observed_binary(pdf,"technical_sheet","application/pdf",[{"declared_size_bytes":1}])["code"])
  self.assertEqual("BINARY_SIGNATURE_INVALID",validate_observed_binary(png,"image","image/png",[{"declared_extension":".jpg"}])["code"])

  source=snapshot(); source["collections"]["product_images"].append({"id":9,"product_id":5,"image":"/media/synthetic.png","file_url":"/api/product-images/9/file","alt_text":"y","is_main":False,"order":1}); source["collections"]["technical_sheets"][0]["size_bytes"]=len(pdf)
  source["semantic_fingerprint"]=semantic_fingerprint(source); value=plan(source,assess(source,contract())); original=copy.deepcopy(value)
  canonical_sheet_path="/api/technical-sheets/8/file"
  self.assertEqual(canonical_sheet_path,source["collections"]["technical_sheets"][0]["file_url"])
  self.assertEqual(canonical_sheet_path,next(target["root_relative_path"] for target in value["targets"] if target["media_class"]=="technical_sheet"))
  responses={"/api/product-images/6/file":("image/jpeg",jpeg),"/api/product-images/9/file":("image/png",png),canonical_sheet_path:("application/pdf",pdf)}
  class SyntheticTransport:
   def __init__(self): self.calls=[]
   def __call__(self,base,path,headers,timeout,limit):
    self.calls.append((base,path,copy.deepcopy(headers),timeout,limit))
    if path not in responses: raise AssertionError("UNEXPECTED_SYNTHETIC_URL: "+path)
    mime,body=responses[path]
    return {"status":200,"mime":mime,"body":body,"content_length":str(len(body))}
  transports=[SyntheticTransport(),SyntheticTransport()]
  reports=[capture_plan(value,value["plan_fingerprint"],"c"*64,transport) for transport in transports]
  self.assertEqual(original,value); self.assertEqual(reports[0],reports[1]); validate(reports[0],ROOT/"schemas/v1/local-binary-observation-report.schema.json")
  expected_paths=[target["root_relative_path"] for target in value["targets"]]
  for transport in transports:
   self.assertEqual(expected_paths,[call[1] for call in transport.calls]); self.assertEqual(len(value["targets"]),len(transport.calls))
   self.assertIn(canonical_sheet_path,[call[1] for call in transport.calls])
   with self.assertRaisesRegex(AssertionError,"UNEXPECTED_SYNTHETIC_URL"): transport(value["base_url"],"/unexpected",{},15,1)
  receipts={receipt["target_id"]:receipt for receipt in reports[0]["receipts"]}
  self.assertEqual(len(value["targets"]),len(receipts))
  for target in value["targets"]:
   receipt=receipts[target["target_id"]]; mime,body=responses[target["root_relative_path"]]
   self.assertEqual((target["target_id"],target["media_class"],target["bindings"]),(receipt["target_id"],receipt["media_class"],receipt["bindings"])); self.assertEqual((mime,len(body),hashlib.sha256(body).hexdigest()),(receipt["observed_mime"],receipt["observed_size_bytes"],receipt["observed_sha256"])); self.assertTrue(receipt["binary_validation"].startswith("bounded_"))
  sheet_receipt=next(receipt for receipt in reports[0]["receipts"] if receipt["media_class"]=="technical_sheet")
  self.assertEqual("observed",reports[0]["state"]); self.assertFalse(sheet_receipt["manual_relation_verification_required"])
  self.assertTrue(sheet_receipt["relation_observable"]); self.assertEqual(5,sheet_receipt["bindings"][0]["product_id"]); self.assertEqual(canonical_sheet_path,sheet_receipt["bindings"][0]["root_relative_path"])
  def contains_body(item): return isinstance(item,(bytes,bytearray,memoryview)) or (isinstance(item,dict) and any(contains_body(x) for x in item.values())) or (isinstance(item,list) and any(contains_body(x) for x in item))
  self.assertFalse(contains_body(reports[0])); json.dumps(reports[0])
  response_negative={
   "response":("BINARY_READ_RESPONSE_INVALID",{"status":200,"mime":"application/pdf","body":pdf}),
   "mime":("BINARY_READ_MIME",{"status":200,"mime":"image/png","body":pdf,"content_length":str(len(pdf))}),
   "empty":("BINARY_READ_EMPTY",{"status":200,"mime":"application/pdf","body":b"","content_length":"0"}),
   "content_length":("BINARY_CONTENT_LENGTH_MISMATCH",{"status":200,"mime":"application/pdf","body":pdf,"content_length":str(len(pdf)+1)}),
   "too_large":("BINARY_READ_TOO_LARGE",{"status":200,"mime":"application/pdf","body":b"x"*(CAPTURE_POLICY["max_pdf_bytes"]+1),"content_length":str(CAPTURE_POLICY["max_pdf_bytes"]+1)}),
   "status":("BINARY_READ_STATUS",{"status":404,"mime":"application/pdf","body":pdf,"content_length":str(len(pdf))}),
   "structure":("BINARY_SIGNATURE_INVALID",{"status":200,"mime":"application/pdf","body":pdf[:-6],"content_length":str(len(pdf)-6)}),
  }
  for condition,(code,response) in response_negative.items():
   with self.subTest(response=condition):
    negative_calls=[]
    def rejecting_transport(base,path,headers,timeout,limit,response=response):
     negative_calls.append(path)
     if path==canonical_sheet_path: return response
     if path not in responses: raise AssertionError("UNEXPECTED_SYNTHETIC_URL: "+path)
     mime,body=responses[path]
     return {"status":200,"mime":mime,"body":body,"content_length":str(len(body))}
    with self.assertRaisesRegex(BinaryObservationError,code): capture_plan(value,value["plan_fingerprint"],"c"*64,rejecting_transport)
    sheet_index=expected_paths.index(canonical_sheet_path)
    self.assertEqual(expected_paths[:sheet_index+1],negative_calls)
  aggregate_plan=copy.deepcopy(value); aggregate_plan["capture_policy"]["max_total_bytes"]=len(pdf)
  aggregate_plan["plan_fingerprint"]=__import__("catalog_pipeline_common.serialization",fromlist=["content_fingerprint"]).content_fingerprint({key:item for key,item in aggregate_plan.items() if key!="plan_fingerprint"})
  with mock.patch.dict(CAPTURE_POLICY,{"max_total_bytes":len(pdf)}), self.assertRaisesRegex(BinaryObservationError,"BINARY_TOTAL_LIMIT_EXCEEDED"):
   capture_plan(aggregate_plan,aggregate_plan["plan_fingerprint"],"c"*64,SyntheticTransport())
 def test_30_capture_response_taxonomy_is_stable(self):
  source=(ROOT/"jem_nexus_import/binary_observation.py").read_text(encoding="utf-8")
  for code in ("BINARY_READ_STATUS","BINARY_READ_MIME","BINARY_READ_EMPTY","BINARY_CONTENT_LENGTH_INVALID","BINARY_CONTENT_LENGTH_MISMATCH","BINARY_READ_TOO_LARGE","BINARY_TOTAL_LIMIT_EXCEEDED","BINARY_SIGNATURE_INVALID","BINARY_SIZE_MISMATCH","BINARY_PDF_UNSAFE"):
   with self.subTest(code=code): self.assertIn(code,source+(ROOT/"catalog_pipeline_common/binary_validation.py").read_text(encoding="utf-8"))
  class Response:
   status=200; headers={"Content-Type":"image/jpeg","Content-Length":"1"}
   def __enter__(self): return self
   def __exit__(self,*unused): return None
   def read(self,limit): return b"x"
  class Opener:
   def __init__(self,result): self.result=result; self.requests=[]
   def open(self,request,timeout):
    self.requests.append((request,timeout))
    if isinstance(self.result,BaseException): raise self.result
    return self.result
  def factory(opener): return lambda *handlers: opener
  for status in (401,404):
   from urllib.error import HTTPError
   opener=Opener(HTTPError("http://localhost:1/private",status,"private",{},None)); transport=LocalBinaryTransport("secret",factory(opener))
   with self.subTest(http=status), self.assertRaises(BinaryTransportError) as raised: transport("http://localhost:1","/synthetic.jpg",{},15,10)
   self.assertEqual("BINARY_READ_STATUS",raised.exception.code); self.assertEqual("GET",opener.requests[0][0].method)
  response=Response(); response.status=302; opener=Opener(response); transport=LocalBinaryTransport("secret",factory(opener))
  with self.assertRaises(BinaryTransportError) as raised: transport("http://localhost:1","/synthetic.jpg",{},15,10)
  self.assertEqual("BINARY_READ_REDIRECT",raised.exception.code)
  with self.assertRaises(BinaryTransportError) as raised: LocalBinaryTransport("",factory(Opener(Response())))
  self.assertEqual("CAPTURE_TOKEN_MISSING",raised.exception.code)
  with self.assertRaises(BinaryTransportError) as raised: LocalBinaryTransport("secret",factory(Opener(Response())))("http://example.invalid:1","/x",{},15,10)
  self.assertEqual("UNSAFE_LOCAL_TARGET",raised.exception.code)

if __name__=="__main__": unittest.main()
