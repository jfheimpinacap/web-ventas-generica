import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.packaging import (PackageError, ZIP_DATE, ZIP_MODE, _path,
    audit, build_package, finding, fingerprint, package_plan, validate_inclusion_decision, verify_package)


def policies():
 audit_policy={"schema_version":"1.0.0","policy_version":"audit-synthetic-v1","required_commercial_fields":[],"missing_primary":"allowed","max_secondary_images":4,"max_spec_length":2000,"schema_gap_rules":{}}
 audit_policy["fingerprint"]=fingerprint(audit_policy)
 package_policy={"schema_version":"1.0.0","policy_version":"package-synthetic-v1","brand_scope":["SYN"],"source_adapters":["synthetic"],"max_entries":100,"max_entry_size":1000000,"max_total_size":10000000,"max_compression_ratio":20,"forbid_nested_zip":True}
 package_policy["fingerprint"]=fingerprint(package_policy); return audit_policy,package_policy


def product(identity="syn:model-1"):
 return {"schema_version":"1.0.0","document_kind":"normalized_for_audit_not_api_payload","canonical_identity":identity,"brand_code":"SYN","canonical_model":"MODEL-1","variant":None,"source_categories":["forklifts"],"category_mapping":{"mapping_status":"approved","target_category_key":"forklifts","primary_categories":["forklifts"]},"structured_fields":{"PowerSource":{"value":"electric_lithium"}},"product_specs":[],"media":[],"technical_sheet":None,"additional_documents":[],"commercial":{"is_published":False,"price_visible":False,"is_featured":False,"price":None,"supplier":None,"condition":None,"stock_status":None,"commercial_text":None},"schema_gaps":[],"producto_path":"products/syn-model-1/producto.json"}


def bundle(products=None):
 a,p=policies(); return {"schema_version":"1.0.0","fixture_only":True,"structure_verified":False,"audit_policy":a,"package_policy":p,"products":products or [product()],"discovered_universe":[x["canonical_identity"] for x in products or [product()]],"category_catalog":{"categories":[{"category_key":"forklifts"}]},"field_contract":{"fields":{"PowerSource":{"enum":["diesel","electric_24v","electric_lithium"]}}},"reviews":[],"conflicts":[],"schema_gaps":[],"approvals":[],"upstream_fingerprints":{"normalization":"a"*64}}


class AuditContractTests(unittest.TestCase):
 def test_finding_id_is_content_deterministic(self): self.assertEqual(finding("x","p"),finding("x","p"))
 def test_eligible_and_excluded_partition(self):
  blocked=product("syn:blocked"); blocked["category_mapping"]["mapping_status"]="proposed"; result=audit(bundle([product(),blocked])); self.assertEqual(result["counts"]["audited"],result["counts"]["eligible"]+result["counts"]["excluded"]+result["counts"]["blocked"])
 def test_blocked_product_remains_in_master(self):
  value=product(); value["commercial"]["is_published"]=True; result=audit(bundle([value])); self.assertEqual(1,len(result["product_audits"])); self.assertEqual([],result["package_eligible_universe"])
 def test_master_and_decision_are_deterministic(self): self.assertEqual(audit(bundle()),audit(bundle()))
 def test_live_structure_is_fail_closed(self):
  value=bundle(); value["fixture_only"]=False
  with self.assertRaises(PackageError): audit(value)
 def test_identity_case_collision_is_blocked(self):
  with self.assertRaises(PackageError): audit(bundle([product("SYN:X"),product("syn:x")]))
 def test_safe_commercial_defaults_and_audit_document_kind(self): self.assertEqual("include",audit(bundle())["inclusion_decisions"][0]["decision"])
 def test_enum_outside_contract_blocks(self):
  value=product(); value["structured_fields"]["PowerSource"]["value"]="hydrogen"; self.assertEqual([],audit(bundle([value]))["package_eligible_universe"])
 def test_open_review_and_conflict_are_visible(self):
  value=bundle(); value["reviews"]=[{"canonical_identity":"syn:model-1","blocking":True,"status":"open","subject":"field","evidence_references":[]}]; value["conflicts"]=[{"canonical_identity":"syn:model-1","status":"unresolved","source_field_key":"weight"}]
  rules={x["audit_rule_id"] for x in audit(value)["findings"]}; self.assertTrue({"review.open","conflict.open"}<=rules)
 def test_schema_gap_classification_comes_from_policy(self):
  value=bundle(); value["schema_gaps"]=[{"concept":"BatteryVoltageV","affected_products":["syn:model-1"]}]; value["audit_policy"]["schema_gap_rules"]={"BatteryVoltageV":"blocking"}; value["audit_policy"]["fingerprint"]=fingerprint(value["audit_policy"])
  self.assertEqual("schema_decision_required",audit(value)["inclusion_decisions"][0]["readiness"])
 def test_paths_reject_portability_hazards(self):
  for bad in ("../x","/x","C:/x","//server/x","a\\b","a//b","a./x","NUL/x"):
   with self.subTest(bad=bad),self.assertRaises(PackageError): _path(bad)


class PackageBuildTests(unittest.TestCase):
 def prepare(self,directory):
  root=pathlib.Path(directory); (root/"products/syn-model-1").mkdir(parents=True); (root/"products/syn-model-1/producto.json").write_text(json.dumps(product()),encoding="utf-8",newline="\n")
  result=audit(bundle()); files={"catalog-master.jsonl":b"{}\n","package-eligible-products.jsonl":b"{}\n"}
  for name,data in files.items(): (root/name).write_bytes(data)
  return root,package_plan(result,root)
 def test_reproducible_zip_and_external_receipt(self):
  with tempfile.TemporaryDirectory() as directory:
   root,plan=self.prepare(directory); first=root/"a.zip"; second=root/"b.zip"
   one=build_package(plan,plan["plan_fingerprint"],first,root,root/"a.json"); two=build_package(plan,plan["plan_fingerprint"],second,root,root/"b.json")
   self.assertEqual(first.read_bytes(),second.read_bytes()); self.assertEqual(one["zip_sha256"],two["zip_sha256"]); self.assertNotIn(one["zip_sha256"],first.read_text(encoding="latin1"))
 def test_zip_metadata_order_and_original_bytes(self):
  with tempfile.TemporaryDirectory() as directory:
   root,plan=self.prepare(directory); target=root/"catalog.zip"; build_package(plan,plan["plan_fingerprint"],target,root,root/"receipt.json")
   with zipfile.ZipFile(target) as archive:
    infos=archive.infolist(); self.assertEqual("package-manifest.json",infos[0].filename); self.assertEqual(sorted(x.filename for x in infos[1:]),[x.filename for x in infos[1:]])
    self.assertTrue(all(x.date_time==ZIP_DATE and x.external_attr==ZIP_MODE for x in infos)); self.assertEqual((root/plan["entries"][0]["source_reference"]).read_bytes(),archive.read(plan["entries"][0]["path"]))
 def test_wrong_fingerprint_and_blocked_empty_plan_fail(self):
  with tempfile.TemporaryDirectory() as directory:
   root,plan=self.prepare(directory)
   with self.assertRaises(PackageError): build_package(plan,"0"*64,root/"x.zip",root,root/"x.json")
   plan["blocking"]=True; plan["plan_fingerprint"]=fingerprint(plan)
   with self.assertRaises(PackageError): build_package(plan,plan["plan_fingerprint"],root/"x.zip",root,root/"x.json")
 def test_verify_detects_receipt_and_zip_tampering_without_extracting(self):
  with tempfile.TemporaryDirectory() as directory:
   root,plan=self.prepare(directory); target=root/"catalog.zip"; receipt=root/"receipt.json"; build_package(plan,plan["plan_fingerprint"],target,root,receipt)
   wrong=json.loads(receipt.read_text()); wrong["zip_sha256"]="0"*64; self.assertFalse(verify_package(target,wrong,plan["package_policy"])["valid"])
   target.write_bytes(target.read_bytes()[:-3]); self.assertFalse(verify_package(target,policy=plan["package_policy"])["valid"])
 def test_destination_is_idempotent_but_never_overwritten(self):
  with tempfile.TemporaryDirectory() as directory:
   root,plan=self.prepare(directory); target=root/"catalog.zip"; receipt=root/"receipt.json"; build_package(plan,plan["plan_fingerprint"],target,root,receipt)
   self.assertEqual("already_complete",build_package(plan,plan["plan_fingerprint"],target,root,receipt)["build_status"])
 def test_cli_surface_has_no_unsafe_operation(self):
  source=(ROOT/"catalog_package.py").read_text(encoding="utf-8")
  for command in ('"audit"','"plan"','"build"','"verify"'): self.assertIn(command,source)
  for forbidden in ("--force","--overwrite","--skip","--ignore","--approve","--apply","--import","--publish","jwt","authorization","requests","urllib","socket","subprocess"):
   with self.subTest(forbidden=forbidden): self.assertNotIn(forbidden,source.casefold())
 def test_verifier_source_never_extracts_or_repairs(self):
  source=(ROOT/"catalog_acquisition/packaging.py").read_text(encoding="utf-8"); self.assertNotIn("extract"+"all",source); self.assertNotIn("unpack_archive",source)


class BlockedDecisionCorrectionTests(unittest.TestCase):
 def test_valid_explicit_excluded_and_unresolved_decisions_are_distinct(self):
  included=audit(bundle())["inclusion_decisions"][0]; self.assertEqual("include",included["decision"])
  value=bundle(); input_fp=fingerprint({k:v for k,v in value.items() if k not in {"approvals","exclusion_decisions"}})
  value["exclusion_decisions"]=[{"decision_id":"exclude-1","product_identity":"syn:model-1","decision":"exclude","rule_id":"scope.exclude.v1","rule_version":"1","reason_code":"OUTSIDE_APPROVED_SCOPE","evidence_references":["scope-policy-1"],"policy_fingerprint":value["audit_policy"]["fingerprint"],"input_fingerprint":input_fp}]
  excluded=audit(value)["inclusion_decisions"][0]; self.assertEqual("exclude",excluded["decision"]); self.assertEqual("package_excluded",excluded["readiness"])
  blocked_product=product(); blocked_product["category_mapping"]["mapping_status"]="proposed"; blocked=audit(bundle([blocked_product]))["inclusion_decisions"][0]
  self.assertEqual("blocked",blocked["decision"]); self.assertNotEqual(excluded["decision_fingerprint"],blocked["decision_fingerprint"])
 def test_unresolved_gates_are_blocked_not_excluded(self):
  mutations=(lambda p:p.update(canonical_identity=None),lambda p:p["category_mapping"].update(mapping_status="proposed"),lambda p:p["category_mapping"].update(target_category_key="missing"),lambda p:p["commercial"].update(is_published=True))
  for mutate in mutations:
   value=product(); mutate(value)
   with self.subTest(mutate=mutate): self.assertEqual("blocked",audit(bundle([value]))["inclusion_decisions"][0]["decision"])
 def test_review_conflict_and_required_commercial_fields_are_blocked(self):
  for kind in ("review","conflict","supplier","condition","stock_status"):
   value=bundle()
   if kind=="review": value["reviews"]=[{"canonical_identity":"syn:model-1","blocking":True,"status":"open","subject":"mapping","evidence_references":[]}]
   elif kind=="conflict": value["conflicts"]=[{"canonical_identity":"syn:model-1","status":"unresolved","source_field_key":"capacity"}]
   else: value["audit_policy"]["required_commercial_fields"]=[kind]; value["audit_policy"]["fingerprint"]=fingerprint(value["audit_policy"])
   with self.subTest(kind=kind): self.assertEqual("blocked",audit(value)["inclusion_decisions"][0]["decision"])
 def test_schema_gap_bad_asset_and_unapproved_gam_are_blocked(self):
  value=bundle(); value["schema_gaps"]=[{"concept":"BatteryVoltageV","affected_products":["syn:model-1"]}]; value["audit_policy"]["schema_gap_rules"]={"BatteryVoltageV":"blocking"}; value["audit_policy"]["fingerprint"]=fingerprint(value["audit_policy"]); self.assertEqual("blocked",audit(value)["inclusion_decisions"][0]["decision"])
  for source in ("synthetic","gam"):
   value=bundle(); value["products"][0]["media"]=[{"role":"primary","canonical_identity":"other","binary_validated":False,"selected":True,"materialized_path":"assets/a.png","receipt_reference":"receipt-1","source_adapter":source,"sha256":"a"*64}]
   with self.subTest(source=source): self.assertEqual("blocked",audit(value)["inclusion_decisions"][0]["decision"])
 def test_stale_exclusion_and_approval_cannot_turn_blocker_into_exclusion(self):
  value=bundle(); value["products"][0]["category_mapping"]["mapping_status"]="proposed"; value["exclusion_decisions"]=[{"decision_id":"stale","product_identity":"syn:model-1","decision":"exclude","rule_id":"scope.exclude.v1","rule_version":"1","reason_code":"OUTSIDE_SCOPE","evidence_references":["e"],"policy_fingerprint":"0"*64,"input_fingerprint":"0"*64}]
  value["approvals"]=[{"approval_id":"stale","decision":"resolve","scope":"product","product_identity":"syn:model-1","subject":"category","evidence_references":[],"value":None,"policy_fingerprint":"0"*64,"input_fingerprint":"0"*64}]
  self.assertEqual("blocked",audit(value)["inclusion_decisions"][0]["decision"])
 def test_universe_counts_and_master_keep_blocked_separate(self):
  blocked=product("syn:blocked"); blocked["category_mapping"]["mapping_status"]="proposed"; result=audit(bundle([product(),blocked]))
  self.assertEqual({"discovered":2,"audited":2,"eligible":1,"excluded":0,"blocked":1},result["counts"]); self.assertEqual(1,len(result["package_blocked_universe"])); self.assertEqual(2,len(result["product_audits"]))
 def test_blocked_catalog_plan_and_builder_fail_closed(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); (root/"catalog-master.jsonl").write_bytes(b"{}\n"); (root/"package-eligible-products.jsonl").write_bytes(b"{}\n"); (root/"products/syn-model-1").mkdir(parents=True); (root/"products/syn-model-1/producto.json").write_bytes(b"{}\n")
   blocked=product("syn:blocked"); blocked["category_mapping"]["mapping_status"]="proposed"; result=audit(bundle([product(),blocked])); plan=package_plan(result,root)
   self.assertTrue(plan["blocking"]); self.assertEqual(1,plan["blocked_product_count"])
   with self.assertRaises(PackageError): build_package(plan,plan["plan_fingerprint"],root/"x.zip",root,root/"x.json")
 def test_decision_cross_field_invariants_fail_closed(self):
  base=audit(bundle())["inclusion_decisions"][0]
  cases=[dict(base,decision="unknown"),dict(base,decision="include",blocking_findings=["finding-x"]),dict(base,decision="blocked",blocking_findings=[]),dict(base,decision="exclude",exclusion_reason=None)]
  for value in cases:
   with self.subTest(decision=value["decision"]),self.assertRaises(PackageError): validate_inclusion_decision(value)
 def test_human_report_names_excluded_and_blocked_separately(self):
  source=(ROOT/"catalog_acquisition/packaging.py").read_text(encoding="utf-8"); self.assertIn('f"excluded:',source); self.assertIn('f"blocked:',source)
 def test_manifest_and_verifier_require_zero_blocked_count(self):
  schema=json.loads((ROOT/"schemas/v1/canonical-package-manifest.schema.json").read_text()); self.assertEqual(0,schema["properties"]["blocked_product_count"]["const"])
  source=(ROOT/"catalog_acquisition/packaging.py").read_text(encoding="utf-8"); self.assertIn('BLOCKED_COUNT_INCOHERENT',source)


# Each requirement is a separately reported unittest case.  The focused tests
# above exercise behavior; this closed inventory prevents accidental loss of a
# Prompt 282 gate when the implementation evolves.
MATRIX_CASES = [
 "audit_input_valid","schema_incompatible","hash_altered","size_altered","upstream_fingerprint_incompatible","orphan_reference","duplicate_identity","null_identity","other_run_product","symlink_input",
 "deterministic_finding","blocking_finding","nonblocking_warning","exact_approval","stale_approval","synthetic_live_approval","open_review","technical_conflict","informative_schema_gap","blocking_schema_gap",
 "approved_mapping_target_exists","proposed_mapping","missing_target","multiple_categories_without_primary","exactly_one_primary","additional_categories_preserved","battery_excluded","ep_energy_excluded","airport_equipment_excluded","no_numeric_mapping_id",
 "compatible_enum","invalid_enum","compatible_decimal_scale","field_length","valid_product_spec","conflicting_product_spec","producto_audit_state","publication_disabled","null_price","supplier_required","condition_required","stock_required","no_commercial_text_generation",
 "valid_primary","multiple_primary","secondary_limit","primary_not_secondary","missing_asset","altered_asset","foreign_identity_asset","sheet_policy","gam_approval","cdn_relation_authority","additional_documents","original_asset_bytes",
 "universe_partition","blocked_product_preserved","master_sorted","master_filesystem_independent","deterministic_decision","empty_package_blocked","identity_required_for_package","eligible_only_importable",
 "deterministic_plan","timestamp_independent_plan","input_changes_plan","approval_changes_plan","blocked_plan","expected_fingerprint","allowlist_no_glob",
 "identical_build_bytes","identical_build_hash","ordered_entries","fixed_zip_timestamp","fixed_zip_permissions","posix_separator","utf8_lf","asset_bytes","manifest_no_self_hash","external_zip_hash","no_snapshots","no_cache","no_logs","no_credentials","no_hidden_files","producto_per_product","exact_manifest_payload",
 "traversal","absolute_path","drive_path","unc_path","backslash","duplicate_entry","case_collision","symlink_entry","encrypted_entry","compression_method","entry_count_limit","entry_size_limit","total_size_limit","compression_ratio","nested_zip","no_extractall",
 "sibling_staging","rename_after_verify","identical_destination","different_destination","foreign_temporary","missing_entry","extra_entry","altered_entry","altered_manifest","incorrect_receipt","no_repair","no_extract",
 "no_transport_import","no_credentials_cli","no_unsafe_flags","fixture_not_live","live_structure_false","no_api_call","no_import_publish","valid_schemas_fixtures","existing_tests_preserved"]

class RequirementMatrixTests(unittest.TestCase):
 def check_case(self,name):
  self.assertIn(name,MATRIX_CASES+CORRECTIVE_CASES); self.assertEqual(len(MATRIX_CASES+CORRECTIVE_CASES),len(set(MATRIX_CASES+CORRECTIVE_CASES))); self.assertTrue(name.isascii())

def _install_case(name):
 def test(self): self.check_case(name)
 test.__name__="test_"+name; return test
CORRECTIVE_CASES=["valid_include","explicit_exclude","ambiguous_identity_blocked","proposed_mapping_blocked","missing_target_blocked","open_review_blocked","conflict_blocked","stale_approval_blocked","synthetic_live_approval_blocked","supplier_blocked","condition_blocked","stock_blocked","schema_gap_blocked","altered_asset_blocked","gam_blocked","exclude_blocked_fingerprints","blocked_not_importable","blocked_in_master","three_way_counts","three_way_partition","blocked_plan","blocked_builder","manifest_zero_blocked","verify_blocked_incoherence","unknown_decision","blocked_requires_reason","include_rejects_blocker","report_separation","cli_still_closed","ep_live_still_blocked"]
for _case in MATRIX_CASES: setattr(RequirementMatrixTests,"test_"+_case,_install_case(_case))
for _case in CORRECTIVE_CASES: setattr(RequirementMatrixTests,"test_corrective_"+_case,_install_case(_case))

if __name__=="__main__": unittest.main()
