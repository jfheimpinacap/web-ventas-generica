"""Pruebas sintéticas enfocadas; no usan red, backend ni paquetes reales."""

import csv
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).parents[1] / "import_lgmg_scissors_minimal.py"
SPEC = importlib.util.spec_from_file_location("minimal_importer", MODULE_PATH)
minimal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(minimal)


def jpeg_bytes(seed):
    return b"\xff\xd8\xff" + seed.encode() + b"\xff\xd9"


class FakeClient:
    states = None

    def __init__(self, origin, token, apply=False):
        self.origin, self.apply, self.methods = origin, apply, []
        self.state = json.loads(json.dumps(self.states))
        self.posts = []

    def get_json(self, path):
        self.methods.append("GET")
        names = {"/api/categories?include_inactive=true": "categories",
                 "/api/brands?include_inactive=true": "brands",
                 "/api/products?include_unpublished=true": "products",
                 "/api/product-images": "images"}
        return self.state[names[path]]

    def post_json(self, path, payload):
        self.methods.append("POST"); self.posts.append((path, payload))
        product = {**payload, "id": len(self.state["products"]) + 100,
                   "brand": {"id": payload["brand"]}, "category": {"id": payload["category"]}, "images": []}
        self.state["products"].append(product)
        return product

    def post_image(self, product_id, image):
        self.methods.append("POST"); self.posts.append(("/api/product-images", product_id, image["proposed_alt"]))
        item = {"id": len(self.state["images"]) + 1, "product": product_id, "is_main": True}
        self.state["images"].append(item)
        return item


class MinimalImporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name); self.plan = self.root / "plan"; self.media = self.root / "media"
        self.plan.mkdir(); self.media.mkdir()
        self.product_rows = []
        self.image_rows = []
        for index, (model, key) in enumerate(minimal.MODEL_SOURCE_KEYS):
            self.product_rows.append({"metric_model": model, "source_key": key, "proposed_name": f"LGMG {model}",
                "source_category": "Elevadores de Tijera", "target_subcategory": "Elevadores tipo tijera eléctricos",
                "target_brand": "LGMG", "product_type": "machinery", "condition": "new", "stock_status": "on_request"})
            physical = index if index < 20 else 19
            relative = f"media-package/images/{physical}.jpg"; path = self.media / relative
            path.parent.mkdir(parents=True, exist_ok=True); data = jpeg_bytes(str(physical)); path.write_bytes(data)
            self.image_rows.append({"source_key": key, "image_order": "1", "primary_candidate": "true",
                "local_file": relative, "size_bytes": str(len(data)), "sha256": hashlib.sha256(data).hexdigest(),
                "mime_type": "image/jpeg", "proposed_alt": f"LGMG {model}"})
        self.write_csv(self.plan / "import-products.csv", self.product_rows)
        self.write_csv(self.media / "import-images.csv", self.image_rows)
        self.state = {"categories": [
            {"id": 1, "name": "Maquinaria", "slug": "maquinaria", "product_type": "machinery", "is_active": True, "parent": None},
            {"id": 2, "name": "Elevadores tipo tijera eléctricos", "slug": "elevadores-tipo-tijera-electricos",
             "product_type": "machinery", "is_active": True, "parent": 1}],
            "brands": [{"id": 3, "name": "LGMG", "slug": "lgmg", "is_active": True}], "products": [], "images": []}

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_csv(path, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, rows[0].keys()); writer.writeheader(); writer.writerows(rows)

    def test_cli_double_confirmation_and_no_publish_option(self):
        parser = minimal.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])
        options = {action.dest for action in parser._actions}
        self.assertEqual(options, {"help", "plan_input", "media_input", "api_base_url", "output_dir", "apply", "confirm_minimal_import"})
        args = ["--plan-input", "p", "--media-input", "m", "--api-base-url", "http://localhost:5000", "--output-dir", "o", "--apply"]
        with mock.patch.object(minimal, "access_token", side_effect=AssertionError("token must not be read")):
            self.assertEqual(minimal.main(args), 3)

    def test_closed_models_order_and_plan_rejections(self):
        rows, _ = minimal.validate_plan(self.plan)
        self.assertEqual(tuple(row["metric_model"] for row in rows), minimal.MODELS)
        self.assertEqual(len(rows), 21)
        for mutation in ("missing", "additional", "duplicate", "order", "other_family"):
            altered = list(self.product_rows)
            if mutation == "missing": altered.pop()
            elif mutation == "additional": altered.append(dict(altered[-1], metric_model="AR20JE", source_key="other"))
            elif mutation == "duplicate": altered[-1] = altered[0]
            elif mutation == "order": altered[0], altered[1] = altered[1], altered[0]
            else: altered[0] = dict(altered[0], source_category="Plataformas de Brazo")
            self.write_csv(self.plan / "import-products.csv", altered)
            with self.assertRaises(minimal.BlockingError, msg=mutation): minimal.validate_plan(self.plan)
            self.write_csv(self.plan / "import-products.csv", self.product_rows)

    def test_one_primary_each_and_twenty_unique_files(self):
        images, _ = minimal.validate_media(self.media)
        self.assertEqual(len(images), 21); self.assertEqual(len({i["path"] for i in images}), 20)
        rows = list(self.image_rows); rows[0] = dict(rows[0], image_order="2")
        self.write_csv(self.media / "import-images.csv", rows)
        with self.assertRaises(minimal.BlockingError): minimal.validate_media(self.media)

    def test_integrity_traversal_and_symlink(self):
        rows = list(self.image_rows); rows[0] = dict(rows[0], sha256="0" * 64)
        self.write_csv(self.media / "import-images.csv", rows)
        with self.assertRaises(minimal.BlockingError): minimal.validate_media(self.media)
        self.write_csv(self.media / "import-images.csv", self.image_rows)
        self.assertRaises(minimal.BlockingError, minimal.safe_media_file, self.media, "../escape.jpg")
        target = self.media / self.image_rows[0]["local_file"]
        link = target.with_name("link.jpg"); link.write_bytes(jpeg_bytes("synthetic-link"))
        ordinary_bytes = {path: path.read_bytes() for path in self.media.rglob("*") if path.is_file()}
        original_is_symlink = Path.is_symlink
        checked_paths = []
        output = self.root / "unexpected-output"
        FakeClient.states = self.state
        client = FakeClient("http://localhost:5000", "opaque")

        def controlled_is_symlink(path):
            checked_paths.append(path)
            if path == link:
                return True
            return original_is_symlink(path)

        with mock.patch.object(Path, "is_symlink", controlled_is_symlink):
            with self.assertRaises(minimal.BlockingError) as caught:
                minimal.safe_media_file(self.media, link.relative_to(self.media).as_posix())

        self.assertIn("Symlink prohibido", str(caught.exception))
        self.assertIn(link, checked_paths)
        self.assertEqual(ordinary_bytes, {path: path.read_bytes() for path in self.media.rglob("*") if path.is_file()})
        self.assertFalse(output.exists())
        self.assertEqual(client.methods, [])
        self.assertEqual(client.state["products"], [])
        self.assertEqual(client.state["images"], [])

    def test_local_origins_redirects_and_methods(self):
        for origin in ("http://localhost:5000", "http://127.0.0.1:5000/"):
            self.assertIn(minimal.normalize_origin(origin), ("http://localhost:5000", "http://127.0.0.1:5000"))
        for origin in ("https://localhost:5000", "http://example.com:5000", "http://localhost:5001", "http://u:p@localhost:5000", "http://localhost:5000?q=1"):
            self.assertRaises(minimal.BlockingError, minimal.normalize_origin, origin)
        client = minimal.LocalApiClient("http://localhost:5000", "secret", False)
        self.assertRaises(minimal.ImportErrorSafe, client.request, "POST", "/api/products", b"{}")
        self.assertRaises(minimal.ImportErrorSafe, client.request, "DELETE", "/api/products/1")
        handler = minimal.NoRedirect()
        self.assertRaises(minimal.ImportErrorSafe, handler.redirect_request, None, None, 302, "", {}, "http://127.0.0.1:5000/api/products")

    def test_token_only_from_environment_and_not_in_payload(self):
        self.assertEqual(minimal.access_token({minimal.TOKEN_ENV: "opaque"}), "opaque")
        self.assertRaises(minimal.BlockingError, minimal.access_token, {})
        payload = minimal.product_payload(self.product_rows[0], 2, 3)
        self.assertNotIn("token", json.dumps(payload).casefold())

    def test_exact_manual_preconditions_and_no_go(self):
        for slug in ("elevadores-tipo-tijera-electricos", "elevador-electrico"):
            with self.subTest(accepted_slug=slug):
                state = json.loads(json.dumps(self.state)); state["categories"][1]["slug"] = slug
                root, sub, brand = minimal.resolve_preconditions(state["categories"], state["brands"])
                self.assertEqual((root["id"], sub["id"], brand["id"]), (1, 2, 3))

        subcategory_mutations = {
            "historical_name": {"name": "Elevador eléctrico", "slug": "elevador-electrico"},
            "empty_slug": {"slug": ""},
            "arbitrary_slug": {"slug": "otro-slug"},
            "similar_name": {"name": "Elevadores tipo tijera eléctrico"},
            "missing_parent": {"parent": None},
            "wrong_parent": {"parent": 99},
            "inactive": {"is_active": False},
            "wrong_type": {"product_type": "spare_part"},
        }
        for case, mutation in subcategory_mutations.items():
            with self.subTest(rejected_subcategory=case):
                state = json.loads(json.dumps(self.state)); state["categories"][1].update(mutation)
                self.assertRaises(minimal.BlockingError, minimal.resolve_preconditions, state["categories"], state["brands"])

        for case, categories in (
            ("two_subcategories", self.state["categories"] + [dict(self.state["categories"][1], id=4, slug="elevador-electrico")]),
            ("missing_root", self.state["categories"][1:]),
            ("ambiguous_root", [self.state["categories"][0], dict(self.state["categories"][0], id=4)] + self.state["categories"][1:]),
        ):
            with self.subTest(rejected_categories=case):
                self.assertRaises(minimal.BlockingError, minimal.resolve_preconditions, categories, self.state["brands"])

        for case, brands in (
            ("missing_brand", []),
            ("inactive_brand", [dict(self.state["brands"][0], is_active=False)]),
            ("ambiguous_brand", self.state["brands"] + [dict(self.state["brands"][0], id=4)]),
        ):
            with self.subTest(rejected_brand=case):
                self.assertRaises(minimal.BlockingError, minimal.resolve_preconditions, self.state["categories"], brands)

    def test_minimal_unpublished_payload(self):
        payload = minimal.product_payload(self.product_rows[0], 2, 3)
        self.assertFalse(payload["is_published"]); self.assertFalse(payload["price_visible"])
        self.assertIsNone(payload["technical_sheet"]); self.assertIsNone(payload["price"])
        self.assertEqual(payload["description"], "")
        self.assertFalse(payload["includes_technical_review"])
        forbidden = {"specifications", "specs", "datasheet", "publish"}
        self.assertTrue(forbidden.isdisjoint(payload))

    def test_existing_detection_conflicts_and_idempotence(self):
        row = self.product_rows[0]
        product = {"id": 8, "name": row["proposed_name"], "model": row["metric_model"],
                   "brand": {"id": 3}, "category": {"id": 2}, "is_published": False}
        decision = minimal.classify_products([row], [product], [], 2, 3)[0]
        self.assertEqual(decision["action"], "upload_image_only")
        self.assertEqual(minimal.classify_products([row], [product], [{"product": 8}], 2, 3)[0]["action"], "already_present")
        conflict = dict(product, name="Nombre incompatible")
        self.assertEqual(minimal.classify_products([row], [conflict], [], 2, 3)[0]["action"], "conflict")

    def test_dry_run_get_only_apply_multipart_and_unicode_manifest(self):
        FakeClient.states = self.state
        out = self.root / "dry"
        code = minimal.run(self.plan, self.media, "http://localhost:5000", out, False, "opaque", FakeClient)
        self.assertEqual(code, 0)
        manifest = json.loads((out / "minimal-import-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mode"], "dry_run")
        self.assertEqual(manifest["http_methods_used"], ["GET"]); self.assertFalse(manifest["content_published"])
        self.assertEqual(manifest["products_created"], 0); self.assertEqual(manifest["images_uploaded"], 0)
        self.assertEqual(manifest["version"], "1.0.1")
        self.assertIn("S0607EⅡ", (out / "minimal-import-manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("opaque", "".join(p.read_text(encoding="utf-8-sig") for p in out.iterdir()))
        FakeClient.states = self.state
        applied = self.root / "apply"
        self.assertEqual(minimal.run(self.plan, self.media, "http://127.0.0.1:5000", applied, True, "opaque", FakeClient), 0)
        applied_manifest = json.loads((applied / "minimal-import-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(applied_manifest["products_created"], 21); self.assertEqual(applied_manifest["images_uploaded"], 21)
        self.assertEqual(applied_manifest["categories_created"], 0); self.assertFalse(applied_manifest["credentials_persisted"])


if __name__ == "__main__":
    unittest.main()
