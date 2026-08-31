"""Pruebas sintéticas: nunca usan red, API real ni base de datos."""

from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

PATH = Path(__file__).parents[1] / "enrich_lgmg_scissors_catalog.py"
SPEC = importlib.util.spec_from_file_location("enrichment", PATH)
tool = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = tool; SPEC.loader.exec_module(tool)


class Headers:
    def __init__(self, mime="application/json", values=None): self.mime, self.values = mime, values or {}
    def get_content_type(self): return self.mime
    def get(self, key): return self.values.get(key)


class Response:
    def __init__(self, url, value, mime="application/json"):
        self.url, self.raw, self.headers = url, value if isinstance(value, bytes) else json.dumps(value).encode(), Headers(mime)
    def geturl(self): return self.url
    def read(self, amount): return self.raw


class Opener:
    def __init__(self): self.requests = []; self.responses = []
    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.responses.pop(0) if self.responses else Response(request.full_url, {})


def sheet_metadata(sheet_id, name, filename, data):
    return {"id": sheet_id, "name": name, "original_file_name": filename,
        "content_type": "application/pdf", "size_bytes": len(data), "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z", "file_url": f"/technical-sheets/{sheet_id}/file"}


class FakeClient:
    """Backend falso mutable y persistente para invocaciones consecutivas."""
    def __init__(self, state, files, media_files):
        self.state, self.files, self.media_files, self.calls = state, files, media_files, []
        self.post_count = self.patch_count = 0
        self.concurrent_change = False

    def get_json(self, path):
        self.calls.append(("GET", path))
        routes = {"/api/categories?include_inactive=true": "categories", "/api/brands?include_inactive=true": "brands",
            "/api/products?include_unpublished=true": "products", "/api/product-images": "images",
            "/api/product-specs": "specs", "/api/technical-sheets": "sheets"}
        if path in routes: return deepcopy(self.state[routes[path]])
        product_id = int(path.rsplit("/", 1)[1]); return deepcopy(self.state["details"][product_id])

    def download(self, sheet_id):
        self.calls.append(("GET", f"/api/technical-sheets/{sheet_id}/file")); return self.files[sheet_id]

    def post_datasheet(self, name, filename, data):
        self.calls.append(("POST", "/api/technical-sheets")); self.post_count += 1
        sheet_id = max([s["id"] for s in self.state["sheets"]] or [0]) + 1
        sheet = sheet_metadata(sheet_id, name, filename, data)
        self.state["sheets"].append(sheet); self.files[sheet_id] = data
        return deepcopy(sheet)

    def patch_product(self, product_id, payload):
        self.calls.append(("PATCH", f"/api/products/{product_id}")); self.patch_count += 1
        detail = self.state["details"][product_id]
        for key, value in payload.items(): detail[key] = {"id": value} if key == "technical_sheet" else value
        if self.concurrent_change: detail["slug"] += "-concurrent"
        return deepcopy(detail)


def fixture():
    catalog = tuple({"source_model": f"SRC{i:02}", "target_model": f"M{i:02}",
        "target_name": f"Elevador tipo tijera eléctrico LGMG M{i:02}", "working_height_m": float(i),
        "maximum_load_capacity_kg": 200 + i, "machine_weight_kg": 1000 + i,
        "power_source": "electric_24v", "datasheet_name": f"Ficha técnica LGMG M{i:02}"} for i in range(1, 22))
    datasheets, media = [], {}
    for i, row in enumerate(catalog, 1):
        data = b"%PDF-" + bytes([64 + i]) * (20 + i); filename = f"M{i:02}.pdf"; media[filename] = data
        datasheets.append({"file_name": filename, "relative_path": filename, "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()})
    state = {"categories": [{"id": 1, "name": "Maquinaria", "is_active": True, "parent": None, "product_type": "machinery"},
            {"id": 2, "name": "Elevadores tipo tijera eléctricos", "is_active": True, "parent": {"id": 1}, "product_type": "machinery"}],
        "brands": [{"id": 1, "name": "LGMG", "is_active": True}], "products": [], "details": [],
        "images": [], "specs": [], "sheets": []}
    state["details"] = {}
    for i, row in enumerate(catalog, 1):
        summary = {"id": i, "name": row["target_name"], "model": row["target_model"], "slug": f"m{i:02}"}
        state["products"].append(summary)
        state["details"][i] = {**summary, "brand": {"id": 1}, "category": {"id": 2}, "description": f"desc {i}",
            "summary": f"summary {i}", "supplier": None, "price": 100, "currency": "CLP", "includes_vat": True,
            "stock": 1, "condition": "new", "sku": f"SKU{i}", "includes": "charger", "is_published": False,
            "is_featured": False, "terrain_type": None, "year": None, "hours_meter": None,
            "working_height_m": None, "maximum_load_capacity_kg": None, "machine_weight_kg": None,
            "power_source": None, "technical_sheet": None, "updated_at": "old", "updated_by": None}
        state["images"].append({"id": i, "product": {"id": i}, "is_main": True, "url": f"/{i}.jpg"})
        state["specs"].append({"id": i, "product": {"id": i}, "label": "unchanged"})
    return catalog, tuple(datasheets), media, state


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream: return list(csv.DictReader(stream))


class EnrichmentTests(unittest.TestCase):
    def approved(self): return tool.approved_catalog()[0]

    def test_closed_table_has_exact_21_values(self):
        self.assertEqual(len(tool.APPROVED_ROWS), 21)
        self.assertEqual(tool.APPROVED_ROWS[0], ("S0607E-2", "S0607E-2", "7.8", 230, 1550))
        self.assertEqual(tool.APPROVED_ROWS[-1], ("S1413Ⅱ", "S1413", "15.8", 320, 3500))

    def test_backend_static_contract(self):
        root = PATH.parents[2]
        endpoints = (root / "backend-dotnet/JemNexus.Api/Endpoints/TechnicalSheetEndpoints.cs").read_text()
        dtos = (root / "backend-dotnet/JemNexus.Api/Dtos/TechnicalSheetDtos.cs").read_text()
        program = (root / "backend-dotnet/JemNexus.Api/Program.cs").read_text()
        self.assertIn('MapGet("/{id:int}/file"', endpoints)
        self.assertNotIn('MapGet("/{id:int}/' + 'download"', endpoints)
        self.assertIn("string ContentType", dtos); self.assertIn("JsonNamingPolicy.SnakeCaseLower", program)

    def test_real_content_type_contract_is_strict(self):
        data = b"%PDF-x"; valid = sheet_metadata(1, "n", "x.pdf", data)
        tool.validate_sheet_contract(valid)
        invalid = dict(valid); invalid["mi" + "me_type"] = invalid.pop("content_type")
        with self.assertRaises(tool.SafeError): tool.validate_sheet_contract(invalid)

    def test_download_uses_file_route_and_allowlist(self):
        opener = Opener(); opener.responses.append(Response("http://localhost:5000/api/technical-sheets/4/file", b"%PDF-x", "application/pdf"))
        client = tool.LocalApiClient("http://localhost:5000", "secret", True, opener)
        client.download(4)
        self.assertEqual(client.calls, [("GET", "/api/technical-sheets/4/file")])
        with self.assertRaises(tool.SafeError): client.get_json("/api/technical-sheets/4/" + "download")

    def test_minimal_patch_never_emits_null_sheet(self):
        approved = self.approved(); detail = {"working_height_m": None, "maximum_load_capacity_kg": 230,
            "machine_weight_kg": "1550", "power_source": "electric_24v", "technical_sheet": None}
        self.assertEqual(tool.minimal_patch(detail, approved), {"working_height_m": 7.8})
        self.assertEqual(tool.minimal_patch(detail, approved, 9), {"working_height_m": 7.8, "technical_sheet": 9})
        self.assertNotIn(None, tool.minimal_patch(detail, approved).values())

    def test_hierarchy_parent_and_root_are_enforced(self):
        catalog, datasheets, media, state = fixture(); state["categories"][1]["parent"] = {"id": 99}
        with self.assertRaisesRegex(tool.SafeError, "Jerarquía"): tool.preflight(FakeClient(state, {}, media), state, catalog, datasheets)
        self.assertEqual(state["sheets"], [])

    def test_dry_run_has_21_rows_and_no_writes(self):
        catalog, datasheets, media, state = fixture(); client = FakeClient(state, {}, media)
        code, result = tool.orchestrate(client, deepcopy(state), catalog, datasheets, ".", False)
        self.assertEqual((code, result["verdict"]), (0, "DRY_RUN_APPROVED"))
        self.assertEqual((len(result["products"]), len(result["datasheets"])), (21, 21))
        self.assertTrue(all(x["status"] == "upload_required" for x in result["datasheets"]))
        self.assertEqual((client.post_count, client.patch_count), (0, 0))

    def test_pause_resume_and_idempotent_three_runs(self):
        catalog, datasheets, media, state = fixture(); files = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in media.items(): (root / name).write_bytes(data)
            first = FakeClient(state, files, media); code1, result1 = tool.orchestrate(first, tool.snapshot(first, catalog), catalog, datasheets, root, True)
            self.assertEqual((code1, result1["verdict"], first.post_count, first.patch_count), (2, "PAUSED_UPLOAD_WINDOW", 20, 20))
            self.assertEqual((len(result1["products"]), len(result1["datasheets"])), (21, 21))
            self.assertEqual(result1["datasheets"][-1]["status"], "pending_upload_window")
            second = FakeClient(state, files, media); code2, result2 = tool.orchestrate(second, tool.snapshot(second, catalog), catalog, datasheets, root, True)
            self.assertEqual((code2, second.post_count, second.patch_count), (0, 1, 1))
            self.assertEqual(result2["verdict"], "APPLY_VERIFIED")
            self.assertEqual(result2["updated_product_ids"], [21])
            third = FakeClient(state, files, media); code3, result3 = tool.orchestrate(third, tool.snapshot(third, catalog), catalog, datasheets, root, True)
            self.assertEqual((code3, third.post_count, third.patch_count), (0, 0, 0))
            self.assertEqual(result3["verdict"], "IDEMPOTENT_VERIFIED")
            self.assertTrue(all(x["final_verified"] for x in result3["products"]))
            self.assertEqual((len(result3["products"]), len(result3["datasheets"])), (21, 21))

    def test_already_enriched_product_is_accepted(self):
        catalog, datasheets, media, state = fixture(); data = media["M01.pdf"]
        state["sheets"].append(sheet_metadata(1, catalog[0]["datasheet_name"], "M01.pdf", data)); files = {1: data}
        detail = state["details"][1]
        for key in tool.DIRECT_FIELDS: detail[key] = catalog[0][key]
        detail["technical_sheet"] = {"id": 1}
        plans, _ = tool.preflight(FakeClient(state, files, media), state, catalog, datasheets)
        self.assertEqual(plans[0].sheet_status, "already_associated"); self.assertEqual(plans[0].direct_patch, {})

    def test_orphan_exact_sheet_is_reused_without_post(self):
        catalog, datasheets, media, state = fixture(); data = media["M01.pdf"]
        state["sheets"].append(sheet_metadata(1, catalog[0]["datasheet_name"], "M01.pdf", data)); client = FakeClient(state, {1: data}, media)
        plans, _ = tool.preflight(client, state, catalog, datasheets)
        self.assertEqual(plans[0].sheet_status, "reuse_required")

    def test_product_21_conflict_blocks_every_write(self):
        catalog, datasheets, media, state = fixture(); state["details"][21]["working_height_m"] = 999
        client = FakeClient(state, {}, media)
        with self.assertRaises(tool.SafeError): tool.orchestrate(client, deepcopy(state), catalog, datasheets, ".", True)
        self.assertEqual((client.post_count, client.patch_count), (0, 0))

    def test_wrong_associated_sheet_is_conflict(self):
        catalog, datasheets, media, state = fixture(); data = b"%PDF-wrong"
        state["sheets"].append(sheet_metadata(99, "Other", "other.pdf", data)); state["details"][1]["technical_sheet"] = {"id": 99}
        with self.assertRaisesRegex(tool.SafeError, "asociada"):
            tool.preflight(FakeClient(state, {99: data}, media), state, catalog, datasheets)

    def test_same_size_different_hash_unrelated_is_ignored(self):
        catalog, datasheets, media, state = fixture(); expected = media["M01.pdf"]; foreign = b"%PDF-Z" + b"Z" * (len(expected) - 6)
        self.assertEqual(len(expected), len(foreign))
        state["sheets"].append(sheet_metadata(8, "Foreign", "foreign.pdf", foreign))
        plans, _ = tool.preflight(FakeClient(state, {8: foreign}, media), state, catalog, datasheets)
        self.assertEqual(plans[0].sheet_status, "upload_required")

    def test_same_hash_under_other_name_is_conflict(self):
        catalog, datasheets, media, state = fixture(); data = media["M01.pdf"]
        state["sheets"].append(sheet_metadata(8, "Foreign", "foreign.pdf", data))
        with self.assertRaisesRegex(tool.SafeError, "Colisión"):
            tool.preflight(FakeClient(state, {8: data}, media), state, catalog, datasheets)

    def test_concurrent_commercial_change_is_detected(self):
        catalog, datasheets, media, state = fixture(); files = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in media.items(): (Path(tmp) / name).write_bytes(data)
            client = FakeClient(state, files, media); client.concurrent_change = True
            with self.assertRaisesRegex(tool.SafeError, "comercial"):
                tool.orchestrate(client, tool.snapshot(client, catalog), catalog[:1], datasheets[:1], tmp, True)

    def test_collections_are_preserved_after_complete_application(self):
        catalog, datasheets, media, state = fixture(); before = deepcopy(state); files = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in media.items(): (Path(tmp) / name).write_bytes(data)
            client = FakeClient(state, files, media)
            # Use one item to avoid the intentional 20-upload window in this preservation unit.
            code, result = tool.orchestrate(client, tool.snapshot(client, catalog[:1]), catalog[:1], datasheets[:1], tmp, True)
            self.assertEqual(code, 0); self.assertTrue(result["final_verification"])
            for key in ("categories", "brands", "images", "specs", "products"): self.assertEqual(state[key], before[key])

    def test_reports_have_required_columns_and_no_secrets(self):
        catalog, datasheets, media, state = fixture(); _, result = tool.orchestrate(FakeClient(state, {}, media), deepcopy(state), catalog, datasheets, ".", False)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"; tool.write_outputs(output, result)
            products, sheets = read_rows(output / "enrichment-products.csv"), read_rows(output / "enrichment-datasheets.csv")
            self.assertEqual((len(products), len(sheets)), (21, 21))
            self.assertTrue({"direct_fields_pending", "technical_sheet_status", "final_verified"} <= set(products[0]))
            self.assertTrue({"target_model", "product_id", "content_type", "hash_verified", "associated"} <= set(sheets[0]))
            combined = b"".join(x.read_bytes() for x in output.iterdir())
            for secret in (b"Authorization", b"Bearer", b"secret"): self.assertNotIn(secret, combined)

    def test_client_safety_multipart_and_rate_limit(self):
        opener = Opener(); client = tool.LocalApiClient("http://localhost:5000", "secret", True, opener)
        client.post_datasheet("Ficha", "safe.pdf", b"%PDF-x")
        body = opener.requests[0][0].data
        self.assertEqual(body.count(b'name="name"'), 1); self.assertEqual(body.count(b'name="file"'), 1); self.assertNotIn(b"secret", body)
        class RateOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 429, "rate", Headers(values={"Retry-After": "17"}), None)
        with self.assertRaises(tool.RatePause) as caught:
            tool.LocalApiClient("http://localhost:5000", "x", opener=RateOpener()).get_json("/api/technical-sheets")
        self.assertEqual((caught.exception.verdict, caught.exception.retry_after), ("PAUSED_RATE_LIMIT", 17))

    def test_origin_token_and_write_allowlists(self):
        self.assertEqual(tool.normalize_origin("http://localhost:5000"), "http://localhost:5000")
        for bad in ("https://localhost:5000", "http://localhost:5001", "http://user@localhost:5000"):
            with self.assertRaises(tool.SafeError): tool.normalize_origin(bad)
        self.assertEqual(tool.access_token({tool.TOKEN_ENV: "opaque"}), "opaque")
        client = tool.LocalApiClient("http://localhost:5000", "x", True, Opener())
        with self.assertRaises(tool.SafeError): client.patch_product(1, {"technical_sheet": None})
        source = PATH.read_text(); self.assertNotIn('request("DELETE"', source); self.assertNotIn('request("PUT"', source)


if __name__ == "__main__": unittest.main()
