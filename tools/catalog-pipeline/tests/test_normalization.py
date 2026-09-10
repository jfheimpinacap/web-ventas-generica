import copy, hashlib, json, pathlib, sys, tempfile, unittest
from decimal import Decimal

ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.normalization import (NormalizationError, build_plan, fingerprint,
    map_categories, normalize_observation, normalize_to, parse_measure, validate_inputs, verify_output)

def numeric(**changes):
    value={"kind":"number","rule_id":"numeric.v1","rule_version":"1","decimal_separator":".","thousands_separator":None,"target_unit":"m","scale":3,"rounding":"ROUND_HALF_EVEN","conversions":{"mm->m":"0.001"}}
    value.update(changes); return value
def policy(rules=None):
    value={"schema_version":"1.0.0","policy_version":"normalization-ep-v1","field_rules":rules or {}}
    value["fingerprint"]=fingerprint(value); return value
def observation(key="working_height",raw="3",unit="m",source="ep_html"):
    return {"canonical_identity":"synthetic-1","model":"MODEL-1","variant":None,"source_field_key":key,"source_label":key.replace("_"," ").title(),"raw_value":raw,"raw_unit":unit,"source":source,"source_url":"https://example.invalid/evidence-only","source_document":None,"source_page":None,"source_section":"specifications","extraction_rule":"table.v1","evidence_references":["e-1"],"relation_references":["r-1"],"locale":"en","qualifiers":[]}
def bundle(observations=None,mapping="approved"):
    rules={"working_height":numeric(target_field="WorkingHeightM"),"lift_height":numeric(target_field="WorkingHeightM",target_unit="mm",conversions={"m->mm":"1000"}),"rated_load_capacity":numeric(target_field="MaximumLoadCapacityKg",target_unit="kg",scale=0,conversions={}),"machine_weight":numeric(target_field="MachineWeightKg",target_unit="kg",scale=0,conversions={}),"battery_capacity":numeric(target_field="MaximumLoadCapacityKg",target_unit="Ah",scale=0,conversions={}),"power_source":{"kind":"enum","rule_id":"power.v1","rule_version":"1","target_field":"PowerSource"}}
    return {"schema_version":"1.0.0","fixture_only":True,"structure_verified":False,"artifact_references":[],"products":[{"canonical_identity":"synthetic-1","brand_code":"SYN","canonical_model":"MODEL-1","variant":None,"source_titles":["Synthetic MODEL-1"],"source_category_keys":["forklifts"]}],"observations":observations or [observation()],"policy":policy(rules),"category_catalog":{"schema_version":"1.0.0","categories":[{"category_key":"forklifts"}]},"category_matrix":{"schema_version":"1.0.0","mappings":[{"mapping_id":"map-1","source_category_key":"forklifts","mapping_status":mapping,"target_category_key":"forklifts","primary":True}]},"asset_decisions":{"synthetic-1":{"media":["SYN/catalogo/forklifts/MODEL-1/imagenes/SYN-MODEL-1-1-principal.png"],"technical_sheet":None,"additional_documents":[]}},"upstream_fingerprints":{"identity":"a"*64,"extraction":"b"*64,"selection":"c"*64}}

class NumberNormalizationTests(unittest.TestCase):
 def test_exact_metric_value(self): self.assertEqual("3.000",parse_measure("3","m",numeric())["normalized_value"])
 def test_comma_decimal_with_declared_locale(self): self.assertEqual("1.500",parse_measure("1,5","m",numeric(decimal_separator=","))["normalized_value"])
 def test_ambiguous_decimal_requires_review(self): self.assertEqual("manual_approval_required",parse_measure("1.500","m",numeric(decimal_separator=None))["resolution_status"])
 def test_declared_thousands_separator(self): self.assertEqual("1500",parse_measure("1 500","kg",numeric(decimal_separator=",",thousands_separator=" ",target_unit="kg",scale=0))["normalized_value"])
 def test_exact_conversion_uses_decimal(self): self.assertEqual("0.300",parse_measure("300","mm",numeric())["normalized_value"])
 def test_declared_rounding(self): self.assertEqual("1.24",parse_measure("1.235","m",numeric(scale=2,rounding="ROUND_HALF_UP"))["normalized_value"])
 def test_unknown_unit_is_preserved(self):
  value=parse_measure("7","furlong",numeric()); self.assertEqual("unsupported",value["resolution_status"]); self.assertEqual("furlong",value["normalized_unit"])
 def test_missing_unit_is_not_invented(self): self.assertEqual("unit_missing",parse_measure("7",None,numeric())["reason"])
 def test_ranges_until_and_multiple_values_are_not_collapsed(self):
  for raw in ("1-2","hasta 2","1/2","≤2","≥1"):
   with self.subTest(raw=raw): self.assertIsNone(parse_measure(raw,"m",numeric())["normalized_value"])
 def test_absence_literals_never_become_zero(self):
  for raw in ("","-","—","N/A","n/a","no aplica","opcional","según configuración","a consultar"):
   with self.subTest(raw=raw): self.assertIsNone(parse_measure(raw,"m",numeric())["normalized_value"])

class RoutingAndProvenanceTests(unittest.TestCase):
 def test_working_height_routes_but_lift_height_does_not(self):
  p=bundle()["policy"]; self.assertEqual("WorkingHeightM",normalize_observation(observation(),p)["target_field"]); self.assertIsNone(normalize_observation(observation("lift_height","3000","mm"),p)["target_field"])
 def test_battery_capacity_is_not_load_capacity(self): self.assertIsNone(normalize_observation(observation("battery_capacity","200","Ah"),bundle()["policy"])["target_field"])
 def test_machine_weight_routes_and_battery_weight_does_not(self):
  p=bundle()["policy"]; self.assertEqual("MachineWeightKg",normalize_observation(observation("machine_weight","900","kg"),p)["target_field"]); self.assertIsNone(normalize_observation(observation("battery_weight","100","kg"),p)["target_field"])
 def test_power_alias_is_closed_and_voltage_does_not_infer_power(self):
  p=bundle()["policy"]; self.assertEqual("electric_lithium",normalize_observation(observation("power_source","lithium electric",None),p)["normalized_value"]); self.assertIsNone(normalize_observation(observation("battery_voltage","24","V"),p)["target_field"])
 def test_unknown_power_and_terrain_remain_unsupported(self):
  value=normalize_observation(observation("power_source","hydrogen",None),bundle()["policy"]); self.assertEqual("unsupported",value["resolution_status"])
 def test_year_hours_snapshot_are_never_derived(self):
  result=build_plan(bundle()); self.assertNotIn("Year",result["products"][0]["structured_fields"]); self.assertNotIn("HoursMeter",result["products"][0]["structured_fields"])
 def test_raw_qualifiers_and_evidence_are_preserved(self):
  source=observation("lift_height","3000","mm"); source["qualifiers"]=["mast duplex"]; result=build_plan(bundle([source])); spec=result["product_specs"][0]; self.assertEqual(["mast duplex"],spec["qualifiers"]); self.assertEqual(["e-1"],spec["evidence_references"])
 def test_equal_ep_gam_deduplicates_conclusion_not_evidence(self):
  first=observation(); second=observation(source="gam"); second["evidence_references"]=["e-2"]; result=build_plan(bundle([first,second])); self.assertEqual(1,len(result["observations"])); self.assertEqual(["e-1","e-2"],result["observations"][0]["evidence_references"])
 def test_ep_gam_and_official_conflicts_remain_visible(self):
  for source in ("gam","ep_pdf"):
   second=observation(raw="4",source=source); second["evidence_references"]=["e-2"]; result=build_plan(bundle([observation(),second])); self.assertEqual(1,len(result["conflicts"])); self.assertEqual("conflict_blocked",result["products"][0]["readiness"])

class ProductCategoryAndGapTests(unittest.TestCase):
 def test_productspec_order_is_deterministic(self):
  result=build_plan(bundle([observation("zeta","z",None),observation("alpha","a",None)])); self.assertEqual(["alpha","zeta"],[x["canonical_key"] for x in result["products"][0]["product_specs"]])
 def test_approved_mapping_and_proposed_mapping_readiness(self):
  self.assertEqual("normalized_ready_for_audit",build_plan(bundle())["products"][0]["readiness"]); self.assertEqual("category_mapping_required",build_plan(bundle(mapping="proposed"))["products"][0]["readiness"])
 def test_missing_target_and_multiple_primary_are_blocking(self):
  value=bundle(); value["category_catalog"]["categories"]=[]; self.assertEqual("category_mapping_required",build_plan(value)["products"][0]["readiness"])
  value=bundle(); value["category_matrix"]["mappings"].append(dict(value["category_matrix"]["mappings"][0],mapping_id="map-2")); self.assertEqual("category_mapping_required",build_plan(value)["products"][0]["readiness"])
 def test_unmapped_battery_energy_airport_categories_remain_pending(self):
  for category in ("batteries","ep-energy","airport-equipment"):
   value=bundle(); value["products"][0]["source_category_keys"]=[category]; self.assertEqual("category_mapping_required",build_plan(value)["products"][0]["readiness"])
 def test_lift_and_battery_gaps_are_proposals_only(self):
  values=[observation("lift_height","3000","mm"),observation("battery_capacity","200","Ah")]; result=build_plan(bundle(values)); self.assertEqual(["BatteryCapacityAh","MaximumLiftHeightMm"],[x["concept"] for x in result["schema_gaps"]]); self.assertTrue(all(x["provisional_destination"]=="ProductSpec" for x in result["schema_gaps"]))
 def test_producto_is_audit_only_and_commercial_defaults_are_safe(self):
  product=build_plan(bundle())["products"][0]; self.assertEqual("normalized_for_audit_not_api_payload",product["document_kind"]); self.assertEqual({"is_published":False,"price_visible":False,"is_featured":False,"price":None,"supplier":None,"condition":None,"stock_status":None,"commercial_text":None},product["commercial"])
 def test_selected_assets_are_consumed_without_reselection(self): self.assertIn("principal.png",build_plan(bundle())["products"][0]["media"][0])

class GatesMaterializationAndCliTests(unittest.TestCase):
 def test_live_unverified_is_blocked_but_fixture_is_scoped(self):
  value=bundle(); validate_inputs(value); value["fixture_only"]=False
  with self.assertRaises(NormalizationError): validate_inputs(value)
 def test_duplicate_unknown_and_policy_mismatch_fail_closed(self):
  for mutation in ("duplicate","orphan","policy"):
   value=bundle()
   if mutation=="duplicate": value["products"].append(copy.deepcopy(value["products"][0]))
   elif mutation=="orphan": value["observations"][0]["canonical_identity"]="unknown"
   else: value["policy"]["fingerprint"]="0"*64
   with self.subTest(mutation=mutation),self.assertRaises(NormalizationError): validate_inputs(value)
 def test_plan_and_timestamp_independent_fingerprint_are_deterministic(self):
  first=build_plan(bundle()); value=bundle(); value["created_at"]="2099-01-01T00:00:00Z"; second=build_plan(value); self.assertEqual(first["fingerprint"],second["fingerprint"])
 def test_atomic_idempotent_and_tamper_extra_missing_detection(self):
  plan=build_plan(bundle())
  with tempfile.TemporaryDirectory() as directory:
   target=pathlib.Path(directory)/"run"; self.assertEqual("completed",normalize_to(plan,plan["fingerprint"],target)["state"]); self.assertEqual("already_complete",normalize_to(plan,plan["fingerprint"],target)["state"])
   product=next(target.glob("products/*/producto.json")); product.write_text("altered",encoding="utf-8"); self.assertFalse(verify_output(target)["valid"])
 def test_wrong_plan_fingerprint_is_rejected(self):
  with tempfile.TemporaryDirectory() as directory,self.assertRaises(NormalizationError): normalize_to(build_plan(bundle()),"0"*64,pathlib.Path(directory)/"run")
 def test_cli_has_only_offline_commands_and_no_bypass(self):
  text=(ROOT/"catalog_normalize.py").read_text(encoding="utf-8"); self.assertIn('"plan"',text); self.assertIn('"normalize"',text); self.assertIn('"verify"',text)
  for forbidden in ("--force","--overwrite","--skip-validation","--allow-unverified","--ignore-reviews","--publish","--apply","--approve","requests","urllib","socket","subprocess"):
   with self.subTest(forbidden=forbidden): self.assertNotIn(forbidden,text)
