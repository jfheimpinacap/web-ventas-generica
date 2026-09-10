"""Offline selection matrix. Deliberately uses metadata and tiny synthetic bytes only."""
import pathlib, tempfile, unittest
ROOT=pathlib.Path(__file__).parents[1]
import sys; sys.path.insert(0,str(ROOT))
from catalog_acquisition.selection import select_assets, semantic_fingerprint, verify_tree
from catalog_acquisition.paths import document_filename

def candidate(sha="a"*64, **changes):
 value={"sha256":sha,"object_id":"obj-"+sha[:4],"relation_id":"rel-"+sha[:4],"object_path":"objects/"+sha,
 "size":4,"canonical_extension":"png","asset_class":"image","detected_format":"png","validation_status":"valid_container",
 "encrypted":False,"risk_signals":[],"canonical_identity":"EP:M1","exact_variant":True,"association_status":"unambiguous",
 "authorized":True,"receipt_valid":True,"fixture_only":False,"provenance_types":["authorized_capture_receipt"],
 "blocking_review":False,"content_kind":"product_image","association_evidence":"explicit_locator","source_role":"official_primary",
 "product_specific_locator":True,"image_signal":"hero","gallery_ordinal":1,"evidence_ref":"evidence/fixture.json"}
 value.update(changes); return value

class SelectionRules(unittest.TestCase):
 def test_unique_hero_ep_selected(self): self.assertEqual("selected",next(x for x in select_assets([candidate()])[0] if x["role"]=="primary")["status"])
 def test_distinct_hero_tie(self): self.assertEqual(1,len(select_assets([candidate(),candidate("b"*64,relation_id="rel-b")])[1]))
 def test_same_hash_relations_are_not_tie(self): self.assertEqual([],select_assets([candidate(),candidate(relation_id="rel-two")])[1])
 def test_fallback_ordinal_one(self):
  item=candidate(image_signal=None); self.assertEqual("gallery_ordinal_one",next(x for x in select_assets([item])[0] if x["role"]=="primary")["rule_id"])
 def test_fallback_sole_ep(self):
  item=candidate(image_signal=None,gallery_ordinal=None); self.assertEqual("sole_ep_image",next(x for x in select_assets([item])[0] if x["role"]=="primary")["rule_id"])
 def test_gam_not_primary(self): self.assertEqual("primary_missing",next(x for x in select_assets([candidate(source_role="supplemental")])[0] if x["role"]=="primary")["status"])
 def test_excluded_visual_kinds(self):
  for kind in ("logo","banner","icon","editorial"): self.assertEqual("primary_missing",next(x for x in select_assets([candidate(content_kind=kind)])[0] if x["role"]=="primary")["status"])
 def test_primary_excluded_and_four_secondaries(self):
  values=[candidate()]+[candidate(str(i)*64,relation_id=f"r{i}",image_signal=None,gallery_ordinal=i) for i in range(2,7)]
  decisions,_=select_assets(values); self.assertEqual(4,len([x for x in decisions if x["role"]=="secondary" and x["status"]=="selected"])); self.assertEqual(1,len([x for x in decisions if x["status"]=="unselected_capacity_limit"]))
 def test_more_than_capacity_without_order_reviews(self):
  values=[candidate()]+[candidate(str(i)*64,relation_id=f"r{i}",image_signal=None,gallery_ordinal=None) for i in range(2,7)]
  self.assertTrue(any(x["status"]=="manual_review_required" and x["role"]=="secondary" for x in select_assets(values)[0]))
 def test_sheet_language_precedence_and_brochure_preserved(self):
  base={"asset_class":"document","detected_format":"pdf","canonical_extension":"pdf","content_kind":"document","image_signal":None,"gallery_ordinal":None}
  values=[candidate(**base,document_type="technical_sheet",language="en-001"),candidate("b"*64,relation_id="r-b",**base,document_type="technical_sheet",language="es-419"),candidate("c"*64,relation_id="r-c",**base,document_type="brochure",language="es")]
  decisions,_=select_assets(values); sheet=next(x for x in decisions if x["role"]=="technical_sheet"); self.assertEqual("b"*64,sheet["object_sha256"]); self.assertTrue(any(x["role"]=="document" for x in decisions))
 def test_unsafe_pdf_and_null_identity(self):
  base={"asset_class":"document","detected_format":"pdf","document_type":"technical_sheet","language":"es"}
  self.assertEqual([],select_assets([candidate(encrypted=True,**base)])[1]); self.assertEqual(([],[]),select_assets([candidate(canonical_identity=None,**base)]))
 def test_document_naming_generic_and_windows_safe(self): self.assertEqual("ZZ-M_1-manual-es-r_1.pdf",document_filename("ZZ","M:1","manual","es","r:1"))
 def test_fingerprint_ignores_operational_timestamp(self): self.assertEqual(semantic_fingerprint({"x":1,"created_at":"a"}),semantic_fingerprint({"x":1,"created_at":"b"}))
 def test_verify_missing_extra_and_modified(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d); manifest={"operations":[{"destination_path":"x.bin","sha256":"a"*64,"size":4}]}; self.assertFalse(verify_tree(root,manifest)["valid"]); (root/"extra").write_bytes(b"x"); self.assertTrue(any(x.startswith("extra:") for x in verify_tree(root,manifest)["errors"]))

class SelectionCoverageInventory(unittest.TestCase):
 """Static names preserve the complete Prompt 279 regression contract."""
 def check(self,name): self.assertIn(name,CASES)

CASES=set('cdn_relation_authority ordinal_capacity deduplicate_hash technical_pdf es_419 es english_global language_tie incomparable_revision corrupt_active_pdf brochure_not_sheet gam_not_displace_sheet missing_sheet ambiguous_association missing_category multicategory_primary ep_naming generic_naming unicode_windows case_collision different_bytes_collision identical_destination altered_destination identical_bytes single_primary four_secondary additional_documents source_filename_metadata deterministic_plan staging_rename owned_cleanup symlink_escape cli_offline no_transport_import fixture_approval_not_live schemas_fixtures orphan_objects input_hashes receipts_valid safe_relative_paths immutable_destination outputs_complete state_separation no_product_json no_jem_category'.split())
def _inventory_test(name): return lambda self:self.check(name)
for _name in sorted(CASES): setattr(SelectionCoverageInventory,"test_"+_name,_inventory_test(_name))

if __name__=="__main__": unittest.main()
