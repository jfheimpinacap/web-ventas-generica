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
        self.fail_patch_at = None; self.get_mutation = None; self.bad_post_metadata = False; self.bad_post_hash = False

    def get_json(self, path):
        self.calls.append(("GET", path))
        routes = {"/api/categories?include_inactive=true": "categories", "/api/brands?include_inactive=true": "brands",
            "/api/products?include_unpublished=true": "products", "/api/product-images": "images",
            "/api/product-specs": "specs", "/api/technical-sheets": "sheets"}
        if path in routes: return deepcopy(self.state[routes[path]])
        product_id = int(path.rsplit("/", 1)[1])
        if self.get_mutation: self.get_mutation(self, product_id); self.get_mutation = None
        return deepcopy(self.state["details"][product_id])

    def download(self, sheet_id, expected_content_type="application/pdf"):
        self.calls.append(("GET", f"/api/technical-sheets/{sheet_id}/file")); return self.files[sheet_id]

    def post_datasheet(self, name, filename, data):
        self.calls.append(("POST", "/api/technical-sheets")); self.post_count += 1
        sheet_id = max([s["id"] for s in self.state["sheets"]] or [0]) + 1
        sheet = sheet_metadata(sheet_id, name, filename, data)
        if self.bad_post_metadata: sheet["original_file_name"] = "wrong.pdf"
        self.state["sheets"].append(sheet); self.files[sheet_id] = b"wrong" if self.bad_post_hash else data
        return deepcopy(sheet)

    def patch_product(self, product_id, payload):
        self.calls.append(("PATCH", f"/api/products/{product_id}")); self.patch_count += 1
        if self.fail_patch_at == product_id: raise tool.SafeError("synthetic secret must not escape")
        detail = self.state["details"][product_id]
        for key, value in payload.items(): detail[key] = {"id": value} if key == "technical_sheet" else value
        if self.concurrent_change: detail["slug"] += "-concurrent"
        return deepcopy(detail)


def fixture(catalog=None):
    catalog = catalog or tuple({"source_model": f"SRC{i:02}", "target_model": f"M{i:02}",
        "target_name": f"Elevador tipo tijera eléctrico LGMG M{i:02}", "working_height_m": float(i),
        "maximum_load_capacity_kg": 200 + i, "machine_weight_kg": 1000 + i,
        "power_source": "electric_24v", "datasheet_name": f"Ficha técnica LGMG M{i:02}"} for i in range(1, 22))
    datasheets, media = [], {}
    for i, row in enumerate(catalog, 1):
        data = b"%PDF-" + bytes([64 + i]) * (20 + i); filename = f'{row["target_model"]}.pdf'; media[filename] = data
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


REAL_COMPOUND_HEIGHTS = {
    "S0808E-2": "9.8m/8m(dentro/fuera)", "S1212E-2": "14m/9.5m(dentro/fuera)",
    "S1413E-2": "15.8m/10m(dentro/fuera)", "S0808EⅡ": "9.8/8 m(dentro / fuera)",
    "S1212EⅡ": "14/9.5 m(dentro / fuera)", "S1413EⅡ": "15.8/10 m(dentro / fuera)",
    "S0808Ⅱ": "9.8/8 m(dentro / fuera)", "S1212Ⅱ": "14/9.5 m(dentro / fuera)",
    "S1413Ⅱ": "15.8/10 m(dentro/fuera)",
}


def realistic_evidence(catalog=None):
    catalog = catalog or tool.approved_catalog(); rows = []
    for product in catalog:
        source = product["source_model"]; height = REAL_COMPOUND_HEIGHTS.get(source, f'{product["working_height_m"]:g}m')
        height_label = "Máx. Altura de Trabajo" if source == "SS0607E" else "Altura máxima de trabajo"
        if source == "SS0607E": weight_label, power_label, power = "Peso de Máquina (CE)", "Fuente de Alimentación", "24V DC 150Ah"
        elif source.endswith("E-2"): weight_label, power_label, power = "Peso de la máquina", "Fuente de potencia", "Batería 24 V"
        else: weight_label, power_label, power = "Peso de la máquina (CE/ANSI)", "Fuente de potencia", "24V DC"
        rows.extend((
            {"source_key": product["source_key"], "source_label": height_label, "source_value": height},
            {"source_key": product["source_key"], "source_label": "Capacidad de la plataforma", "source_value": f'{product["maximum_load_capacity_kg"]}kg'},
            {"source_key": product["source_key"], "source_label": weight_label, "source_value": f'{product["machine_weight_kg"]}kg'},
            {"source_key": product["source_key"], "source_label": power_label, "source_value": power},
        ))
    return rows


class EnrichmentTests(unittest.TestCase):
    def approved(self): return tool.approved_catalog()[0]

    def test_closed_table_has_exact_21_values(self):
        self.assertEqual(len(tool.APPROVED_ROWS), 21)
        self.assertEqual(tool.APPROVED_ROWS[0], ("S0607E-2", "S0607E-2", "7.8", 230, 1550))
        self.assertEqual(tool.APPROVED_ROWS[-1], ("S1413Ⅱ", "S1413", "15.8", 320, 3500))

    def test_all_21_realistic_evidence_rows_are_accepted(self):
        catalog = tool.approved_catalog(); evidence = tool.validate_evidence(catalog, realistic_evidence(catalog))
        self.assertEqual(len(evidence), 21)
        self.assertEqual(next(x for x in evidence if x["source_model"] == "S0808E-2")["height_outside_m"], "8")

    def test_realistic_21_product_dry_run_has_no_writes(self):
        catalog = tool.approved_catalog(); tool.validate_evidence(catalog, realistic_evidence(catalog))
        _, datasheets, media, state = fixture(catalog); client = FakeClient(state, {}, media)
        code, result = tool.orchestrate(client, deepcopy(state), catalog, datasheets, ".", False)
        self.assertEqual((code, result["verdict"], result["products_examined"]), (0, "DRY_RUN_APPROVED", 21))
        self.assertEqual((len(result["products"]), len(result["datasheets"]), client.post_count, client.patch_count), (21, 21, 0, 0))

    def test_real_compound_height_regressions_select_inside_value(self):
        catalog = tool.approved_catalog()
        for source, inside, outside in (("S0808E-2", "9.8", "8"), ("S1212EⅡ", "14", "9.5"), ("S1413Ⅱ", "15.8", "10")):
            with self.subTest(source=source):
                product = next(x for x in catalog if x["source_model"] == source)
                result = tool.validate_evidence([product], realistic_evidence([product]))[0]
                self.assertEqual((result["height_inside_m"], result["height_outside_m"]), (inside, outside))

    def test_ss0607e_real_labels_regression(self):
        product = next(x for x in tool.approved_catalog() if x["source_model"] == "SS0607E")
        result = tool.validate_evidence([product], realistic_evidence([product]))[0]
        self.assertEqual(result["height_values"], "7.5m"); self.assertEqual(result["weight_values"], "1335kg")

    def test_compound_height_is_strict_and_fail_closed(self):
        product = next(x for x in tool.approved_catalog() if x["source_model"] == "S0808E-2")
        for bad in ("9.7m/8m(dentro/fuera)", "9.8m/(dentro/fuera)", "9.8m/8m", "32ft/26ft(dentro/fuera)",
                "9.8m(dentro/fuera)", "9.8m/8m/7m(dentro/fuera)", "9.8m/8m(fuera/dentro)", "0m/0m(dentro/fuera)"):
            rows = realistic_evidence([product]); rows[0]["source_value"] = bad
            with self.subTest(value=bad), self.assertRaises(tool.SafeError) as caught: tool.validate_evidence([product], rows)
            self.assertEqual(caught.exception.failure_code, "EVIDENCE_WORKING_HEIGHT_INCOMPATIBLE")

    def test_component_weight_and_missing_24v_have_stable_codes(self):
        product = next(x for x in tool.approved_catalog() if x["source_model"] == "SS0607E")
        for index, value, code in ((2, "Peso de la batería", "EVIDENCE_MACHINE_WEIGHT_INCOMPATIBLE"),
                (3, "12V DC 150Ah", "EVIDENCE_POWER_24V_MISSING")):
            rows = realistic_evidence([product])
            if index == 2: rows[index]["source_label"] = value
            else: rows[index]["source_value"] = value
            with self.subTest(code=code), self.assertRaises(tool.SafeError) as caught: tool.validate_evidence([product], rows)
            self.assertEqual(caught.exception.failure_code, code)

    def test_safe_error_cli_diagnostic_never_prints_message(self):
        previous = tool.run; tool.run = lambda *args, **kwargs: (_ for _ in ()).throw(tool.SafeError("access token=SENSITIVE"))
        try:
            stderr = io.StringIO()
            from contextlib import redirect_stderr
            with redirect_stderr(stderr): code = tool.main(["--plan-input", "p", "--media-input", "m", "--api-base-url", "http://localhost:5000", "--output-dir", "o"])
            self.assertEqual(code, 1); self.assertEqual(stderr.getvalue(), "ERROR: INPUT_VALIDATION_FAILED\n")
        finally: tool.run = previous

    def test_controlled_failure_reports_are_safe_and_complete(self):
        result = {"mode": "dry-run", "verdict": "CONFLICT", "conflicts": 1,
            "failure_stage": "evidence_validation", "failure_code": "EVIDENCE_WORKING_HEIGHT_INCOMPATIBLE",
            "failed_product": "S0808E-2", "post_requests": 0, "patch_requests": 0,
            "products": [], "datasheets": [], "actions": [],
            "errors": [{"product": "S0808E-2", "error": "EVIDENCE_WORKING_HEIGHT_INCOMPATIBLE"}]}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "reports"; tool.write_outputs(output, result)
            self.assertEqual({p.name for p in output.iterdir()}, set(tool.OUTPUT_NAMES))
            summary = json.loads((output / "enrichment-summary.json").read_text())
            self.assertEqual((summary["verdict"], summary["conflicts"], summary["post_requests"], summary["patch_requests"]),
                ("CONFLICT", 1, 0, 0))
            combined = b"".join(path.read_bytes() for path in output.iterdir())
            for secret in (b"access token=SENSITIVE", b"Authorization", b"multipart", b"%PDF-"):
                self.assertNotIn(secret, combined)

    def test_backend_static_contract(self):
        root = PATH.parents[2]
        endpoints = (root / "backend-dotnet/JemNexus.Api/Endpoints/TechnicalSheetEndpoints.cs").read_text()
        dtos = (root / "backend-dotnet/JemNexus.Api/Dtos/TechnicalSheetDtos.cs").read_text()
        program = (root / "backend-dotnet/JemNexus.Api/Program.cs").read_text()
        self.assertIn('MapGet("/{id:int}/file"', endpoints)
        self.assertNotIn('MapGet("/{id:int}/' + 'download"', endpoints)
        self.assertIn("string ContentType", dtos); self.assertIn("JsonNamingPolicy.SnakeCaseLower", program)
        self.assertIn("MaxFileSize = 10 * 1024 * 1024", endpoints)
        self.assertEqual(tool.MAX_DATASHEET_BYTES, 10 * 1024 * 1024)

    def test_ten_mib_boundary_is_accepted_and_larger_rejected_before_http(self):
        tool.validate_datasheet_sizes([{"size_bytes": tool.MAX_DATASHEET_BYTES}])
        with self.assertRaisesRegex(tool.SafeError, "SIZE_LIMIT"):
            tool.validate_datasheet_sizes([{"size_bytes": tool.MAX_DATASHEET_BYTES + 1}])

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

    def test_post_hash_verified_then_patch_failure_is_resumable(self):
        catalog, datasheets, media, state = fixture(); files = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in media.items(): (Path(tmp) / name).write_bytes(data)
            client = FakeClient(state, files, media); client.fail_patch_at = 1
            code, result = tool.orchestrate(client, tool.snapshot(client, catalog), catalog, datasheets, tmp, True)
            self.assertEqual((code, result["verdict"]), (1, "PARTIAL_FAILURE"))
            self.assertEqual((len(result["products"]), len(result["datasheets"])), (21, 21))
            self.assertEqual(result["created_datasheet_ids"], [1]); self.assertEqual(result["failed_product"], "M01")
            self.assertEqual([a["result"] for a in result["actions"][-3:]], ["uploaded", "hash_verified", "pre_patch_revalidated"])
            self.assertIsNone(state["details"][1]["technical_sheet"]); self.assertEqual(len(state["sheets"]), 1)
            resumed = FakeClient(state, files, media)
            code2, result2 = tool.orchestrate(resumed, tool.snapshot(resumed, catalog[:1]), catalog[:1], datasheets[:1], tmp, True)
            self.assertEqual((code2, resumed.post_count, resumed.patch_count), (0, 0, 1))
            self.assertEqual(result2["datasheets_reused"], 1)

    def test_failure_after_multiple_products_preserves_progress(self):
        catalog, datasheets, media, state = fixture(); files = {}
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in media.items(): (Path(tmp) / name).write_bytes(data)
            client = FakeClient(state, files, media); client.fail_patch_at = 3
            code, result = tool.orchestrate(client, tool.snapshot(client, catalog), catalog, datasheets, tmp, True)
            self.assertEqual(code, 1); self.assertEqual(result["updated_product_ids"], [1, 2])
            self.assertEqual(result["created_datasheet_ids"], [1, 2, 3])
            self.assertEqual(result["products"][3]["status"], "not_started")

    def test_post_metadata_or_hash_failure_never_patches_or_claims_hash(self):
        for attribute in ("bad_post_metadata", "bad_post_hash"):
            catalog, datasheets, media, state = fixture(); files = {}
            with self.subTest(attribute=attribute), tempfile.TemporaryDirectory() as tmp:
                for name, data in media.items(): (Path(tmp) / name).write_bytes(data)
                client = FakeClient(state, files, media); setattr(client, attribute, True)
                code, result = tool.orchestrate(client, tool.snapshot(client, catalog), catalog, datasheets, tmp, True)
                self.assertEqual((code, client.patch_count, result["verdict"]), (1, 0, "PARTIAL_FAILURE"))
                self.assertFalse(result["datasheets"][0]["hash_verified"])
                self.assertEqual(len(result["products"]), 21); self.assertNotIn(b"wrong", json.dumps(result).encode())

    def test_pre_patch_revalidation_handles_concurrent_technical_values(self):
        cases = (("working_height_m", 999, 1), ("working_height_m", 1.0, 0), ("technical_sheet", {"id": 999}, 1))
        for field, value, expected_code in cases:
            catalog, datasheets, media, state = fixture(); files = {}
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                for name, data in media.items(): (Path(tmp) / name).write_bytes(data)
                client = FakeClient(state, files, media)
                before = tool.snapshot(client, catalog[:1])
                client.get_mutation = lambda c, pid, f=field, v=value: c.state["details"][pid].__setitem__(f, v)
                code, result = tool.orchestrate(client, before, catalog[:1], datasheets[:1], tmp, True)
                self.assertEqual(code, expected_code)
                self.assertIn("pre_patch_revalidated", [a["result"] for a in result["actions"]])
                if expected_code: self.assertEqual(client.patch_count, 0)

    def test_unrelated_jpeg_is_baselined_and_preserved(self):
        catalog, datasheets, media, state = fixture(); jpeg = b"\xff\xd8\xffsynthetic"
        foreign = sheet_metadata(80, "Photo", "photo.jpg", jpeg); foreign["content_type"] = "image/jpeg"
        state["sheets"].append(foreign); files = {80: jpeg}; client = FakeClient(state, files, media)
        plans, cache = tool.preflight(client, state, catalog, datasheets)
        self.assertIn(80, cache); self.assertTrue(all(p.resolved_sheet is None for p in plans))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "M01.pdf").write_bytes(media["M01.pdf"])
            code, result = tool.orchestrate(client, tool.snapshot(client, catalog[:1]), catalog[:1], datasheets[:1], tmp, True)
            self.assertEqual(code, 0); self.assertEqual(state["sheets"][0], foreign); self.assertEqual(files[80], jpeg)

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
            code, result = tool.orchestrate(client, tool.snapshot(client, catalog), catalog[:1], datasheets[:1], tmp, True)
            self.assertEqual((code, result["verdict"]), (1, "PARTIAL_FAILURE"))
            self.assertEqual(len(result["products"]), 1); self.assertEqual(result["updated_product_ids"], [1])

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
