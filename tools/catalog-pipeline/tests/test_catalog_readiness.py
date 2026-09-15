import copy
import json
import pathlib
import tempfile
import unittest

from catalog_pipeline_common.serialization import canonical_bytes
from catalog_readiness import main
from jem_nexus_import.readiness import assess, contract_fingerprint
from jem_nexus_import.snapshot import READ_TARGETS, semantic_fingerprint
from catalog_acquisition.schema_validation import validate

ROOT = pathlib.Path(__file__).parents[1]


def contract(): return json.loads((ROOT / "schemas/v1/jem-nexus-contract.json").read_text(encoding="utf-8"))


def snapshot(observable=False):
    c = contract()
    binary = {"sha256":"a" * 64, "bytes":"c3ludGhldGlj"} if observable else {}
    value = {"schema_version":"1.0.0", "complete":True, "classification":"fixture_only",
             "contract_fingerprint":contract_fingerprint(c), "collections":{
        "categories":[{"id":41,"name":"Maquinarias","slug":"maquinaria","parent_id":None,"product_type":"machinery"},
                      {"id":2,"name":"Plataformas","slug":"plataformas","parent_id":41,"product_type":"machinery"}],
        "brands":[{"id":3,"name":"Marca sintética","slug":"marca-sintetica"}],
        "suppliers":[{"id":4,"name":"Proveedor sintético"}],
        "products":[{"id":5,"name":"Equipo sintético","slug":"equipo-sintetico","category_id":2,"brand_id":3,"supplier_id":4,"technical_sheet_id":8,"relations_complete":True,"model":"S1","sku":None,"product_type":"machinery","condition":"used","short_description":"s","description":"d","working_height_m":1.0,"terrain_type":None,"year":None,"hours_meter":0,"maximum_load_capacity_kg":None,"machine_weight_kg":2.0,"power_source":"diesel","includes_technical_review":True,"includes_commercial_technical_advice":True,"includes_coordinated_delivery":True,"price":None,"price_currency":"CLP","price_tax_mode":"plus_vat","price_visible":False,"stock_status":"available","is_featured":False,"is_published":False,"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}],
        "product_images":[{"id":6,"product_id":5,"image":"/media/synthetic.png","file_url":"/api/product-images/6/file","alt_text":"Sintética","is_main":True,"order":0,**binary}],
        "product_specs":[{"id":7,"product_id":5,"key":"altura","value":"1","unit":"m","order":0}],
        "technical_sheets":[{"id":8,"name":"Ficha sintética","original_file_name":"synthetic.pdf","content_type":"application/pdf","size_bytes":9,"file_url":"/api/technical-sheets/8/file",**binary}]},
             "endpoints":[{"collection":name,"path":target,"status":200,"mime":"application/json","response_sha256":"a"*64,"pages_received":1,"pages_expected":1,"complete":True} for name,target in READ_TARGETS.items()]}
    value["semantic_fingerprint"] = semantic_fingerprint(value)
    return value


class ReadinessTests(unittest.TestCase):
    def report(self, value=None): return assess(value or snapshot(), contract())

    def test_01_real_shape_is_manual_for_binary_evidence(self): self.assertEqual("read_compatible_manual_binary_verification", self.report()["result"])
    def test_02_observable_binary_is_compatible(self): self.assertEqual("read_compatible", self.report(snapshot(True))["result"])
    def test_03_snapshot_is_not_modified(self):
        value = snapshot(); before = copy.deepcopy(value); self.report(value); self.assertEqual(before, value)
    def test_04_report_fingerprint_is_deterministic(self): self.assertEqual(self.report()["report_fingerprint"], self.report()["report_fingerprint"])
    def test_05_same_input_produces_same_bytes(self): self.assertEqual(canonical_bytes(self.report()), canonical_bytes(self.report()))
    def test_06_missing_root_blocks(self):
        value=snapshot(); value["collections"]["categories"]=value["collections"]["categories"][1:]; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ROOT_CATEGORY_MISSING", [x["code"] for x in self.report(value)["blockers"]])
    def test_07_ambiguous_root_blocks(self):
        value=snapshot(); value["collections"]["categories"].append({"id":9,"name":"Otra","slug":"maquinaria","parent_id":None,"product_type":"machinery"}); value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ROOT_CATEGORY_AMBIGUOUS", [x["code"] for x in self.report(value)["blockers"]])
    def test_08_missing_collection_blocks(self):
        value=snapshot(); del value["collections"]["brands"]; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("COLLECTION_MISSING", [x["code"] for x in self.report(value)["blockers"]])
    def test_09_wrong_collection_type_blocks(self):
        value=snapshot(); value["collections"]["brands"]={}; self.assertIn("COLLECTION_TYPE_INVALID", [x["code"] for x in self.report(value)["blockers"]])
    def test_10_duplicate_id_blocks(self):
        value=snapshot(); value["collections"]["brands"].append(dict(value["collections"]["brands"][0])); value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("DUPLICATE_ID", [x["code"] for x in self.report(value)["blockers"]])
    def test_11_identity_collision_blocks(self):
        value=snapshot(); value["collections"]["brands"].append({"id":9,"name":"Otra","slug":"MARCA-SINTETICA"}); value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("IDENTITY_COLLISION", [x["code"] for x in self.report(value)["blockers"]])
    def test_12_orphan_product_category_blocks(self):
        value=snapshot(); value["collections"]["products"][0]["category_id"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_13_orphan_product_brand_blocks(self):
        value=snapshot(); value["collections"]["products"][0]["brand_id"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_14_orphan_image_blocks(self):
        value=snapshot(); value["collections"]["product_images"][0]["product_id"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_15_orphan_spec_blocks(self):
        value=snapshot(); value["collections"]["product_specs"][0]["product_id"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_16_orphan_sheet_blocks_when_observable(self):
        value=snapshot(); value["collections"]["products"][0]["technical_sheet_id"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_17_changed_snapshot_fingerprint_blocks(self):
        value=snapshot(); value["collections"]["brands"][0]["name"]="Changed"; self.assertIn("SNAPSHOT_FINGERPRINT_MISMATCH", [x["code"] for x in self.report(value)["blockers"]])
    def test_18_contract_fingerprint_mismatch_blocks(self):
        value=snapshot(); value["contract_fingerprint"]="0"*64; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("CONTRACT_FINGERPRINT_MISMATCH", [x["code"] for x in self.report(value)["blockers"]])
    def test_19_missing_required_dto_field_blocks(self):
        value=snapshot(); del value["collections"]["products"][0]["name"]; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("DTO_FIELD_MISSING", [x["code"] for x in self.report(value)["blockers"]])
    def test_20_wrong_required_dto_type_blocks(self):
        value=snapshot(); value["collections"]["products"][0]["id"]="5"; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("DTO_FIELD_TYPE_INVALID", [x["code"] for x in self.report(value)["blockers"]])
    def test_21_cli_manual_returns_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); (root/"snapshot.json").write_bytes(canonical_bytes(snapshot())); self.assertEqual(0,main(["assess","--snapshot",str(root/"snapshot.json"),"--contract",str(ROOT/"schemas/v1/jem-nexus-contract.json"),"--output-dir",str(root/"out")]))
    def test_22_cli_incompatible_returns_three(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); value=snapshot(); value["collections"].pop("brands"); value["semantic_fingerprint"]=semantic_fingerprint(value); (root/"snapshot.json").write_bytes(canonical_bytes(value)); self.assertEqual(3,main(["assess","--snapshot",str(root/"snapshot.json"),"--contract",str(ROOT/"schemas/v1/jem-nexus-contract.json"),"--output-dir",str(root/"out")]))
    def test_23_outputs_are_idempotent_and_divergence_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); path=root/"snapshot.json"; path.write_bytes(canonical_bytes(snapshot())); args=["assess","--snapshot",str(path),"--contract",str(ROOT/"schemas/v1/jem-nexus-contract.json"),"--output-dir",str(root/"out")]; self.assertEqual((0,0),(main(args),main(args))); value=snapshot(True); path.write_bytes(canonical_bytes(value)); self.assertEqual(4,main(args))
    def test_24_report_excludes_credentials_and_resource_bodies(self):
        text=canonical_bytes(self.report()).decode("utf-8").casefold(); self.assertNotIn("authorization",text); self.assertNotIn("token",text); self.assertNotIn("cookie",text); self.assertNotIn("equipo sintético".casefold(),text)
    def test_25_assessor_has_no_network_or_mutation_import_and_importer_has_six_commands(self):
        source=(ROOT/"jem_nexus_import/readiness.py").read_text(encoding="utf-8"); cli=(ROOT/"catalog_readiness.py").read_text(encoding="utf-8"); importer=(ROOT/"catalog_import.py").read_text(encoding="utf-8"); self.assertFalse(any(word in source+cli for word in ("import urllib","import socket","jem_nexus_local_transport","jem_nexus_local_mutation_transport"))); self.assertTrue(all(name in importer for name in ('"snapshot-local"','"plan"','"dry-run"','"apply-local"','"resume-local"','"verify-local"'))); self.assertNotIn('add_parser("assess")',importer)

    def test_26_contract_declares_canonical_root_metadata(self):
        self.assertEqual({"collection":"categories", "identity_field":"slug", "identity":"maquinaria",
                          "parent_field":"parent_id", "product_type":"machinery"}, contract()["local_readiness"]["root_category"])

    def test_27_plural_slug_does_not_satisfy_contract(self):
        value=snapshot(); value["collections"]["categories"][0]["slug"]="maquinarias"; value["semantic_fingerprint"]=semantic_fingerprint(value)
        self.assertIn("ROOT_CATEGORY_MISSING", [x["code"] for x in self.report(value)["blockers"]])

    def test_28_invalid_root_shapes_fail_closed(self):
        for field, invalid in (("parent_id", 9), ("id", None), ("id", True), ("id", "41"), ("product_type", "service")):
            with self.subTest(field=field, invalid=invalid):
                value=snapshot(); value["collections"]["categories"][0][field]=invalid; before=copy.deepcopy(value); fingerprint=semantic_fingerprint(value)
                self.assertEqual(before,value); value["semantic_fingerprint"]=fingerprint
                self.assertIn("ROOT_CATEGORY_INVALID", [x["code"] for x in self.report(value)["blockers"]])

    def test_29_root_selection_is_order_independent_and_ignores_other_types(self):
        value=snapshot(); value["collections"]["categories"][:0]=[
            {"id":31,"name":"Servicios","slug":"servicios","parent_id":None,"product_type":"service"},
            {"id":32,"name":"Repuestos","slug":"repuestos","parent_id":None,"product_type":"spare_part"}]
        value["semantic_fingerprint"]=semantic_fingerprint(value); first=self.report(value)
        value["collections"]["categories"].reverse(); value["semantic_fingerprint"]=semantic_fingerprint(value); second=self.report(value)
        self.assertTrue(first["root_category"]["valid"]); self.assertEqual(first["root_category"],second["root_category"])

    def test_30_contract_change_invalidates_old_snapshot_fingerprint(self):
        value=snapshot(); old=copy.deepcopy(contract()); old["local_readiness"]["root_category"]["identity"]="maquinarias"
        value["contract_fingerprint"]=contract_fingerprint(old); value["semantic_fingerprint"]=semantic_fingerprint(value)
        self.assertNotEqual(contract_fingerprint(old),contract_fingerprint(contract()))
        self.assertIn("CONTRACT_FINGERPRINT_MISMATCH", [x["code"] for x in self.report(value)["blockers"]])

    def test_31_valid_root_removes_false_missing_but_preserves_binary_warning_and_zero_mutation(self):
        report=self.report(); self.assertNotIn("ROOT_CATEGORY_MISSING", [x["code"] for x in report["blockers"]])
        self.assertIn("BINARY_CONTENT_NOT_OBSERVABLE", [x["code"] for x in report["warnings"]])
        self.assertEqual({"assessment_network_requests":0,"mutation_requests":0,"resources_created":0,"resources_updated":0,
                          "resources_deleted":0,"content_published":False,"mutation_authorized":False},report["zero_mutation_manifest"])

    def test_32_v2_report_validates_schema_and_nullable_managed_fields_remain_required(self):
        report=self.report(); self.assertEqual("jem-local-readiness-v2",report["rules_version"])
        validate(report,ROOT/"schemas/v1/local-readiness-report.schema.json")
        value=snapshot(); del value["collections"]["products"][0]["technical_sheet_id"]; value["semantic_fingerprint"]=semantic_fingerprint(value)
        self.assertIn("DTO_FIELD_MISSING", [item["code"] for item in self.report(value)["blockers"]])

    def test_33_bool_is_neither_integer_nor_number_and_dto_aliases_are_not_accepted(self):
        for field in ("year","working_height_m"):
            value=snapshot(); value["collections"]["products"][0][field]=True; value["semantic_fingerprint"]=semantic_fingerprint(value)
            self.assertIn("DTO_FIELD_TYPE_INVALID",[item["code"] for item in self.report(value)["blockers"]])
        value=snapshot(); product=value["collections"]["products"][0]; product["category"]={"id":product.pop("category_id")}; value["semantic_fingerprint"]=semantic_fingerprint(value)
        self.assertIn("DTO_FIELD_MISSING",[item["code"] for item in self.report(value)["blockers"]])


if __name__ == "__main__": unittest.main()
