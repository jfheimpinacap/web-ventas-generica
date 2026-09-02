"""Pruebas sintéticas de la finalización reducida LGMG."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PATH = Path(__file__).parents[1] / "complete_lgmg_remaining_core.py"
SPEC = importlib.util.spec_from_file_location("complete_lgmg_remaining_core", PATH)
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


def row(index):
    model = core.PARTIAL_MODEL if index == 2 else f"M{index:02d}"
    return {"source_order": index + 1, "source_key": f"source-{index}", "approval_key": f"approval-{index}",
            "metric_model": model, "approved_name": f"LGMG {model}", "approved_family": core.base.FAMILIES[index % 6]}


def decision(index):
    r = row(index)
    return {"row": r, "status": "create_candidate", "product": None,
            "payload": {"name": r["approved_name"], "model": r["metric_model"], "category": index % 6 + 1,
                        "brand": 8, "technical_sheet": None, "price": None, "price_visible": False,
                        "is_published": False, "is_featured": False}}


def fixture_data():
    images = {}
    for i in range(34):
        model = row(i)["metric_model"]
        images[model] = [{"metric_model": model, "is_primary": "true", "sha256": f"{i:064x}",
                          "size_bytes": "12", "relative_path": f"images/{model}.jpg", "original_filename": f"{model}.jpg"}]
    return {"images": images, "fingerprints": dict(core.base.APPROVED_FINGERPRINTS)}


class CoreCompletionTests(unittest.TestCase):
    def test_contract_and_safe_import(self):
        self.assertEqual((core.TOOL_NAME, core.TOOL_VERSION, core.CHECKPOINT_SCHEMA_VERSION, core.COMPLETION_PROFILE),
                         ("complete_lgmg_remaining_core", "1.0.0", "1.0", "core_products_with_primary_images"))
        self.assertIs(core.RequestCoordinator, core.base.RateLimitCoordinator)
        self.assertIs(core.ApiClient, core.base.ApiClient)

    def test_cli_is_closed_and_modes_are_exclusive(self):
        parser = core.build_parser()
        self.assertEqual({x.dest for x in parser._actions if x.dest != "help"},
            {"plan_input", "remaining_audit_input", "repaired_media_input", "source_checkpoint", "output_dir",
             "api_base_url", "checkpoint", "dry_run", "apply", "verify", "rollback", "resume", "confirm_apply", "confirm_rollback"})
        with self.assertRaises(SystemExit): parser.parse_args(["--dry-run", "--apply"])
        args = argparse.Namespace(dry_run=True, apply=False, verify=False, rollback=False, resume=True,
                                  confirm_apply=None, confirm_rollback=None)
        with self.assertRaises(core.ConflictError): core.validate_cli(args)

    def test_token_only_from_environment_and_not_argument(self):
        self.assertEqual(core.access_token({core.TOKEN_ENV: "secret"}), "secret")
        with self.assertRaises(core.ConflictError): core.access_token({})
        self.assertNotIn("token", {x.dest for x in core.build_parser()._actions})

    def test_origin_is_strictly_local_with_explicit_port(self):
        self.assertEqual(core.normalize_origin("http://localhost:8000"), "http://localhost:8000")
        self.assertEqual(core.normalize_origin("http://127.0.0.1:5000"), "http://127.0.0.1:5000")
        for value in ("https://localhost:8000", "http://localhost", "http://example.com:80", "http://u:p@localhost:1", "http://localhost:1/x"):
            with self.subTest(value=value), self.assertRaises(core.ConflictError): core.normalize_origin(value)

    def test_plan_is_exact_deterministic_and_reuses_one_sheet(self):
        data = fixture_data(); missing = [decision(i) for i in range(34)]
        first = core.build_core_operations(data, missing, 25)
        second = core.build_core_operations(data, missing, 25)
        self.assertEqual(first, second)
        self.assertEqual(core.operations_fingerprint(first), core.operations_fingerprint(second))
        self.assertEqual(len(first), 68)
        self.assertEqual([sum(x["batch"] == b and x["resource_type"] == "product" for x in first) for b in (1, 2)], [20, 14])
        self.assertEqual(sum(x["resource_type"] == "product" for x in first), 34)
        self.assertEqual(sum(x["resource_type"] == "image" for x in first), 34)
        self.assertFalse(any(x["resource_type"] in {"specification", "datasheet"} for x in first))
        products = {x["metric_model"]: x for x in first if x["resource_type"] == "product"}
        self.assertEqual(products[core.PARTIAL_MODEL]["request_template"]["technical_sheet"], 25)
        self.assertTrue(all(x["request_template"]["technical_sheet"] is None for m, x in products.items() if m != core.PARTIAL_MODEL))
        for image in first[1::2]:
            self.assertLess(next(x["operation_order"] for x in first if x["operation_key"] == image["depends_on_operation_key"]), image["operation_order"])

    def test_invalid_image_cardinality_is_rejected(self):
        data = fixture_data(); data["images"][row(0)["metric_model"]] = []
        with self.assertRaises(core.ConflictError): core.build_core_operations(data, [decision(i) for i in range(34)], 25)

    def test_source_checkpoint_hash_and_size_checked_before_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"; path.write_bytes(b"{}")
            before = path.read_bytes()
            with self.assertRaises(core.ConflictError): core.validate_source_checkpoint(path)
            self.assertEqual(path.read_bytes(), before)

    def test_source_checkpoint_synthetic_contract_and_historical_derivation(self):
        planned, completed = [], []
        kinds = (["product"] * 2 + ["image"] * 2 + ["datasheet"] * 2 + ["specification"] * 58 + ["datasheet"])
        for i in range(1197):
            key = core.PARTIAL_SHEET_KEY if i == 64 else f"{i + 1:064x}"
            model = ("SR0818E-2" if i == 0 else "SR1018E-2" if i == 1 else core.PARTIAL_MODEL if i == 64 else "X")
            op = {"operation_key": key, "metric_model": model}
            if i == 64: op.update({"request_template": {"name": core.PARTIAL_SHEET_NAME}, "file_sha256": core.PARTIAL_SHEET_SHA256, "file_size_bytes": core.PARTIAL_SHEET_SIZE})
            planned.append(op)
            if i < 65: completed.append({"operation_key": key, "metric_model": model, "resource_type": kinds[i], "resource_id": 25 if i == 64 else i + 1})
        value = {"version": "2.1.1", "state": "apply_partial", "planned_operations": planned, "completed_operations": completed}
        raw = json.dumps(value, separators=(",", ":")).encode()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"; path.write_bytes(raw)
            _, unchanged, historical = core.validate_source_checkpoint(path, expected_sha256=core.sha(raw), expected_size=len(raw))
            self.assertEqual(unchanged, raw); self.assertEqual(historical["partial_sheet_id"], 25)
            self.assertEqual([len(historical[k]) for k in ("products", "images", "datasheets", "specifications")], [2, 2, 3, 58])

    def test_apply_and_rollback_confirmations(self):
        base = dict(dry_run=False, verify=False, resume=False)
        with self.assertRaises(core.ConflictError): core.validate_cli(argparse.Namespace(**base, apply=True, rollback=False, confirm_apply=None, confirm_rollback=None))
        with self.assertRaises(core.ConflictError): core.validate_cli(argparse.Namespace(**base, apply=False, rollback=True, confirm_apply=None, confirm_rollback=None))

    def test_checkpoint_paths_must_be_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same"
            with self.assertRaises(core.ConflictError):
                core.run(path, path, path, path, Path(tmp) / "out", "http://localhost:1", path, "dry_run", "x")

    def test_outputs_are_exact_bom_crlf_formula_safe_and_secret_free(self):
        data = fixture_data(); decisions = [decision(i) for i in range(34)]
        for model in core.HISTORICAL_MODELS:
            i = len(decisions); r = row(i); r["metric_model"] = model; r["approved_name"] = "=" + model
            decisions.append({"row": r, "payload": {"category": 1, "brand": 8}, "status": "already_imported_exact", "product": {"id": i}})
        operations = core.build_core_operations(data, decisions[:34], 25)
        cp = {"completed_operations": [], "resources_created": {"products": [], "images": []},
              "resources_historical": {"products": [], "images": [], "datasheets": [], "specifications": []}}
        report = core.report_data(data, decisions, operations, cp, "CORE_DRY_RUN_READY")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"; core.write_outputs(out, report)
            self.assertEqual({x.name for x in out.iterdir()}, set(core.OUTPUT_NAMES))
            raw = (out / "core-products.csv").read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf")); self.assertIn(b"\r\n", raw); self.assertIn(b"'=SR", raw)
            self.assertEqual(len((out / "core-operations.csv").read_text(encoding="utf-8-sig").splitlines()) - 1, 68)

    def test_secret_scanner(self):
        for raw in (b"Authorization: x", b"Bearer abc", b"eyJabc.def.ghi", b"password=x"):
            with self.assertRaises(core.ConflictError): core._secret_free(raw)

    def test_stop_on_first_failure_and_resume_skip_are_explicit(self):
        source = PATH.read_text(encoding="utf-8")
        self.assertIn("if op[\"operation_key\"] in done: continue", source)
        self.assertIn("core_apply_partial", source)
        self.assertIn("for kind, endpoint in ((\"images\", \"product-images\"), (\"products\", \"products\"))", source)
        self.assertNotIn("technical-sheets/{int(resource", source)

    def test_no_secret_is_serialized_in_checkpoint(self):
        operations = core.build_core_operations(fixture_data(), [decision(i) for i in range(34)], 25)
        cp = core.new_checkpoint("http://localhost:1", b"source", {"partial_sheet_id": 25}, operations, {}, "f" * 64, fixture_data())
        text = json.dumps(cp)
        self.assertNotIn("Bearer", text); self.assertNotIn("Authorization", text); self.assertNotIn("secret", text)


if __name__ == "__main__":
    unittest.main()
