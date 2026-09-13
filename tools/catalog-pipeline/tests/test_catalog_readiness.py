import copy
import json
import pathlib
import tempfile
import unittest

from catalog_pipeline_common.serialization import canonical_bytes
from catalog_readiness import main
from jem_nexus_import.readiness import assess, contract_fingerprint
from jem_nexus_import.snapshot import semantic_fingerprint

ROOT = pathlib.Path(__file__).parents[1]


def contract(): return json.loads((ROOT / "schemas/v1/jem-nexus-contract.json").read_text(encoding="utf-8"))


def snapshot(observable=False):
    c = contract()
    binary = {"sha256":"a" * 64, "bytes":"c3ludGhldGlj"} if observable else {}
    value = {"schema_version":"1.0.0", "complete":True, "classification":"fixture_only",
             "contract_fingerprint":contract_fingerprint(c), "collections":{
        "categories":[{"id":1,"name":"Maquinarias","slug":"maquinarias","parent":None,"product_type":"machinery"},
                      {"id":2,"name":"Plataformas","slug":"plataformas","parent":1,"product_type":"machinery"}],
        "brands":[{"id":3,"name":"Marca sintética","slug":"marca-sintetica"}],
        "suppliers":[{"id":4,"name":"Proveedor sintético"}],
        "products":[{"id":5,"name":"Equipo sintético","slug":"equipo-sintetico","category":{"id":2},"brand":{"id":3},"model":"S1","product_type":"machinery"}],
        "product_images":[{"id":6,"product":5,"image":"/media/synthetic.png","alt_text":"Sintética","is_main":True,"order":0,**binary}],
        "product_specs":[{"id":7,"product":5,"name":"altura","value":"1","unit":"m","order":0}],
        "technical_sheets":[{"id":8,"name":"Ficha sintética","original_file_name":"synthetic.pdf","content_type":"application/pdf","size_bytes":9,"file_url":"/technical-sheets/8/file",**binary}]},
             "endpoints":[]}
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
        value=snapshot(); value["collections"]["categories"].append({"id":9,"name":"Otra","slug":"maquinarias","parent":None,"product_type":"machinery"}); value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ROOT_CATEGORY_AMBIGUOUS", [x["code"] for x in self.report(value)["blockers"]])
    def test_08_missing_collection_blocks(self):
        value=snapshot(); del value["collections"]["brands"]; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("COLLECTION_MISSING", [x["code"] for x in self.report(value)["blockers"]])
    def test_09_wrong_collection_type_blocks(self):
        value=snapshot(); value["collections"]["brands"]={}; self.assertIn("COLLECTION_TYPE_INVALID", [x["code"] for x in self.report(value)["blockers"]])
    def test_10_duplicate_id_blocks(self):
        value=snapshot(); value["collections"]["brands"].append(dict(value["collections"]["brands"][0])); value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("DUPLICATE_ID", [x["code"] for x in self.report(value)["blockers"]])
    def test_11_identity_collision_blocks(self):
        value=snapshot(); value["collections"]["brands"].append({"id":9,"name":"Otra","slug":"MARCA-SINTETICA"}); value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("IDENTITY_COLLISION", [x["code"] for x in self.report(value)["blockers"]])
    def test_12_orphan_product_category_blocks(self):
        value=snapshot(); value["collections"]["products"][0]["category"]={"id":99}; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_13_orphan_product_brand_blocks(self):
        value=snapshot(); value["collections"]["products"][0]["brand"]={"id":99}; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_14_orphan_image_blocks(self):
        value=snapshot(); value["collections"]["product_images"][0]["product"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_15_orphan_spec_blocks(self):
        value=snapshot(); value["collections"]["product_specs"][0]["product"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
    def test_16_orphan_sheet_blocks_when_observable(self):
        value=snapshot(); value["collections"]["technical_sheets"][0]["product"]=99; value["semantic_fingerprint"]=semantic_fingerprint(value); self.assertIn("ORPHAN_RELATION", [x["code"] for x in self.report(value)["blockers"]])
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


if __name__ == "__main__": unittest.main()
