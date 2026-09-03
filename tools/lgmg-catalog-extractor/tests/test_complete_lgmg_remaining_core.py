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
                         ("complete_lgmg_remaining_core", "1.0.3", "1.0", "core_products_with_primary_images"))
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

    def historical_sheet(self, **changes):
        sheet = {"id": 25, "name": core.PARTIAL_SHEET_NAME,
                 "original_file_name": core.PARTIAL_SHEET_ORIGINAL_FILENAME,
                 "content_type": "application/pdf", "size_bytes": 406080,
                 "file_url": "/technical-sheets/25/file",
                 "created_at": "2025-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
        sheet.update(changes)
        return sheet

    def validate_sheet(self, sheet, resource_id=25, allowed_product_ids=()):
        return core.validate_historical_sheet([sheet], resource_id, core.PARTIAL_SHEET_NAME,
                                              core.PARTIAL_SHEET_SHA256, core.PARTIAL_SHEET_SIZE,
                                              allowed_product_ids)

    def test_real_historical_sheet_dto_without_sha_or_product_is_accepted(self):
        sheet = self.historical_sheet()
        self.assertIs(self.validate_sheet(sheet), sheet)
        sheet["created_at"] = "different"; sheet["updated_at"] = None; sheet["product_id"] = None
        self.assertIs(self.validate_sheet(sheet), sheet)

    def test_exact_explicit_sha_and_proven_product_association_are_accepted(self):
        self.validate_sheet(self.historical_sheet(sha256=core.PARTIAL_SHEET_SHA256))
        self.validate_sheet(self.historical_sheet(product={"id": 91, "model": core.PARTIAL_MODEL}),
                            allowed_product_ids={91})

    def test_historical_sheet_reports_each_divergent_field(self):
        cases = (
            ({"id": 26}, "historical_sheet_id_mismatch"),
            ({"name": "another"}, "historical_sheet_name_mismatch"),
            ({"content_type": "text/plain"}, "historical_sheet_content_type_mismatch"),
            ({"size_bytes": 406081}, "historical_sheet_size_mismatch"),
            ({"file_url": "/technical-sheets/26/file"}, "historical_sheet_file_url_mismatch"),
            ({"sha256": "0" * 64}, "historical_sheet_explicit_sha256_mismatch"),
            ({"product_id": 91}, "historical_sheet_unexpected_product_association"),
        )
        for changes, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(core.ConflictError, diagnostic):
                self.validate_sheet(self.historical_sheet(**changes))

    def test_historical_sheet_requires_exact_canonical_original_filename(self):
        digest = core.PARTIAL_SHEET_SHA256
        invalid = ("0" * 64 + ".pdf", digest[:32] + ".pdf", digest + ".PDF",
                   digest.upper() + ".pdf", digest + "-copy.pdf", digest + ".pdf.bak")
        for filename in invalid:
            with self.subTest(filename=filename), self.assertRaisesRegex(
                    core.ConflictError, "historical_sheet_original_filename_mismatch"):
                self.validate_sheet(self.historical_sheet(original_file_name=filename))

    def test_historical_sheet_rejects_unsafe_or_noncanonical_urls(self):
        invalid = ("https://example.com/technical-sheets/25/file",
                   "/technical-sheets/25/file?download=1", "/technical-sheets/25/file#x",
                   "/technical-sheets/../25/file", "//user:password@example.com/technical-sheets/25/file")
        for file_url in invalid:
            with self.subTest(file_url=file_url), self.assertRaisesRegex(
                    core.ConflictError, "historical_sheet_file_url_mismatch"):
                self.validate_sheet(self.historical_sheet(file_url=file_url))

    def test_historical_sheet_id_is_supplied_from_checkpoint_derivation(self):
        self.validate_sheet(self.historical_sheet(id=73, file_url="/technical-sheets/73/file"), resource_id=73)
        with self.assertRaisesRegex(core.ConflictError, "historical_sheet_id_mismatch"):
            self.validate_sheet(self.historical_sheet(), resource_id=73)

    def test_apply_and_rollback_confirmations(self):
        base = dict(dry_run=False, verify=False, resume=False)
        with self.assertRaises(core.ConflictError): core.validate_cli(argparse.Namespace(**base, apply=True, rollback=False, confirm_apply=None, confirm_rollback=None))
        with self.assertRaises(core.ConflictError): core.validate_cli(argparse.Namespace(**base, apply=False, rollback=True, confirm_apply=None, confirm_rollback=None))

    def test_checkpoint_paths_must_be_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same"
            with self.assertRaises(core.ConflictError):
                core.run(path, path, path, path, Path(tmp) / "out", "http://localhost:1", path, "dry_run", "x")

    def test_reduced_checkpoint_version_1_0_0_is_rejected(self):
        legacy = {"tool": core.TOOL_NAME, "version": "1.0.0", "schema": core.CHECKPOINT_SCHEMA_VERSION,
                  "state": "core_dry_run_ready", "planned_operations": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"; path.write_text(json.dumps(legacy), encoding="utf-8")
            with self.assertRaisesRegex(core.ConflictError, "Checkpoint reducido incompatible"):
                core.read_core_checkpoint(path)

    def core_checkpoint(self, version="1.0.3"):
        operations = core.build_core_operations(fixture_data(), [decision(i) for i in range(34)], 25)
        value = core.new_checkpoint("http://localhost:5000", b"source", {"partial_sheet_id": 25},
                                    operations, {}, "f" * 64, fixture_data())
        value["version"] = version
        return value

    def partial_fixture(self, prefix):
        checkpoint = self.core_checkpoint()
        checkpoint["state"] = "core_apply_partial"
        checkpoint["completed_operations"] = []
        checkpoint["resources_created"] = {"products": [], "images": []}
        product_ids = {}
        for op in checkpoint["planned_operations"][:prefix]:
            resource_id = 1000 + op["operation_order"]
            record = {"operation_key": op["operation_key"], "operation_order": op["operation_order"],
                      "metric_model": op["metric_model"], "resource_type": op["resource_type"],
                      "resource_id": resource_id}
            checkpoint["completed_operations"].append(record)
            checkpoint["resources_created"][op["resource_type"] + "s"].append(
                {"id": resource_id, "metric_model": op["metric_model"]})
            if op["resource_type"] == "product": product_ids[op["operation_key"]] = resource_id
        checkpoint["external_effects"] = {"writes": prefix, "published": 0}
        checkpoint["next_operation"] = prefix + 1
        decisions, images = [], []
        for i, op in enumerate(checkpoint["planned_operations"][::2]):
            done = op["operation_key"] in {x["operation_key"] for x in checkpoint["completed_operations"]}
            product = {"id": product_ids[op["operation_key"]], "model": op["metric_model"],
                       "technical_sheet": op["request_template"]["technical_sheet"]} if done else None
            decisions.append({**decision(i), "status": "already_imported_exact" if done else "create_candidate",
                              "product": product})
        historical_products, historical_images = [], []
        for historical_index, model in enumerate(sorted(core.HISTORICAL_MODELS)):
            r = row(40); r.update(metric_model=model, approved_name="LGMG " + model)
            product_id, image_id = 800 + historical_index, 900 + historical_index
            decisions.append({"row": r, "payload": {}, "status": "already_imported_exact",
                              "product": {"id": product_id, "model": model}})
            historical_products.append({"resource_id": product_id, "metric_model": model})
            historical_images.append({"resource_id": image_id, "metric_model": model})
            images.append({"id": image_id, "product_id": product_id, "is_main": True, "order": 0})
        checkpoint["resources_historical"] = {"products": historical_products, "images": historical_images,
                                                "datasheets": [], "specifications": [], "partial_sheet_id": 25}
        by_key = {x["operation_key"]: x for x in checkpoint["completed_operations"]}
        for op in checkpoint["planned_operations"]:
            if op["resource_type"] == "image" and op["operation_key"] in by_key:
                images.append({"id": by_key[op["operation_key"]]["resource_id"],
                               "product": {"id": product_ids[op["depends_on_operation_key"]]},
                               "is_main": True, "order": 0})
        return checkpoint, decisions, {"images": images}

    def test_progress_snapshot_is_derived_for_multiple_prefixes(self):
        for prefix in (1, 2, 43, 67):
            checkpoint, decisions, state = self.partial_fixture(prefix)
            with self.subTest(prefix=prefix), mock.patch.object(core.base, "classify_products", return_value=decisions):
                self.assertIs(core.validate_progress_snapshot({}, state, {}, {}, checkpoint), decisions)

    def test_progress_checkpoint_rejects_noncanonical_accounting(self):
        for field, mutate, diagnostic in (
                ("gap", lambda x: x["completed_operations"].pop(1), "prefijo"),
                ("resource", lambda x: x["resources_created"]["products"].pop(), "resources_created"),
                ("effects", lambda x: x["external_effects"].__setitem__("writes", 1), "external_effects"),
                ("next", lambda x: x.__setitem__("next_operation", 2), "next_operation"),
                ("id", lambda x: x["completed_operations"][0].pop("resource_id"), "resource_id")):
            checkpoint, _, _ = self.partial_fixture(43)
            mutate(checkpoint)
            with self.subTest(field=field), self.assertRaisesRegex(core.ConflictError, diagnostic):
                core._validate_checkpoint_content(checkpoint)

    def test_progress_snapshot_rejects_missing_completed_and_unexpected_pending_resources(self):
        checkpoint, decisions, state = self.partial_fixture(43)
        completed_product = next(d for d in decisions if d["status"] == "already_imported_exact" and
                                 d["row"]["metric_model"] not in core.HISTORICAL_MODELS)
        completed_product["status"], completed_product["product"] = "create_candidate", None
        with mock.patch.object(core.base, "classify_products", return_value=decisions), self.assertRaisesRegex(
                core.ConflictError, "Producto completado"):
            core.validate_progress_snapshot({}, state, {}, {}, checkpoint)
        checkpoint, decisions, state = self.partial_fixture(43)
        pending = next(d for d in decisions if d["status"] == "create_candidate")
        pending["status"], pending["product"] = "already_imported_exact", {"id": 9999}
        with mock.patch.object(core.base, "classify_products", return_value=decisions), self.assertRaisesRegex(
                core.ConflictError, "Producto remoto inesperado"):
            core.validate_progress_snapshot({}, state, {}, {}, checkpoint)
        checkpoint, decisions, state = self.partial_fixture(43)
        dependency = checkpoint["completed_operations"][-1]["resource_id"]
        state["images"].append({"id": 9999, "product_id": dependency, "is_main": True, "order": 0})
        with mock.patch.object(core.base, "classify_products", return_value=decisions), self.assertRaisesRegex(
                core.ConflictError, "Imagen remota inesperada"):
            core.validate_progress_snapshot({}, state, {}, {}, checkpoint)

    def test_completed_image_requires_recorded_id_and_product_association(self):
        for mutation in (lambda image: image.__setitem__("id", 9999),
                         lambda image: image.__setitem__("product", {"id": 9999}),
                         lambda image: image.__setitem__("is_main", False)):
            checkpoint, decisions, state = self.partial_fixture(2)
            created_image = next(image for image in state["images"] if image["id"] == 1002)
            mutation(created_image)
            with mock.patch.object(core.base, "classify_products", return_value=decisions), self.assertRaisesRegex(
                    core.ConflictError, "Imagen completada"):
                core.validate_progress_snapshot({}, state, {}, {}, checkpoint)

    def test_checkpoint_reader_handles_physical_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            with self.assertRaisesRegex(core.ConflictError, "Checkpoint vacío o inválido"):
                core.read_core_checkpoint(path)
            for raw, diagnostic in ((b"", "Checkpoint vacío"), (b"{", "JSON inválido"),
                                    (b"{}", "Checkpoint vacío"), (b"[]", "Checkpoint vacío")):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaisesRegex(core.ConflictError, diagnostic): core.read_core_checkpoint(path)

    def test_current_checkpoint_is_loaded_and_semantically_validated(self):
        checkpoint = self.core_checkpoint()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"; core.atomic_checkpoint(path, checkpoint)
            loaded, legacy = core.read_core_checkpoint(path)
            self.assertFalse(legacy); self.assertEqual(loaded["planned_operations"], checkpoint["planned_operations"])
            for mutate, diagnostic in (
                    (lambda x: x["planned_operations"].pop(), "68 operaciones"),
                    (lambda x: x["planned_operations"].append(dict(x["planned_operations"][0])), "68 operaciones"),
                    (lambda x: x["operation_keys"].__setitem__(1, x["operation_keys"][0]), "operation_key"),
                    (lambda x: x["planned_operations"][1].__setitem__("depends_on_operation_key", "0" * 64), "Hash recalculable"),
                    (lambda x: x.__setitem__("planned_operations_fingerprint_sha256", "0" * 64), "Fingerprint")):
                candidate = json.loads(json.dumps(checkpoint)); mutate(candidate); core.atomic_checkpoint(path, candidate)
                with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(core.ConflictError, diagnostic):
                    core.read_core_checkpoint(path)

    def test_only_exact_approved_101_is_accepted_and_marked_for_migration(self):
        checkpoint = self.core_checkpoint("1.0.1")
        checkpoint.update({"human_approval": core.HUMAN_APPROVAL, "state": "core_dry_run_ready",
                           "source_checkpoint_sha256": core.SOURCE_SHA256, "source_checkpoint_size": core.SOURCE_SIZE,
                           "source_checkpoint_status": "superseded_by_core_completion",
                           "source_checkpoint_modified": False, "full_resume_authorized": False,
                           "partial_resume_fingerprint_sha256": core.PARTIAL_RESUME_FINGERPRINT,
                           "remote_dry_run_fingerprint_sha256": core.APPROVED_101_REMOTE_FINGERPRINT,
                           "planned_operations_fingerprint_sha256": core.APPROVED_101_PLAN_FINGERPRINT})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            raw = json.dumps(checkpoint, ensure_ascii=False).encode()
            raw += b" " * (core.APPROVED_101_SIZE - len(raw)); path.write_bytes(raw)
            with mock.patch.object(core, "operations_fingerprint", return_value=core.APPROVED_101_PLAN_FINGERPRINT):
                loaded, legacy = core.read_core_checkpoint(path, digest=lambda _: core.APPROVED_101_SHA256)
            self.assertTrue(legacy); self.assertEqual(len(loaded["planned_operations"]), 68)
            with self.assertRaisesRegex(core.ConflictError, "hash o tamaño"):
                core.read_core_checkpoint(path, digest=lambda _: "0" * 64)
            checkpoint["resources_created"]["products"].append({"id": 1}); raw = json.dumps(checkpoint).encode()
            path.write_bytes(raw + b" " * (core.APPROVED_101_SIZE - len(raw)))
            with mock.patch.object(core, "operations_fingerprint", return_value=core.APPROVED_101_PLAN_FINGERPRINT), self.assertRaisesRegex(core.ConflictError, "semánticamente"):
                core.read_core_checkpoint(path, digest=lambda _: core.APPROVED_101_SHA256)

    def test_public_main_classifies_apply_without_resume_and_loads_file(self):
        checkpoint = self.core_checkpoint()
        seen = {}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"; core.atomic_checkpoint(path, checkpoint)
            def fake_run(*args, **kwargs):
                seen["mode"], seen["resume"] = args[7], args[9]
                seen["checkpoint"], _ = core.read_core_checkpoint(args[6])
                return 0
            argv = []
            for flag in ("plan-input", "remaining-audit-input", "repaired-media-input", "source-checkpoint", "output-dir"):
                argv += ["--" + flag, str(Path(tmp) / flag)]
            argv += ["--api-base-url", "http://localhost:5000", "--checkpoint", str(path), "--apply",
                     "--confirm-apply", core.APPLY_CONFIRMATION]
            with mock.patch.object(core, "access_token", return_value="temporary"), mock.patch.object(core, "run", side_effect=fake_run):
                self.assertEqual(core.main(argv), 0)
            self.assertEqual((seen["mode"], seen["resume"]), ("apply", False))
            self.assertTrue(seen["checkpoint"]); self.assertEqual(len(seen["checkpoint"]["planned_operations"]), 68)

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
