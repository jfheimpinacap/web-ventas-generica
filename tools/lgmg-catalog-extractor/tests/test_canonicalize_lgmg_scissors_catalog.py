"""Pruebas sinteticas: nunca usan red ni backend real."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "canonicalize_lgmg_scissors_catalog.py"
SPEC = importlib.util.spec_from_file_location("canonicalizer", MODULE_PATH)
canonical = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(canonical)


def state(final=False):
    products = [{"id": 1, "name": "JLG sin tocar", "model": "JLG", "slug": "jlg",
                 "brand": {"id": 3}, "category": {"id": 2}, "is_published": False, "is_featured": False}]
    images = [{"id": 1, "product": 1, "is_main": True}]
    for row in canonical.CATALOG:
        products.append({"id": row["product_id"], "name": row["target_name"] if final else row["source_name"],
                         "model": row["target_model"] if final else row["source_model"],
                         "slug": f"slug-{row['product_id']}", "brand": {"id": 3}, "category": {"id": 2},
                         "is_published": False, "is_featured": False})
        images.append({"id": row["product_id"], "product": row["product_id"], "is_main": True})
    return {"categories": [{"id": 2, "name": "Elevadores tipo tijera eléctricos"}],
            "brands": [{"id": 3, "name": "LGMG"}], "products": products, "images": images}


class FakeClient:
    initial = None
    last = None
    fail_id = None

    def __init__(self, origin, token, apply=False):
        self.origin, self.apply, self.methods = origin, apply, []
        self.data = json.loads(json.dumps(self.initial)); self.patches = []
        FakeClient.last = self

    def get_json(self, path):
        self.methods.append("GET")
        key = {"/api/categories?include_inactive=true": "categories", "/api/brands?include_inactive=true": "brands",
               "/api/products?include_unpublished=true": "products", "/api/product-images": "images"}[path]
        return self.data[key]

    def patch_product(self, product_id, payload):
        self.methods.append("PATCH"); self.patches.append((product_id, dict(payload)))
        if product_id == self.fail_id: raise canonical.SafeError("fallo sintetico")
        product = next(p for p in self.data["products"] if p["id"] == product_id)
        product.update(payload); return product


class CanonicalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        FakeClient.fail_id = None

    def tearDown(self): self.temp.cleanup()

    def run_tool(self, data, apply=False, name="out"):
        FakeClient.initial = data
        code = canonical.run("http://localhost:5000", self.root / name, apply, apply, "opaque", FakeClient)
        return code, FakeClient.last

    def test_exact_closed_table_names_and_unicode_provenance(self):
        self.assertEqual([r["product_id"] for r in canonical.CATALOG], list(range(2, 23)))
        changed = [r for r in canonical.CATALOG if r["source_model"] != r["target_model"]]
        self.assertEqual((len(changed), len(canonical.CATALOG) - len(changed)), (12, 9))
        self.assertTrue(all(r["source_name"] == f"Elevador de tijera eléctrico LGMG {r['source_model']}" for r in canonical.CATALOG))
        self.assertTrue(all(r["target_name"] == f"Elevador tipo tijera eléctrico LGMG {r['target_model']}" for r in canonical.CATALOG))
        self.assertTrue(all("Ⅱ" in r["source_model"] and "Ⅱ" not in r["target_model"] for r in changed))

    def test_dry_run_get_only_reports_and_token_absent(self):
        code, client = self.run_tool(state())
        self.assertEqual(code, 0); self.assertEqual(set(client.methods), {"GET"}); self.assertEqual(client.patches, [])
        self.assertEqual(set(p.name for p in (self.root / "out").iterdir()), set(canonical.OUTPUT_NAMES))
        combined = "".join(p.read_text(encoding="utf-8-sig") for p in (self.root / "out").iterdir())
        self.assertNotIn("opaque", combined); self.assertIn("S0607EⅡ", combined)

    def test_apply_uses_only_get_patch_and_minimal_payload(self):
        before = state(); jlg = json.loads(json.dumps(before["products"][0]))
        code, client = self.run_tool(before, True)
        self.assertEqual(code, 0); self.assertEqual(len(client.patches), 21)
        self.assertEqual(set(client.methods), {"GET", "PATCH"})
        self.assertTrue(all(set(payload) == {"name", "model"} and "slug" not in payload for _, payload in client.patches))
        self.assertEqual(client.data["products"][0], jlg)

    def test_final_is_zero_patch_and_partial_resumes(self):
        code, client = self.run_tool(state(True), True, "final")
        self.assertEqual(code, 0); self.assertEqual(client.patches, [])
        partial = state()
        for row in canonical.CATALOG[:8]:
            next(p for p in partial["products"] if p["id"] == row["product_id"]).update(name=row["target_name"], model=row["target_model"])
        code, client = self.run_tool(partial, True, "partial")
        self.assertEqual(code, 0); self.assertEqual([i for i, _ in client.patches], list(range(10, 23)))

    def test_all_preflight_conflicts_block_every_write(self):
        mutations = []
        missing = state(); missing["products"] = [p for p in missing["products"] if p["id"] != 8]; mutations.append(missing)
        incompatible = state(); incompatible["products"][2]["name"] = "otro"; mutations.append(incompatible)
        published = state(); published["products"][2]["is_published"] = True; mutations.append(published)
        featured = state(); featured["products"][2]["is_featured"] = True; mutations.append(featured)
        no_image = state(); no_image["images"] = [i for i in no_image["images"] if i["product"] != 2]; mutations.append(no_image)
        bad_main = state(); next(i for i in bad_main["images"] if i["product"] == 2)["is_main"] = False; mutations.append(bad_main)
        for index, data in enumerate(mutations):
            with self.subTest(index=index):
                code, client = self.run_tool(data, True, f"blocked-{index}")
                self.assertEqual(code, 3); self.assertEqual(client.patches, []); self.assertEqual(set(client.methods), {"GET"})

    def test_patch_failure_stops_and_is_retriable(self):
        FakeClient.fail_id = 5
        code, client = self.run_tool(state(), True)
        self.assertEqual(code, 2); self.assertEqual([i for i, _ in client.patches], [2, 3, 4, 5])
        summary = json.loads((self.root / "out" / "canonicalization-summary.json").read_text())
        self.assertEqual(summary["updated_ids"], [2, 3, 4]); self.assertEqual(summary["failed_id"], 5)

    def test_origin_methods_redirect_and_environment_token(self):
        for bad in ("https://localhost:5000", "http://example.com:5000", "http://localhost:5001",
                    "http://u:p@localhost:5000", "http://localhost:5000?q=x", "http://localhost:5000/#x"):
            self.assertRaises(canonical.BlockingError, canonical.normalize_origin, bad)
        client = canonical.LocalApiClient("http://localhost:5000", "secret", False)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertRaises(canonical.SafeError, client.request, method, "/api/products/2", {})
        self.assertRaises(canonical.SafeError, canonical.NoRedirect().redirect_request, None, None, 302, "", {}, "http://example.com")
        self.assertEqual(canonical.access_token({canonical.TOKEN_ENV: "opaque"}), "opaque")
        self.assertRaises(canonical.BlockingError, canonical.access_token, {})


if __name__ == "__main__": unittest.main()
