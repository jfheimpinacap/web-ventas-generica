from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from catalog_assets.cli import initial_files, main
from catalog_assets.ep_download import RESULT_FIELDS
from catalog_assets.ep_local_import import (DefinitiveRemoteError, EpLocalError, FORMAT_VERSION,
                                            MISSING_SHEETS, LocalTransport, load_assets,
                                            product_payload, validate_base_url)
from catalog_assets.paths import initialize

JPEG = b"\xff\xd8\xffsynthetic\xff\xd9"
PDF = b"%PDF-1.4\nsynthetic\n%%EOF\n"
BASE = "http://127.0.0.1:8000"


class FakeTransport:
    """Stateful, contract-shaped replacement for all six API collections."""
    def __init__(self, brand=True):
        self.calls = []
        self.fail = None
        self.next_id = 100
        self.categories = [{"id": 1, "slug": "maquinaria", "parent": None,
                            "product_type": "machinery", "is_active": True}]
        self.brands = ([{"id": 2, "name": "EP", "slug": "ep", "is_active": True}] if brand else [])
        self.products, self.images, self.sheets, self.specs, self.binaries = [], [], [], [], {}

    def _id(self):
        self.next_id += 1
        return self.next_id

    def request(self, method, endpoint, token, **kwargs):
        self.calls.append((method, endpoint, token, kwargs))
        if self.fail and method not in {"GET", "GET_BYTES"}:
            error, self.fail = self.fail, None
            raise error
        tables = {
            "/api/categories?include_inactive=true": self.categories,
            "/api/brands?include_inactive=true": self.brands,
            "/api/products?include_unpublished=true": self.products,
            "/api/product-images": self.images,
            "/api/technical-sheets/": self.sheets,
            "/api/product-specs": self.specs,
        }
        if method == "GET":
            return json.loads(json.dumps(tables[endpoint]))
        if method == "GET_BYTES":
            return self.binaries[endpoint]
        if endpoint == "/api/brands":
            row = {"id": self._id(), **kwargs["json_data"], "is_active": True}; self.brands.append(row); return row
        if endpoint == "/api/products":
            row = {"id": self._id(), "technical_sheet_id": None, **kwargs["json_data"]}; self.products.append(row); return row
        if endpoint == "/api/product-images":
            self.assert_image_contract(kwargs)
            path = kwargs["files"]["image"]; row = {"id": self._id(), "product": kwargs["data"]["product"],
                "image": f"/media/product-images/{path.name}", "file_url": "ignored", "alt_text": kwargs["data"]["alt_text"],
                "is_main": kwargs["data"]["is_main"], "order": kwargs["data"]["order"]}
            self.images.append(row); self.binaries[f"/api/product-images/{row['id']}/file"] = path.read_bytes(); return row
        if endpoint == "/api/technical-sheets/":
            path = kwargs["files"]["file"]; row = {"id": self._id(), "name": kwargs["data"]["name"],
                "original_file_name": path.name, "content_type": "application/pdf", "size_bytes": path.stat().st_size,
                "file_url": "ignored"}
            self.sheets.append(row); self.binaries[f"/api/technical-sheets/{row['id']}/file"] = path.read_bytes(); return row
        if method == "PATCH" and endpoint.startswith("/api/products/"):
            product = next(x for x in self.products if x["id"] == int(endpoint.rsplit("/", 1)[1]))
            product["technical_sheet_id"] = kwargs["json_data"]["technical_sheet"]; return product
        raise AssertionError((method, endpoint))

    @staticmethod
    def assert_image_contract(kwargs):
        if set(kwargs.get("files", {})) != {"image"} or set(kwargs.get("data", {})) != {"product", "alt_text", "is_main", "order"}:
            raise DefinitiveRemoteError("HTTP 400 detail=image is required.")
        if not isinstance(kwargs["data"]["product"], int):
            raise DefinitiveRemoteError("HTTP 400")


class CaptureOpener:
    def __init__(self): self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return request.full_url
            def read(self): return b'{"id":1}'
        return Response()


class EpLocalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name) / "Maquinas"
        initialize(self.root, initial_files())
        models = sorted(MISSING_SHEETS | {f"MODEL{i:02d}" for i in range(30)})
        rows = []
        for index, model in enumerate(models):
            image = self.root / "EP/Imagenes modelos EP" / f"EP-{index}.jpg"
            image.parent.mkdir(parents=True, exist_ok=True); image.write_bytes(JPEG[:-2] + str(index).encode() + JPEG[-2:])
            rows.append(self.row(model, "image", image))
            if model not in MISSING_SHEETS:
                sheet = self.root / "EP/fichas-tecnicas EP" / f"EP-{index}.pdf"
                sheet.parent.mkdir(parents=True, exist_ok=True); sheet.write_bytes(PDF[:-6] + str(index).encode() + PDF[-6:])
                rows.append(self.row(model, "technical_sheet", sheet))
        with (self.root / "_control/ep-download-results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS); writer.writeheader(); writer.writerows(rows)

    def tearDown(self): self.temp.cleanup()

    def row(self, model, kind, path):
        return {"source": "EP", "target_brand": "EP", "model": model, "asset_type": kind,
                "asset_url": "https://example.invalid", "page_url": "https://example.invalid",
                "path": path.relative_to(self.root).as_posix(), "bytes": str(path.stat().st_size),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "state": "DOWNLOADED", "detail": ""}

    def run_dry(self, transport):
        with patch.dict(os.environ, {"JEM_NEXUS_LOCAL_READ_TOKEN": "READ-SECRET"}, clear=True):
            self.assertEqual(0, main(["--root", str(self.root), "import-ep-local", "--dry-run", "--base-url", BASE], transport))
        return json.loads((self.root / "_control/ep-local-import/ep-local-import-plan.json").read_text())

    def run_apply(self, transport, fingerprint):
        with patch.dict(os.environ, {"JEM_NEXUS_LOCAL_MUTATION_TOKEN": "WRITE-SECRET"}, clear=True):
            return main(["--root", str(self.root), "import-ep-local", "--apply", "--base-url", BASE,
                         "--confirm-plan-fingerprint", fingerprint], transport)

    def test_assets_are_closed_35_35_30_5_and_paths_are_scoped(self):
        accepted, omitted = load_assets(self.root)
        self.assertEqual((65, 35, 30), (len(accepted), sum(x["type"] == "image" for x in accepted), sum(x["type"] == "technical_sheet" for x in accepted)))
        self.assertEqual(MISSING_SHEETS, {x["model"] for x in accepted if x["type"] == "image"} - {x["model"] for x in accepted if x["type"] == "technical_sheet"})
        self.assertEqual([], omitted); self.assertFalse(any("LGMG" in x["path"] or "JLG" in x["path"] for x in accepted))

    def test_strict_contract_parent_and_six_gets(self):
        fake = FakeTransport(); plan = self.run_dry(fake)
        self.assertEqual(FORMAT_VERSION, plan["format_version"])
        self.assertEqual(6, len(fake.calls)); self.assertTrue(all(x[0] == "GET" for x in fake.calls))
        self.assertEqual((35, 35, 30, 5), tuple(plan["counts"][x] for x in ("models", "images", "technical_sheets", "missing_sheets")))
        self.assertNotIn("READ-SECRET", json.dumps(plan)); self.assertIsNone(plan["category"]["parent"])

    def test_wrong_contract_is_rejected_before_mutation(self):
        fake = FakeTransport(); fake.categories[0]["parent_id"] = fake.categories[0].pop("parent")
        with self.assertRaisesRegex(EpLocalError, "parent"):
            self.run_dry(fake)
        self.assertTrue(all(call[0] == "GET" for call in fake.calls))

    def test_brand_creation_and_minimal_payload(self):
        plan = self.run_dry(FakeTransport(False))
        self.assertEqual("create", plan["brand"]["operation"])
        for op in plan["operations"]:
            self.assertEqual(f"EP {op['model']}", op["payload"]["name"])
            self.assertEqual(False, op["payload"]["is_published"])
            self.assertFalse({"description", "short_description", "price", "specs"} & op["payload"].keys())

    def test_full_apply_multipart_sequence_verify_and_idempotent_dry_run(self):
        fake = FakeTransport(False); plan = self.run_dry(fake); self.assertEqual(0, self.run_apply(fake, plan["fingerprint"]))
        writes = [x for x in fake.calls if x[0] not in {"GET", "GET_BYTES"}]
        self.assertEqual((35, 35, 30, 30), tuple(sum(x[1] == endpoint for x in writes) for endpoint in
            ("/api/products", "/api/product-images", "/api/technical-sheets/", "/never"))[:3] + (sum(x[0] == "PATCH" for x in writes),))
        image_call = next(x for x in writes if x[1] == "/api/product-images")
        sheet_call = next(x for x in writes if x[1] == "/api/technical-sheets/")
        self.assertEqual({"image"}, set(image_call[3]["files"])); self.assertEqual({"file"}, set(sheet_call[3]["files"]))
        self.assertEqual({"product", "alt_text", "is_main", "order"}, set(image_call[3]["data"]))
        self.assertNotIn("product_id", image_call[3]["data"])
        self.assertEqual(fake.products[0]["id"], image_call[3]["data"]["product"])
        self.assertTrue(image_call[3]["data"]["is_main"]); self.assertEqual(0, image_call[3]["data"]["order"])
        self.assertEqual(131, len(writes)); self.assertEqual(131, plan["counts"]["planned_mutations"])
        self.assertEqual(MISSING_SHEETS, {p["model"] for p in fake.products if p["technical_sheet_id"] is None})
        before = len(fake.calls)
        with patch.dict(os.environ, {"JEM_NEXUS_LOCAL_READ_TOKEN": "READ"}, clear=True):
            self.assertEqual(0, main(["--root", str(self.root), "import-ep-local", "--verify", "--base-url", BASE], fake))
        self.assertTrue(all(x[0] in {"GET", "GET_BYTES"} for x in fake.calls[before:]))
        second = self.run_dry(fake); self.assertEqual(0, second["counts"]["planned_mutations"]); self.assertEqual([], second["conflicts"])

    def test_existing_binary_relations_specs_and_divergence(self):
        fake = FakeTransport(); plan = self.run_dry(fake); self.run_apply(fake, plan["fingerprint"])
        fresh = self.run_dry(fake); self.assertTrue(all(not x["upload_image"] and not x["upload_sheet"] for x in fresh["operations"]))
        fake.binaries[next(k for k in fake.binaries if "product-images" in k)] = JPEG + b"changed"
        self.assertTrue(self.run_dry(fake)["conflicts"])
        (self.root / "_control/ep-local-import/ep-local-import-checkpoint.json").unlink()
        fake = FakeTransport(); plan = self.run_dry(fake); self.run_apply(fake, plan["fingerprint"])
        fake.specs.append({"id": 999, "product": fake.products[0]["id"], "name": "x", "value": "y", "order": 0})
        self.assertIn("SPEC_PRESENT", {x["reason"] for x in self.run_dry(fake)["conflicts"]})

    def test_fingerprint_tamper_old_plan_and_remote_drift_block_before_write(self):
        fake = FakeTransport(); plan = self.run_dry(fake); path = self.root / "_control/ep-local-import/ep-local-import-plan.json"
        changed = json.loads(path.read_text()); changed["operations"][0]["payload"]["name"] = "tampered"; path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(EpLocalError, "fingerprint almacenado"):
            self.run_apply(fake, plan["fingerprint"])
        changed["format_version"] = 1; path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(EpLocalError, "versión"):
            self.run_apply(fake, plan["fingerprint"])
        plan = self.run_dry(fake); fake.brands.append({"id": 8, "name": "X", "slug": "x", "is_active": True}); before = len(fake.calls)
        with self.assertRaisesRegex(EpLocalError, "deriva remota"):
            self.run_apply(fake, plan["fingerprint"])
        self.assertTrue(all(x[0] in {"GET", "GET_BYTES"} for x in fake.calls[before:]))

    def test_resume_skips_receipted_mutations_and_definitive_error_clears_intent(self):
        fake = FakeTransport(); plan = self.run_dry(fake); self.run_apply(fake, plan["fingerprint"]); before = len(fake.calls)
        self.run_apply(fake, plan["fingerprint"])
        self.assertTrue(all(x[0] in {"GET", "GET_BYTES"} for x in fake.calls[before:]))
        (self.root / "_control/ep-local-import/ep-local-import-checkpoint.json").unlink()
        other = FakeTransport(); plan = self.run_dry(other); other.fail = DefinitiveRemoteError("HTTP 429 retry_after=12")
        with self.assertRaisesRegex(DefinitiveRemoteError, "retry_after=12"):
            self.run_apply(other, plan["fingerprint"])
        checkpoint = json.loads((self.root / "_control/ep-local-import/ep-local-import-checkpoint.json").read_text())
        self.assertIsNone(checkpoint["intent"]); self.assertNotIn("WRITE-SECRET", json.dumps(checkpoint))

    def test_resume_real_checkpoint_shape_reconciles_and_resolves_error(self):
        fake = FakeTransport(False); plan = self.run_dry(fake); first = plan["operations"][0]
        self.assertEqual("CBY 30II", first["model"])
        brand = {"id": 3, "name": "EP", "slug": "ep", "is_active": True}
        product = {"id": 59, "technical_sheet_id": None, **{**first["payload"], "brand_id": 3}}
        fake.brands.append(brand); fake.products.append(product)
        checkpoint = {"fingerprint": plan["fingerprint"], "intent": None,
                      "completed": {"brand": brand, "CBY 30II:product": product},
                      "receipts": [{"key": "brand", "id": 3}, {"key": "CBY 30II:product", "id": 59}],
                      "errors": [{"key": "CBY 30II:image", "error": "HTTP 400"}]}
        checkpoint_path = self.root / "_control/ep-local-import/ep-local-import-checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
        before = len(fake.calls); self.assertEqual(0, self.run_apply(fake, plan["fingerprint"]))
        writes = [call for call in fake.calls[before:] if call[0] not in {"GET", "GET_BYTES"}]
        self.assertEqual(129, len(writes)); self.assertEqual(("POST", "/api/product-images"), writes[0][:2])
        self.assertEqual(59, writes[0][3]["data"]["product"]); self.assertNotIn("product_id", writes[0][3]["data"])
        self.assertFalse(any(call[1] == "/api/brands" for call in writes))
        self.assertFalse(any(call[1] == "/api/products" and call[3].get("json_data", {}).get("model") == "CBY 30II" for call in writes))
        finished = json.loads(checkpoint_path.read_text())
        self.assertEqual((131, 131), (len(finished["completed"]), len(finished["receipts"])))
        self.assertIsNone(finished["intent"]); self.assertEqual([], finished["errors"])
        self.assertEqual([{"key": "CBY 30II:image", "error": "HTTP 400"}], finished["resolved_errors"])
        before = len(fake.calls); self.run_apply(fake, plan["fingerprint"])
        self.assertTrue(all(call[0] in {"GET", "GET_BYTES"} for call in fake.calls[before:]))
        self.assertEqual(1, len(json.loads(checkpoint_path.read_text())["resolved_errors"]))

    def test_completed_receipt_drift_blocks_before_writes(self):
        fake = FakeTransport(False); plan = self.run_dry(fake)
        brand = {"id": 3, "name": "NOT EP", "slug": "ep", "is_active": True}; fake.brands.append(brand)
        checkpoint = {"fingerprint": plan["fingerprint"], "intent": None, "completed": {"brand": brand},
                      "receipts": [{"key": "brand", "id": 3}], "errors": []}
        (self.root / "_control/ep-local-import/ep-local-import-checkpoint.json").write_text(json.dumps(checkpoint))
        before = len(fake.calls)
        with self.assertRaisesRegex(EpLocalError, "deriva remota"):
            self.run_apply(fake, plan["fingerprint"])
        self.assertTrue(all(call[0] in {"GET", "GET_BYTES"} for call in fake.calls[before:]))

    def test_ambiguous_timeout_keeps_intent(self):
        fake = FakeTransport(); plan = self.run_dry(fake); fake.fail = TimeoutError("lost response")
        with self.assertRaises(TimeoutError): self.run_apply(fake, plan["fingerprint"])
        checkpoint = json.loads((self.root / "_control/ep-local-import/ep-local-import-checkpoint.json").read_text())
        self.assertIsNotNone(checkpoint["intent"]); self.assertNotIn("lost response", json.dumps(checkpoint))

    def test_multipart_encoder_preserves_names_mime_and_bytes(self):
        transport = LocalTransport(BASE); capture = CaptureOpener(); transport.opener = capture
        image = next((self.root / "EP/Imagenes modelos EP").iterdir()); sheet = next((self.root / "EP/fichas-tecnicas EP").iterdir())
        transport.request("POST", "/api/product-images", "secret", files={"image": image}, data={"product": 59, "alt_text": "EP X", "is_main": True, "order": 0})
        transport.request("POST", "/api/technical-sheets/", "secret", files={"file": sheet}, data={"name": "Ficha"})
        image_body, sheet_body = (request.data for request in capture.requests)
        self.assertIn(b'name="image"; filename=', image_body); self.assertNotIn(b'name="file"; filename=', image_body)
        self.assertIn(b'name="product"\r\n\r\n59\r\n', image_body); self.assertNotIn(b'name="product_id"', image_body)
        for field in (b'alt_text', b'is_main', b'order'):
            self.assertIn(b'name="' + field + b'"', image_body)
        self.assertIn(b"Content-Type: image/jpeg", image_body); self.assertIn(image.read_bytes(), image_body)
        self.assertIn(b'name="file"; filename=', sheet_body); self.assertIn(b"Content-Type: application/pdf", sheet_body); self.assertIn(sheet.read_bytes(), sheet_body)

    def test_http_error_detail_is_safe_and_bounded(self):
        class ErrorOpener:
            def __init__(self, body): self.body = body
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 400, "bad", {}, BytesIO(self.body))
        transport = LocalTransport(BASE)
        transport.opener = ErrorOpener(b'{"detail":"image is required."}')
        with self.assertRaisesRegex(DefinitiveRemoteError, r"^HTTP 400 detail=image is required\.$"):
            transport.request("GET", "/api/product-images", "SECRET")
        for body in (b"<html>SECRET</html>", b'{"other":"SECRET"}',
                     json.dumps({"detail": "Authorization Bearer SECRET"}).encode(),
                     json.dumps({"detail": "x" * 241}).encode()):
            transport.opener = ErrorOpener(body)
            with self.assertRaisesRegex(DefinitiveRemoteError, r"^HTTP 400$") as raised:
                transport.request("GET", "/api/product-images", "SECRET")
            self.assertNotIn("SECRET", str(raised.exception))

    def test_guards_missing_token_urls_and_legacy_path(self):
        for url in ("https://localhost:443", "http://localhost", "http://10.0.0.1:80", "http://u:p@localhost:80"):
            with self.assertRaises(EpLocalError): validate_base_url(url)
        fake = FakeTransport()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "JEM_NEXUS_LOCAL_READ_TOKEN"):
                main(["--root", str(self.root), "import-ep-local", "--dry-run", "--base-url", BASE], fake)
        self.assertEqual([], fake.calls); self.assertEqual("ep-model-01", product_payload("MODEL 01", 1, 2)["slug"])
