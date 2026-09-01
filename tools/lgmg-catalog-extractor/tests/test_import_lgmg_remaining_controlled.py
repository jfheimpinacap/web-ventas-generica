import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).parents[1] / "import_lgmg_remaining_controlled.py"
spec = importlib.util.spec_from_file_location("remaining_controlled", MODULE)
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)


class Args:
    dry_run = apply = verify = rollback = False
    checkpoint = None; batch_size = 20; resume = False
    confirm_apply = confirm_rollback = None


class Response:
    def __init__(self, url, value, mime="application/json"):
        self.url = url; self.raw = json.dumps(value).encode(); self.mime = mime
        self.headers = self
    def geturl(self): return self.url
    def read(self, limit): return self.raw
    def get_content_type(self): return self.mime


class Opener:
    def __init__(self, response): self.response = response; self.request = None; self.timeout = None
    def open(self, request, timeout): self.request = request; self.timeout = timeout; return self.response


class ControlledImporterTests(unittest.TestCase):
    def test_01_cli_has_exact_inputs_modes_and_no_token_argument(self):
        parser = tool.build_parser(); destinations = {a.dest for a in parser._actions}
        self.assertTrue({"plan_input", "remaining_audit_input", "repaired_media_input", "output_dir", "api_base_url"} <= destinations)
        self.assertFalse({"token", "publish", "model", "filter"} & destinations)
        with self.assertRaises(SystemExit): parser.parse_args([])
        base = ["--plan-input","p","--remaining-audit-input","a","--repaired-media-input","r","--output-dir","o","--api-base-url","https://api.example"]
        with self.assertRaises(SystemExit): parser.parse_args(base + ["--dry-run", "--verify"])

    def test_02_token_only_environment_and_never_returned_in_error(self):
        self.assertEqual(tool.access_token({tool.TOKEN_ENV: "opaque-secret"}), "opaque-secret")
        for env in ({}, {tool.TOKEN_ENV: "bad\nsecret"}):
            with self.assertRaises(tool.ConflictError) as caught: tool.access_token(env)
            self.assertNotIn("secret", str(caught.exception))

    def test_03_exact_confirmations_and_read_modes_reject_them(self):
        a = Args(); a.apply = True
        with self.assertRaises(tool.ConflictError): tool.validate_cli(a)
        a.confirm_apply = tool.APPLY_CONFIRMATION; self.assertEqual(tool.validate_cli(a), "apply")
        b = Args(); b.rollback = True; b.confirm_rollback = tool.ROLLBACK_CONFIRMATION
        self.assertEqual(tool.validate_cli(b), "rollback")
        c = Args(); c.dry_run = True; c.confirm_apply = tool.APPLY_CONFIRMATION
        with self.assertRaises(tool.ConflictError): tool.validate_cli(c)

    def test_04_fingerprints_families_outputs_and_verdicts_are_closed(self):
        self.assertEqual(len(tool.APPROVED_FINGERPRINTS), 6)
        self.assertTrue(all(len(x) == 64 for x in tool.APPROVED_FINGERPRINTS.values()))
        self.assertEqual(len(tool.FAMILIES), 6); self.assertEqual(len(tool.OUTPUT_NAMES), 8)
        self.assertEqual(tool.VERDICTS, {"DRY_RUN_READY","APPLY_COMPLETE","APPLY_PARTIAL","VERIFY_COMPLETE","ROLLBACK_COMPLETE","CONFLICT"})

    def test_05_closed_cohort_is_read_from_ast(self):
        pairs = tool._load_closed_pairs()
        self.assertEqual((len(pairs), len(set(pairs))), (21, 21))
        self.assertIn(("S0607EⅡ", "lgmg-c7eb4374a0c40929"), pairs)

    def test_06_literal_payload_is_conservative(self):
        row = {"approved_name":"Elevador LGMG SR1018E-2", "metric_model":"SR1018E-2", "stock_status":"on_request",
               "maximum_load_capacity_kg":"450", "target_power_source":"electric_lithium", "description":"Preservada"}
        payload = tool.product_payload(row, 2, 3)
        self.assertEqual(payload["model"], "SR1018E-2"); self.assertEqual(payload["maximum_load_capacity_kg"], 450.0)
        self.assertEqual(payload["power_source"], "electric_lithium"); self.assertEqual(payload["description"], "Preservada")
        for key in ("year","hours_meter","working_height_m","terrain_type","machine_weight_kg","price"):
            self.assertIsNone(payload[key])
        self.assertFalse(payload["price_visible"]); self.assertFalse(payload["is_published"]); self.assertFalse(payload["is_featured"])

    def test_07_capacity_and_energy_are_not_invented(self):
        row = {"approved_name":"N Ⅱ", "metric_model":"Ⅱ", "stock_status":"on_request",
               "maximum_load_capacity_kg":"invalid", "target_power_source":"diesel"}
        payload = tool.product_payload(row, 1, 1)
        self.assertIsNone(payload["maximum_load_capacity_kg"]); self.assertIsNone(payload["power_source"])

    def test_08_specs_preserve_unicode_value_unit_and_order(self):
        value = tool.spec_payload({"name":"Ángulo", "key":"ángulo", "value":"≤ Ⅱ", "unit":"°", "order":"7"}, 9)
        self.assertEqual(value, {"product":9,"name":"Ángulo","key":"ángulo","value":"≤ Ⅱ","unit":"°","order":7})

    def test_09_batch_default_split_and_range(self):
        self.assertEqual([len(x) for x in tool.batch_ranges()], [20, 16])
        self.assertEqual(len(tool.batch_ranges(36, 1)), 36)
        for value in (0, -1, 21):
            with self.assertRaises(tool.ConflictError): tool.batch_ranges(36, value)

    def test_10_safe_paths_reject_traversal_absolute_backslash(self):
        for value in ("../x", "/x", "C:/x", "a\\b", "./x", ""):
            with self.assertRaises(tool.ConflictError): tool.safe_relative(value)
        self.assertEqual(tool.safe_relative("corrected-media/images/x.jpg"), "corrected-media/images/x.jpg")

    def test_11_http_requires_https_except_loopback(self):
        self.assertEqual(tool.normalize_origin("https://API.EXAMPLE/"), "https://api.example")
        self.assertEqual(tool.normalize_origin("http://127.0.0.1:8765"), "http://127.0.0.1:8765")
        for url in ("http://example.com", "https://u:p@example.com", "https://example.com/path", "https://example.com?q=x"):
            with self.assertRaises(tool.ConflictError): tool.normalize_origin(url)

    def test_12_read_client_uses_timeout_auth_and_blocks_mutation(self):
        opener = Opener(Response("http://127.0.0.1:5000/api/auth/me", {"id": 1}))
        client = tool.ApiClient("http://127.0.0.1:5000", "opaque", "dry_run", opener)
        self.assertEqual(client.get("/api/auth/me"), {"id":1}); self.assertEqual(opener.timeout, 20)
        self.assertEqual(opener.request.headers["Authorization"], "Bearer opaque")
        with self.assertRaises(tool.ControlledImportError): client.post("/api/products", {})

    def test_13_redirects_are_rejected(self):
        handler = tool.NoRedirect()
        request = type("R", (), {"full_url":"https://one.example/api/products"})()
        with self.assertRaises(tool.ControlledImportError): handler.redirect_request(request, None, 302, "", {}, "https://two.example/api/products")

    def test_14_pagination_is_bounded_and_detects_cycle(self):
        class Client:
            origin="https://api.example"
            def get(self, path): return {"results":[], "next":path}
        with self.assertRaises(tool.ControlledImportError): tool.paginated(Client(), "/api/products")

    def test_15_taxonomy_exact_brand_duplicate_and_hierarchy(self):
        state = {"categories":[{"id":1,"name":"Maquinaria","product_type":"machinery","parent":None,"is_active":True}] +
                [{"id":i+2,"name":name,"product_type":"machinery","parent":1,"is_active":True} for i,name in enumerate(tool.FAMILIES)],
                "brands":[{"id":9,"name":"LGMG","is_active":True}]}
        _, cats, brand = tool.resolve_taxonomy(state); self.assertEqual((len(cats), brand["id"]), (6, 9))
        state["brands"].append(dict(state["brands"][0], id=10))
        with self.assertRaises(tool.ConflictError): tool.resolve_taxonomy(state)

    def test_16_classification_exact_conflict_and_idempotence(self):
        row={"approved_name":"Producto A13JE","metric_model":"A13JE","approved_family":tool.FAMILIES[0],"stock_status":"on_request"}
        data={"products":[row]}; cats={tool.FAMILIES[0]:{"id":2}}; brand={"id":3}
        empty={"products":[]}; self.assertEqual(tool.classify_products(data,empty,cats,brand)[0]["status"],"create_candidate")
        exact={"id":4,"name":"Producto A13JE","model":"A13JE","category":2,"brand":3,"is_published":False,"is_featured":False,"price":None,"price_visible":False}
        self.assertEqual(tool.classify_products(data,{"products":[exact]},cats,brand)[0]["status"],"already_imported_exact")
        self.assertEqual(tool.classify_products(data,{"products":[dict(exact,name="Otro")]},cats,brand)[0]["status"],"conflict_existing_product")

    def test_17_checkpoint_atomic_resume_and_secret_absence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"state.json"; expected={"tool":tool.TOOL_NAME,"version":tool.TOOL_VERSION,"mode":"apply","batch_size":20,"api_base":"https://a","fingerprints":{},"dry_run_fingerprint_sha256":"x"}
            self.assertEqual(tool.load_checkpoint(path, expected, False), expected)
            self.assertEqual(tool.load_checkpoint(path, expected, True), expected)
            altered=dict(expected,batch_size=19)
            with self.assertRaises(tool.ConflictError): tool.load_checkpoint(path, altered, True)
            self.assertNotIn("Bearer", path.read_text())

    def test_18_csv_bom_crlf_formula_and_exact_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"x.csv"; tool.write_csv(path,("v",),[{"v":"=cmd"},{"v":"ok"}]); raw=path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf")); self.assertIn(b"\r\n",raw); self.assertIn(b"'=cmd",raw)

    def test_19_media_multipart_preserves_bytes_and_primary(self):
        raw=b"\xff\xd8\xffunchanged"
        body,mime=tool._multipart_image(4,{"association_order":"1","is_primary":"true","original_filename":"A13JE.jpg","mime":"image/jpeg"},"a.jpg",raw)
        self.assertIn(raw,body); self.assertIn(b"is_main",body); self.assertIn(b"true",body); self.assertTrue(mime.startswith("multipart/form-data"))

    def test_20_dry_fingerprint_deterministic_and_sensitive(self):
        data={"fingerprints":tool.APPROVED_FINGERPRINTS}; decision={"row":{"approval_key":"a"},"status":"create_candidate","payload":{"model":"Ⅱ"}}
        first=tool.dry_run_fingerprint(data,[decision],"https://a","remote","head")
        self.assertEqual(first,tool.dry_run_fingerprint(data,[decision],"https://a","remote","head")); self.assertNotEqual(first,tool.dry_run_fingerprint(data,[decision],"https://b","remote","head"))

    def test_21_source_contains_no_lgmg_download_url_or_publish_option(self):
        source=MODULE.read_text(encoding="utf-8")
        self.assertNotIn("https://www.lgmglifts.com",source); self.assertNotIn('"--publish"',source)
        self.assertNotIn("import requests",source); self.assertNotIn("telemetry",source.casefold())


if __name__ == "__main__": unittest.main()
