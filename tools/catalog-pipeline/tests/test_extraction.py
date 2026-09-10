import inspect, json, pathlib, sys, tempfile, unittest
ROOT=pathlib.Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from catalog_acquisition.extraction import compare_manifests
from catalog_acquisition.extraction_adapters import FixtureHtmlExtractionAdapter, PAGE_TYPES
from catalog_acquisition.paths import safe_join

META={"encoding":"utf-8","canonical_url":"https://fixtures.invalid/products/e20","requested_url":"https://fixtures.invalid/products/e20",
 "expected_page_type":"series","approved_hosts":["fixtures.invalid"]}

class ExtractionTests(unittest.TestCase):
 def parse(self,name="synthetic-pages.html",**metadata):
  body=(ROOT/'fixtures/extraction'/name).read_bytes()
  return FixtureHtmlExtractionAdapter().parse(body,META|metadata)
 def test_closed_page_classification_and_structure_fail_closed(self):
  self.assertEqual({"product","series","family","listing","document_landing","unknown","structure_changed","parse_failed"},set(PAGE_TYPES))
  self.assertEqual("structure_changed",self.parse("structure-changed.html")["page_type"])
  self.assertTrue(any(x["blocking"] for x in self.parse("empty.html",expected_page_type="product")["issues"]))
  listing=b'<body data-page-type="listing"></body>'
  self.assertTrue(any(x["code"]=="listing_received_as_product" for x in FixtureHtmlExtractionAdapter().parse(listing,META|{"expected_page_type":"product"})["issues"]))
 def test_raw_unicode_entities_unknown_duplicate_and_contradictory_values(self):
  value=self.parse(); fields=value["fields"]
  self.assertIn("montaña",fields[0]["raw_value"]); self.assertIn("ñ",fields[1]["raw_value"]); self.assertIn("1,5",fields[1]["raw_value"])
  table=value["tables"][0]; self.assertTrue(table["irregular"]); self.assertEqual(2,sum(c["raw_value"]=="Capacidad" for r in table["rows"] for c in r["cells"]))
  self.assertTrue(any(x["code"]=="ambiguous_merged_cell" for x in value["issues"]))
 def test_series_models_remain_separate_and_shared_value_is_not_duplicated(self):
  value=self.parse(); scopes=[c["model_scope"] for r in value["tables"][0]["rows"] for c in r["cells"] if c["model_scope"]]
  self.assertEqual({"E20-A","E20-B"},set(scopes)); self.assertEqual("series_shared",value["fields"][2]["scope"]["kind"])
 def test_json_ld_media_documents_and_external_host_are_passive(self):
  value=self.parse(); self.assertEqual(1,len(value["json_ld"])); self.assertTrue(any(x["code"]=="invalid_json_ld" for x in value["issues"]))
  self.assertEqual({"logo","banner","icon"},{x["relationship"] for x in value["media"] if x["scope_status"]=="rejected_audited"})
  self.assertTrue(any(x["scope_status"]=="pending_host_review" for x in value["media"])); self.assertEqual(4,len(value["documents"]))
 def test_supplemental_price_and_stock_are_preserved_for_orchestrator_exclusion(self):
  value=self.parse("synthetic-gam.html",expected_page_type="product"); self.assertEqual(["Precio","Stock","Título"],sorted(x["source_field_raw"] for x in value["fields"]))
 def test_invalid_utf8_is_structured_and_lift_height_never_maps_to_working_height(self):
  value=FixtureHtmlExtractionAdapter().parse(b'\xff',META); self.assertEqual("parse_failed",value["page_type"])
  self.assertNotIn("WorkingHeightM",json.dumps(self.parse(),ensure_ascii=False))
 def test_adapter_is_pure_and_transport_free(self):
  source=inspect.getsource(sys.modules[FixtureHtmlExtractionAdapter.__module__])
  for forbidden in ("http_transport","urllib.request","requests","socket","open(","Path(","eval("): self.assertNotIn(forbidden,source)
 def test_incremental_comparison_and_absence_semantics(self):
  base={"schema_version":"1.0.0","rules_version":"r","identity_strategy":"i","matching_fingerprint":"f","adapters":[],"output_hashes":{"raw-field-observations.jsonl":"a","media-candidates.jsonl":"a","document-candidates.jsonl":"a"}}
  same=compare_manifests(base,dict(base)); self.assertEqual(["unchanged"],same["classifications"])
  changed=json.loads(json.dumps(base)); changed["output_hashes"]["raw-field-observations.jsonl"]="b"
  self.assertIn("new_observation",compare_manifests(base,changed)["classifications"])
  incompatible=dict(base,rules_version="other"); self.assertEqual("comparison_blocked",compare_manifests(base,incompatible)["status"])
 def test_windows_safe_snapshot_references(self):
  with tempfile.TemporaryDirectory() as root:
   with self.assertRaises(Exception): safe_join(pathlib.Path(root),"../escape")
   with self.assertRaises(Exception): safe_join(pathlib.Path(root),"CON")
 def test_cli_has_only_offline_commands_and_utf8_io_is_explicit(self):
  source=(ROOT/'catalog_extract.py').read_text(encoding="utf-8")
  for command in ('"plan"','"extract"','"compare"'): self.assertIn(command,source)
  for forbidden in ('download','publish','http_transport','urllib.request'): self.assertNotIn(forbidden,source)
  extraction=(ROOT/'catalog_acquisition/extraction.py').read_text(encoding="utf-8")
  self.assertIn('encoding="utf-8"',extraction); self.assertIn("shutil.rmtree(staging)",extraction)

if __name__=='__main__': unittest.main()
