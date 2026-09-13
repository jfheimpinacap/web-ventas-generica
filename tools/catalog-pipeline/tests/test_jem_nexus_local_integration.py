"""Level-1, fixture-only JEM Nexus importer certification; never opens a socket."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from catalog_acquisition.packaging import build_package, fingerprint, verify_package
from catalog_pipeline_common.serialization import canonical_bytes, content_fingerprint
from catalog_import import capture_snapshot, create_plan, main
from jem_nexus_import.authorization import AuthorizationError, fingerprint_without
from jem_nexus_import.checkpoint import initial, seal, validate
from jem_nexus_import.execution import (
    ExecutionError, execute, operation_set_fingerprint, persist_reconciliation,
    prepare_execution_bundle, reconcile_in_flight, validate_resume_snapshot,
)
from jem_nexus_import.output import write_output_set
from jem_nexus_import.package_input import read_verified_package
from jem_nexus_import.planning import simulate
from jem_nexus_import.snapshot import COLLECTIONS, semantic_fingerprint
from jem_nexus_import.verification import SnapshotObserver, verify_managed

CONTRACT = "c" * 64
BASE_URL = "http://localhost:2910"
SAFE = {"price": None, "price_visible": False, "is_featured": False, "is_published": False}
IMAGE_PRIMARY = b"\x89PNG\r\n\x1a\nfixture-primary"
IMAGE_SECONDARY = b"\x89PNG\r\n\x1a\nfixture-secondary"
SHEET = b"%PDF-1.4\nfixture technical sheet\n%%EOF\n"


def _asset(path, data, role, mime, ordinal=0):
    return {"entry_path": path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
            "mime": mime, "role": role, "ordinal": ordinal, "source_filename": pathlib.PurePosixPath(path).name}


def _package(directory):
    """Build the minimum synthetic package through the real canonical packager."""
    root = pathlib.Path(directory) / "fuente-sintetica"
    root.mkdir()
    product = {
        "schema_version": "1.0.0", "document_kind": "normalized_for_audit_not_api_payload",
        "canonical_identity": "equipo-sintetico-nino-1", "brand_code": "MARCA-SINTETICA",
        "supplier": "Proveedor Sintético", "canonical_model": "MODELO-FICTICIO-UNO",
        "category_mapping": {"name": "Categoría Física Sintética", "slug": "categoria-fisica-sintetica", "product_type": "machinery"},
        "structured_fields": {"condition": "new", "short_description": "Ensayo íntegramente sintético"},
        "product_specs": [{"key": "capacidad_fixture", "value": "200", "unit": "kg", "order": 0},
                          {"key": "altura_fixture", "value": "3", "unit": "m", "order": 1}],
        "media": [_asset("products/sintetico/primaria.png", IMAGE_PRIMARY, "primary", "image/png"),
                  _asset("products/sintetico/secundaria.png", IMAGE_SECONDARY, "secondary", "image/png", 1)],
        "technical_sheet": {**_asset("products/sintetico/ficha.pdf", SHEET, "technical_sheet", "application/pdf"), "name": "Ficha sintética"},
        "additional_documents": [], "commercial": dict(SAFE), "fixture_only": True,
    }
    files = {
        "products/sintetico/producto.json": canonical_bytes(product),
        "products/sintetico/primaria.png": IMAGE_PRIMARY,
        "products/sintetico/secundaria.png": IMAGE_SECONDARY,
        "products/sintetico/ficha.pdf": SHEET,
    }
    roles = {"products/sintetico/producto.json": "normalized_product", "products/sintetico/primaria.png": "primary",
             "products/sintetico/secundaria.png": "secondary", "products/sintetico/ficha.pdf": "technical_sheet"}
    entries = []
    for path, data in sorted(files.items()):
        local = root / pathlib.PurePosixPath(path).name
        local.write_bytes(data)
        entries.append({"path": path, "role": roles[path], "source_reference": local.name,
                        "source_sha256": hashlib.sha256(data).hexdigest(), "source_size": len(data),
                        "destination_sha256": hashlib.sha256(data).hexdigest(), "destination_size": len(data),
                        "mime": "application/json" if path.endswith("json") else ("image/png" if path.endswith("png") else "application/pdf"),
                        "product_identity": product["canonical_identity"]})
    policy = {"policy_version": "fixture-policy-v1", "fingerprint": "1" * 64}
    descriptors = [{"path": x["path"], "role": x["role"], "sha256": x["destination_sha256"], "size": x["destination_size"],
                    "mime": x["mime"], "product_identity": x["product_identity"]} for x in entries]
    plan = {"schema_version": "1.0.0", "package_schema_version": "1.0.0", "producer": "catalog-package",
            "package_policy": policy, "audit_manifest_fingerprint": "a" * 64, "included_products": [product["canonical_identity"]],
            "excluded_product_count": 0, "blocked_product_count": 0, "decision_fingerprint": "d" * 64,
            "entries": entries, "content_fingerprint": fingerprint({"entries": descriptors, "policy_fingerprint": policy["fingerprint"],
            "audit_fingerprint": "a" * 64, "decision_fingerprint": "d" * 64}), "entry_count": len(entries) + 1,
            "total_uncompressed_size": sum(map(len, files.values())), "blocking": False, "fixture_only": True,
            "source_root": ".", "upstream_fingerprints": {}}
    plan["plan_fingerprint"] = fingerprint(plan)
    package = pathlib.Path(directory) / "paquete-sintetico.zip"
    receipt = pathlib.Path(directory) / "recibo.json"
    build_package(plan, plan["plan_fingerprint"], package, root, receipt)
    return package, receipt, product


class _SyntheticBackend:
    """Stateful injected reader/mutator matching inspected JSON and multipart DTOs."""
    fixture_only = True

    def __init__(self, mode="observable_binary_fixture"):
        self.mode = mode
        self.collections = {name: [] for name in COLLECTIONS}
        self.collections["categories"] = [{"id": 1, "name": "Maquinarias", "slug": "maquinarias", "parent_id": None, "product_type": "machinery"}]
        self.collections["suppliers"] = [{"id": 2, "name": "Proveedor Sintético", "contact_name": "", "phone": "", "email": "", "notes": "", "is_active": True}]
        self.next_id = 10
        self.events = []
        self.posts = {}
        self.asset_bytes = {}
        self.fail_before = None
        self.lose_after = None

    def __call__(self, unused_url):
        return self

    def read_collection(self, name):
        self.events.append("read:" + name)
        values = copy.deepcopy(self.collections[name])
        if self.mode == "real_dto_shape" and name in ("product_images", "technical_sheets"):
            for value in values:
                value.pop("sha256", None)
                if name == "product_images": value["product"] = value.pop("product_id")
        if self.mode == "real_dto_shape" and name == "product_specs":
            for value in values:
                value["product"] = value.pop("product_id"); value["name"] = value.pop("key")
        return values

    def _commit(self, kind, payload, data=None):
        collection = {"category": "categories", "brand": "brands", "supplier": "suppliers", "product": "products",
                      "spec": "product_specs", "image": "product_images", "technical_sheet": "technical_sheets"}[kind]
        resource = {"id": self.next_id}
        self.next_id += 1
        resource.update(copy.deepcopy(payload))
        if kind == "image":
            resource["image"] = "/media/fixture-image.bin"
        if kind == "technical_sheet":
            resource.update({"original_file_name": "upload.pdf", "content_type": "application/pdf", "size_bytes": len(data),
                             "file_url": "/technical-sheets/%d/file" % resource["id"]})
        if data is not None:
            self.asset_bytes[(kind, resource["id"])] = data
        self.collections[collection].append(resource)
        return {"status": 201, "body": copy.deepcopy(resource)}

    def _dispatch(self, kind, payload, data=None):
        operation_id = self.current_operation
        if self.fail_before == operation_id:
            self.fail_before = None
            raise RuntimeError("fixture pre-dispatch failure")
        self.posts[operation_id] = self.posts.get(operation_id, 0) + 1
        self.events.append("post:" + operation_id)
        response = self._commit(kind, payload, data)
        if self.lose_after == operation_id:
            self.lose_after = None
            raise RuntimeError("fixture response lost")
        return response

    def post_json(self, kind, payload):
        return self._dispatch(kind, payload)

    def post_multipart(self, kind, fields, filename, mime, data, expected_hash, expected_size, request_fingerprint):
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_hash:
            raise AssertionError("asset integrity")
        return self._dispatch(kind, {**fields, "sha256": expected_hash}, data)


class _ObservableObserver(SnapshotObserver):
    def bytes_observable(self, kind):
        return kind in ("image", "technical_sheet")


class _Harness:
    def __init__(self, directory, mode="observable_binary_fixture"):
        self.root = pathlib.Path(directory)
        self.package, self.receipt, self.product = _package(directory)
        self.backend = _SyntheticBackend(mode)
        self.policy = {"schema_version": "1.0.0", "rules_version": "fixture-policy-v1", "contract_fingerprint": CONTRACT,
                       "supplier_optional": False, "package_policy": {}}
        self.baseline = capture_snapshot(self.backend, CONTRACT, "fixture_only")
        self.snapshot_path = self.root / "snapshot.json"
        self.policy_path = self.root / "policy.json"
        self.snapshot_path.write_bytes(canonical_bytes(self.baseline))
        self.policy_path.write_bytes(canonical_bytes(self.policy))
        self.plan = create_plan(self.package, self.receipt, self.snapshot_path, self.policy_path)
        self.dry = simulate(self.plan)
        self.view = read_verified_package(self.package, self.receipt, {}, verify_package)
        target = content_fingerprint({"schema_version": "jem-local-target-v1", "rules_version": "jem-import-safety-v1",
                                      "target": {"scheme": "http", "host": "localhost", "port": 2910}})
        expected = {"package_sha256": self.view["verification"]["zip_sha256"], "plan_fingerprint": self.plan["plan_fingerprint"],
                    "dry_run_fingerprint": self.dry["dry_run_fingerprint"], "snapshot_fingerprint": self.baseline["semantic_fingerprint"],
                    "contract_fingerprint": CONTRACT, "policy_fingerprint": self.plan["inputs"]["import_policy_fingerprint"],
                    "operation_set_fingerprint": operation_set_fingerprint(self.plan["operations"]), "operation_count": len(self.plan["operations"]),
                    "allowed_operation_kinds": sorted({x["kind"] for x in self.plan["operations"]}), "target_fingerprint": target}
        self.authorization = {"schema_version": "1.0.0", "rules_version": "jem-local-apply-v1", "classification": "fixture_only",
                              "fixture_only": True, "local_only": True, "production_allowed": False, "publication_allowed": False,
                              "allow_apply": True, "allow_resume": True, "allow_verify": True, **expected, "authorization_fingerprint": ""}
        self.authorization["authorization_fingerprint"] = fingerprint_without(self.authorization, "authorization_fingerprint")
        self.bundle = prepare_execution_bundle(self.view, self.plan, self.dry, self.baseline, self.policy, self.authorization, target)
        self.persisted = []

    def execute(self, checkpoint=None):
        def persist(value):
            self.persisted.append(copy.deepcopy(value))
            if value.get("in_flight"):
                self.backend.current_operation = value["in_flight"]["operation_id"]
        return execute(self.bundle, self.backend, persist, checkpoint)

    def updated_snapshot(self):
        return capture_snapshot(self.backend, CONTRACT, "fixture_only")


class JemNexusLocalIntegrationTests(unittest.TestCase):
    def test_001_complete_package_reaches_verified_with_observable_binaries(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); cp = h.execute(); report = verify_managed(h.plan, cp, _ObservableObserver(h.updated_snapshot()))
            self.assertEqual("verified", report["result"]); self.assertEqual("local_apply_verified", {**cp, "state": "local_apply_verified"}["state"])

    def test_002_real_dto_shape_requires_manual_binary_verification(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d, "real_dto_shape"); cp = h.execute(); report = verify_managed(h.plan, cp, SnapshotObserver(h.updated_snapshot()))
            self.assertEqual("manual_verification_required", report["result"]); self.assertEqual("local_apply_completed_pending_verify", cp["state"])

    def test_003_topological_order_is_exact(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); operations = h.plan["operations"]
            roots = sorted((x for x in operations if x["kind"] in ("brand", "category")), key=lambda x: x["operation_id"])
            product = next(x for x in operations if x["kind"] == "product")
            children = sorted((x for x in operations if x["kind"] not in ("brand", "category", "product")), key=lambda x: x["operation_id"])
            self.assertEqual([x["operation_id"] for x in roots + [product] + children], [x["operation_id"] for x in operations])

    def test_004_real_bindings_are_propagated(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); cp = h.execute(); product = h.backend.collections["products"][0]
            brand_id = h.backend.collections["brands"][0]["id"]; category_id = next(x["id"] for x in h.backend.collections["categories"] if x["slug"] != "maquinarias")
            self.assertEqual((brand_id, category_id, 2), (product["brand_id"], product["category_id"], product["supplier_id"])); self.assertEqual(3, len(cp["produced_bindings"]))

    def test_005_safe_commercial_defaults_reach_backend(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); h.execute(); self.assertEqual(SAFE, {k: h.backend.collections["products"][0][k] for k in SAFE})

    def test_006_image_bytes_are_intact(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); h.execute(); self.assertEqual([IMAGE_PRIMARY, IMAGE_SECONDARY], [v for (k, unused), v in h.backend.asset_bytes.items() if k == "image"])

    def test_007_pdf_bytes_are_intact(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); h.execute(); self.assertEqual(SHEET, next(v for (k, unused), v in h.backend.asset_bytes.items() if k == "technical_sheet"))

    def test_008_final_checkpoint_and_receipts_are_exact(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); cp = h.execute(); self.assertEqual((8, 8, None, 8), (cp["next_operation"], len(cp["receipts"]), cp["in_flight"], cp["counters"]["mutations_confirmed"])); validate(cp)

    def test_009_cli_apply_local_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); self.assertEqual(0, self._cli(h, "apply-local")); self.assertTrue((h.root / "out" / "local-apply-manifest.json").is_file())

    def test_010_cli_resume_reconciled_returns_exact_zero(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); op = h.plan["operations"][0]["operation_id"]; h.backend.lose_after = op
            with self.assertRaises(RuntimeError): h.execute()
            self._write_inputs(h); (h.root / "out").mkdir(); (h.root / "out" / "local-apply-checkpoint.json").write_bytes(canonical_bytes(h.persisted[-1])); (h.root / "out" / "local-operation-receipts.jsonl").write_bytes(b"")
            self.assertEqual(0, self._cli(h, "resume-local", write=False)); self.assertEqual(1, h.backend.posts[op])

    def test_011_cli_verify_observable_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); cp = h.execute(); self._write_inputs(h); (h.root / "checkpoint.json").write_bytes(canonical_bytes(cp))
            code = main(["verify-local", "--plan", str(h.root / "plan.json"), "--checkpoint", str(h.root / "checkpoint.json"), "--base-url", BASE_URL, "--output", str(h.root / "verify")], reader_factory=h.backend, observer_factory=_ObservableObserver)
            self.assertEqual(0, code); self.assertEqual("local_apply_verified", json.loads((h.root / "local-apply-checkpoint.json").read_text(encoding="utf-8"))["state"])

    def test_012_fixture_only_without_injected_mutator_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d)
            with mock.patch("catalog_import.sys.stdout", mock.Mock()):
                self.assertEqual(2, self._cli(h, "apply-local", mutator=False))

    def test_013_fresh_snapshot_and_preflight_precede_mutator(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); events = h.backend.events
            def factory(bundle): events.append("mutator"); self.assertTrue((h.root / "out" / "local-apply-preflight.json").is_file()); return h.backend
            self.assertEqual(0, self._cli(h, "apply-local", factory=factory)); self.assertLess(max(i for i, x in enumerate(events) if x.startswith("read:")), events.index("mutator"))

    def test_014_pre_dispatch_failure_confirms_no_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); op = h.plan["operations"][0]["operation_id"]; h.backend.fail_before = op
            with self.assertRaises(RuntimeError): h.execute()
            self.assertEqual({}, h.backend.posts); self.assertEqual([], h.backend.collections["brands"])

    def test_015_lost_response_preserves_in_flight(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); h.backend.lose_after = h.plan["operations"][0]["operation_id"]
            with self.assertRaises(RuntimeError): h.execute()
            self.assertIsNotNone(h.persisted[-1]["in_flight"]); self.assertEqual("local_apply_reconciliation_required", h.persisted[-1]["state"])

    def test_016_resume_reconciles_without_second_post(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); op = h.plan["operations"][0]["operation_id"]; h.backend.lose_after = op
            with self.assertRaises(RuntimeError): h.execute()
            cp = h.persisted[-1]; current = h.updated_snapshot(); validate_resume_snapshot(h.bundle, cp, h.baseline, current)
            cp = persist_reconciliation(h.bundle, cp, reconcile_in_flight(h.bundle, cp, current), lambda x: None); h.execute(cp)
            self.assertEqual(1, h.backend.posts[op]); self.assertEqual("snapshot_reconciliation", cp["receipts"][0]["confirmation_source"])

    def test_017_absent_in_flight_resource_blocks_without_retry(self): self._assert_blocked_resume("absent", "IN_FLIGHT_ABSENT")
    def test_018_divergent_in_flight_resource_blocks_without_retry(self): self._assert_blocked_resume("divergent", "IN_FLIGHT_DIVERGENT")
    def test_019_duplicate_in_flight_resource_blocks_without_retry(self): self._assert_blocked_resume("duplicate", "IN_FLIGHT_AMBIGUOUS")

    def test_020_persistence_failure_prevents_next_operation(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); calls = []
            def fail_after_receipt(value):
                calls.append(copy.deepcopy(value))
                if value["receipts"]: raise OSError("fixture persistence failure")
                if value.get("in_flight"): h.backend.current_operation = value["in_flight"]["operation_id"]
            with self.assertRaises(OSError): execute(h.bundle, h.backend, fail_after_receipt)
            self.assertEqual(1, sum(h.backend.posts.values())); self.assertEqual(1, len(calls[-1]["receipts"]))

    def test_021_missing_managed_resource_fails_verify(self): self._assert_verify_mutation("missing", "verification_failed")
    def test_022_divergent_managed_resource_fails_verify(self): self._assert_verify_mutation("divergent", "verification_failed")
    def test_023_duplicate_managed_resource_fails_verify(self): self._assert_verify_mutation("duplicate", "verification_failed")
    def test_024_unobservable_binary_is_manual(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d, "real_dto_shape"); cp = h.execute(); self.assertGreater(len(verify_managed(h.plan, cp, SnapshotObserver(h.updated_snapshot()))["manual_verification_operation_ids"]), 0)

    def test_025_repeated_verify_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); cp = h.execute(); snapshot = h.updated_snapshot(); first = verify_managed(h.plan, cp, _ObservableObserver(snapshot)); second = verify_managed(h.plan, cp, _ObservableObserver(snapshot)); self.assertEqual(first, second)

    def test_026_fake_has_no_network_or_concrete_transport(self):
        source = pathlib.Path(__file__).read_text(encoding="utf-8", errors="strict")
        forbidden = ("import " + "socket", "jem_nexus_local_" + "transport import", "jem_nexus_local_mutation_" + "transport import")
        self.assertEqual([], [value for value in forbidden if value in source])

    def test_027_fixture_uses_no_tokens_or_environment(self):
        source = pathlib.Path(__file__).read_text(encoding="utf-8", errors="strict")
        self.assertEqual([], [value for value in ("os." + "environ", "Bear" + "er ") if value in source]); self.assertTrue(_SyntheticBackend.fixture_only)

    def test_028_unicode_and_paths_are_windows_safe(self):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); h.execute(); encoded = canonical_bytes(h.backend.collections["products"][0]); self.assertIn("sintético".encode("utf-8"), encoded); self.assertNotIn(b"\\", encoded)

    def test_029_identical_inputs_have_identical_fingerprints_and_artifacts(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left, right = _Harness(a), _Harness(b); self.assertEqual(left.plan["plan_fingerprint"], right.plan["plan_fingerprint"]); self.assertEqual(left.dry, right.dry); self.assertEqual(left.package.read_bytes(), right.package.read_bytes())

    def test_030_cli_keeps_exactly_six_commands_and_no_unsafe_flag(self):
        from catalog_import import parser
        choices = next(action.choices for action in parser()._actions if getattr(action, "choices", None))
        self.assertEqual({"snapshot-local", "plan", "dry-run", "apply-local", "resume-local", "verify-local"}, set(choices)); self.assertNotIn("--production", parser().format_help())

    def _write_inputs(self, h):
        for name, value in (("plan.json", h.plan), ("dry.json", h.dry), ("authorization.json", h.authorization)):
            (h.root / name).write_bytes(canonical_bytes(value))

    def _cli(self, h, command, write=True, factory=None, mutator=True):
        if write: self._write_inputs(h)
        args = [command, "--package", str(h.package), "--receipt", str(h.receipt), "--plan", str(h.root / "plan.json"),
                "--dry-run-manifest", str(h.root / "dry.json"), "--snapshot", str(h.snapshot_path), "--policy", str(h.policy_path),
                "--authorization", str(h.root / "authorization.json"), "--base-url", BASE_URL, "--checkpoint-dir", str(h.root / "out"),
                "--confirm-plan-fingerprint", h.plan["plan_fingerprint"], "--confirm-dry-run-fingerprint", h.dry["dry_run_fingerprint"]]
        return main(args, reader_factory=h.backend, mutator_factory=(factory or (lambda bundle: h.backend)) if mutator else None)

    def _assert_blocked_resume(self, variant, code):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); op = h.plan["operations"][0]["operation_id"]; h.backend.lose_after = op
            with self.assertRaises(RuntimeError): h.execute()
            if variant == "absent": h.backend.collections["brands"].clear()
            elif variant == "divergent": h.backend.collections["brands"][0]["name"] = "Divergente"
            else: h.backend.collections["brands"].append({**h.backend.collections["brands"][0], "id": 99})
            result = reconcile_in_flight(h.bundle, h.persisted[-1], h.updated_snapshot()); posts = dict(h.backend.posts)
            with self.assertRaisesRegex(ExecutionError, code): persist_reconciliation(h.bundle, h.persisted[-1], result, lambda x: None)
            self.assertEqual(posts, h.backend.posts)

    def _assert_verify_mutation(self, variant, result):
        with tempfile.TemporaryDirectory() as d:
            h = _Harness(d); cp = h.execute(); collection = h.backend.collections["brands"]
            if variant == "missing": collection.clear()
            elif variant == "divergent": collection[0]["slug"] = "otro"
            else: collection.append(copy.deepcopy(collection[0]))
            self.assertEqual(result, verify_managed(h.plan, cp, _ObservableObserver(h.updated_snapshot()))["result"])


if __name__ == "__main__":
    unittest.main()
