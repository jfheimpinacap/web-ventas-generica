"""Pruebas sintéticas: nunca usan red, API real ni base de datos."""

import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error

PATH = Path(__file__).parents[1] / "enrich_lgmg_scissors_catalog.py"
SPEC = importlib.util.spec_from_file_location("enrichment", PATH)
tool = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(tool)


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
        if self.responses: return self.responses.pop(0)
        return Response(request.full_url, {})


class EnrichmentTests(unittest.TestCase):
    def approved(self): return tool.approved_catalog()[0]

    def test_closed_table_has_exact_21_values(self):
        self.assertEqual(len(tool.APPROVED_ROWS), 21)
        self.assertEqual(tool.APPROVED_ROWS[0], ("S0607E-2", "S0607E-2", "7.8", 230, 1550))
        self.assertEqual(tool.APPROVED_ROWS[-1], ("S1413Ⅱ", "S1413", "15.8", 320, 3500))
        self.assertTrue(all(tool.approved_catalog()[i]["power_source"] == "electric_24v" for i in range(21)))

    def test_u2161_and_existing_tables_are_cross_checked(self):
        catalog = tool.approved_catalog()
        changed = [x for x in catalog if x["source_model"] != x["target_model"]]
        self.assertEqual(len(changed), 12)
        self.assertTrue(all("Ⅱ" in x["source_model"] and "Ⅱ" not in x["target_model"] for x in changed))
        self.assertEqual(len({x["source_key"] for x in catalog}), 21)

    def test_exact_names_and_deterministic_datasheet_names(self):
        for row in tool.approved_catalog():
            self.assertEqual(row["target_name"], f"Elevador tipo tijera eléctrico LGMG {row['target_model']}")
            self.assertEqual(row["datasheet_name"], f"Ficha técnica LGMG {row['target_model']}")

    def test_origin_allowlist_is_exact(self):
        for good in ("http://localhost:5000", "http://127.0.0.1:5000/"):
            self.assertIn(tool.normalize_origin(good), ("http://localhost:5000", "http://127.0.0.1:5000"))
        for bad in ("https://localhost:5000", "http://localhost", "http://localhost:5001", "http://user@localhost:5000", "http://localhost:5000/api", "http://localhost:5000?q=1", "http://localhost:5000/#x", "http://LOCALHOST:5000"):
            with self.subTest(bad=bad), self.assertRaises(tool.SafeError): tool.normalize_origin(bad)

    def test_dry_client_allows_only_get(self):
        client = tool.LocalApiClient("http://localhost:5000", "secret", False, Opener())
        client.get_json("/api/products?include_unpublished=true")
        with self.assertRaises(tool.SafeError): client.patch_product(1, {"working_height_m": 7.8})
        with self.assertRaises(tool.SafeError): client.request("DELETE", "/api/products/1")
        self.assertEqual([x[0] for x in client.calls], ["GET"])

    def test_get_query_and_dynamic_routes_are_closed(self):
        client = tool.LocalApiClient("http://localhost:5000", "x", opener=Opener())
        for bad in ("/api/products", "/api/products?include_unpublished=false", "/api/products/1?x=1", "/api/foo"):
            with self.assertRaises(tool.SafeError): client.get_json(bad)

    def test_patch_allowlist_and_numeric_json(self):
        client = tool.LocalApiClient("http://localhost:5000", "x", True, Opener())
        client.patch_product(7, {"working_height_m": 7.8, "power_source": "electric_24v"})
        for payload in ({"name": "x"}, {"working_height_m": "7.8"}, {"power_source": "diesel"}, {}):
            with self.subTest(payload=payload), self.assertRaises(tool.SafeError): client.patch_product(7, payload)
        with self.assertRaises(tool.SafeError): client.request("POST", "/api/products", payload={})

    def test_multipart_has_exact_name_and_file_fields(self):
        opener = Opener(); client = tool.LocalApiClient("http://localhost:5000", "x", True, opener)
        client.post_datasheet("Ficha técnica LGMG S0607", "safe.pdf", b"%PDF-x")
        request = opener.requests[0][0]; body = request.data
        self.assertEqual(body.count(b'name="name"'), 1); self.assertEqual(body.count(b'name="file"'), 1)
        self.assertIn(b'filename="safe.pdf"', body); self.assertNotIn(b"secret", body)

    def test_token_only_from_environment_and_not_cli(self):
        self.assertEqual(tool.access_token({tool.TOKEN_ENV: "opaque"}), "opaque")
        for env in ({}, {tool.TOKEN_ENV: "x\nleak"}):
            with self.assertRaises(tool.SafeError): tool.access_token(env)
        options = {x.dest for x in tool.build_parser()._actions}
        self.assertNotIn("token", options); self.assertNotIn("password", options)

    def test_apply_requires_double_confirmation_before_platform_or_io(self):
        for apply, confirm in ((True, False), (False, True)):
            with self.assertRaisesRegex(tool.SafeError, "ambas confirmaciones"):
                tool.run("missing", "missing", "http://localhost:5000", "out", apply, confirm, "x", platform="linux")

    def test_windows_only_gate(self):
        with self.assertRaisesRegex(tool.SafeError, "Windows"):
            tool.run("missing", "missing", "http://localhost:5000", "out", False, False, "x", platform="linux")

    def test_minimal_patch_only_missing_and_numbers(self):
        approved = self.approved(); detail = {"working_height_m": None, "maximum_load_capacity_kg": 230,
            "machine_weight_kg": "1550", "power_source": "electric_24v", "technical_sheet": None}
        patch = tool.minimal_patch(detail, approved, 9)
        self.assertEqual(patch, {"working_height_m": 7.8, "technical_sheet": 9})
        self.assertIsInstance(patch["working_height_m"], float); self.assertIsInstance(patch["technical_sheet"], int)

    def test_minimal_patch_rejects_nonempty_conflict(self):
        with self.assertRaisesRegex(tool.SafeError, "working_height_m"):
            tool.minimal_patch({"working_height_m": 99}, self.approved(), 1)

    def test_preserved_terrain_year_hours_preflight(self):
        source = PATH.read_text(encoding="utf-8")
        self.assertIn('(\"terrain_type\", \"year\", \"hours_meter\")', source)
        for forbidden in ('"description":', '"slug":', '"is_published":', '"is_featured":'):
            self.assertNotIn(forbidden, source)

    def test_datasheet_reuse_downloads_and_checks_hash(self):
        data = b"%PDF-synthetic"; opener = Opener(); opener.responses.append(Response("http://localhost:5000/api/technical-sheets/4/download", data, "application/pdf"))
        client = tool.LocalApiClient("http://localhost:5000", "secret", True, opener)
        approved = self.approved(); sheet = {"id": 4, "name": approved["datasheet_name"], "original_file_name": "x.pdf", "mime_type": "application/pdf", "size_bytes": len(data)}
        metadata = {"file_name": "x.pdf", "size_bytes": len(data), "sha256": tool.hashlib.sha256(data).hexdigest(), "relative_path": "x.pdf"}
        found, reused = tool.resolve_sheet(client, [sheet], approved, metadata, Path("."))
        self.assertTrue(reused); self.assertEqual(found["id"], 4); self.assertEqual(client.calls, [("GET", "/api/technical-sheets/4/download")])

    def test_datasheet_hash_collision_and_duplicate_are_blocking(self):
        approved = self.approved(); metadata = {"file_name": "x.pdf", "size_bytes": 7, "sha256": "0" * 64, "relative_path": "x.pdf"}
        candidate = {"id": 1, "name": approved["datasheet_name"], "original_file_name": "x.pdf", "mime_type": "application/pdf", "size_bytes": 7}
        client = tool.LocalApiClient("http://localhost:5000", "x", True, Opener())
        with self.assertRaises(tool.SafeError): tool.resolve_sheet(client, [candidate, dict(candidate, id=2)], approved, metadata, ".")
        with self.assertRaises(tool.SafeError): tool.resolve_sheet(client, [dict(candidate, name="Other")], approved, metadata, ".")

    def test_rate_limit_configuration_is_read_from_repository(self):
        root = PATH.parents[2]
        self.assertEqual(tool.read_rate_limit(root), {"PermitLimit": 20, "WindowSeconds": 600})

    def test_rate_429_preserves_retry_after_without_sleep(self):
        class RateOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 429, "rate", Headers(values={"Retry-After": "17"}), None)
        client = tool.LocalApiClient("http://localhost:5000", "x", opener=RateOpener())
        with self.assertRaises(tool.RatePause) as caught: client.get_json("/api/technical-sheets")
        self.assertEqual(caught.exception.retry_after, 17); self.assertEqual(caught.exception.verdict, "PAUSED_RATE_LIMIT")

    def test_upload_limit_constants(self):
        self.assertEqual((tool.UPLOAD_LIMIT, tool.UPLOAD_WINDOW_SECONDS), (20, 600))
        self.assertEqual(tool.RatePause("PAUSED_UPLOAD_WINDOW", 600).retry_after, 600)

    def test_csv_bom_crlf_formula_and_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"; tool.write_csv(path, ["v"], [{"v": "=1+1"}, {"v": "S0607EⅡ"}])
            raw = path.read_bytes(); self.assertTrue(raw.startswith(b"\xef\xbb\xbf")); self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
            self.assertIn(b"'=1+1", raw); self.assertIn("Ⅱ", raw.decode("utf-8-sig"))

    def test_reports_are_exact_staged_and_secret_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"; tool.write_outputs(output, {"mode": "dry-run", "verdict": "DRY_RUN_APPROVED", "products": [], "datasheets": [], "actions": [], "errors": []})
            self.assertEqual({x.name for x in output.iterdir()}, set(tool.OUTPUT_NAMES))
            combined = b"".join(x.read_bytes() for x in output.iterdir()); self.assertNotIn(b"Authorization", combined); self.assertNotIn(b"Bearer", combined)

    def test_output_staging_cleanup_on_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"; output.mkdir(); (output / "keep").write_text("x")
            with self.assertRaises(tool.SafeError): tool.write_outputs(output, {"products": [], "datasheets": [], "actions": [], "errors": []})
            self.assertFalse(any(x.name.startswith(".enrichment-staging-") for x in Path(tmp).iterdir()))

    def test_no_destructive_or_out_of_scope_http(self):
        source = PATH.read_text(encoding="utf-8")
        self.assertNotIn('request("DELETE"', source); self.assertNotIn('request("PUT"', source)
        self.assertNotIn('POST", "/api/products"', source); self.assertNotIn('POST", "/api/product-images"', source)

    def test_redirect_handler_rejects(self):
        with self.assertRaises(tool.SafeError): tool.NoRedirect().redirect_request(None, None, 302, "", {}, "http://elsewhere")

    def test_unsafe_multipart_filename_rejected(self):
        client = tool.LocalApiClient("http://localhost:5000", "x", True, Opener())
        for name in ("../x.pdf", "a/b.pdf", 'a".pdf', "a\n.pdf"):
            with self.subTest(name=name), self.assertRaises(tool.SafeError): client.post_datasheet("n", name, b"x")


if __name__ == "__main__": unittest.main()
