"""Pruebas sintéticas de la auditoría; no usan red, API ni paquetes reales."""

import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).parents[1] / "audit_lgmg_scissors_technical_data.py"
SPEC = importlib.util.spec_from_file_location("technical_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(audit)


class TechnicalAuditTests(unittest.TestCase):
    def product(self):
        item = dict(audit.closed_catalog()[0]); item.update(maximum_load_capacity_kg="230", target_power_source="electric_24v")
        return item

    @staticmethod
    def spec(label, value, unit="", order="1", capacity=""):
        return {"source_label": label, "source_value": value, "unit": unit,
            "specification_order": order, "maximum_load_capacity_candidate_kg": capacity}

    def test_closed_table_matches_canonicalizer_and_preserves_provenance(self):
        catalog = audit.closed_catalog()
        self.assertEqual(len(catalog), 21)
        self.assertEqual(catalog[0]["source_model"], "S0607E-2")
        changed = [r for r in catalog if r["source_model"] != r["target_model"]]
        self.assertEqual(len(changed), 12)
        self.assertTrue(all("Ⅱ" in r["source_model"] and "Ⅱ" not in r["target_model"] for r in changed))
        self.assertTrue(all(r["target_name"] == f"Elevador tipo tijera eléctrico LGMG {r['target_model']}" for r in catalog))

    def test_selection_by_exact_model_and_source_key_excludes_others(self):
        rows = [{"metric_model": r["source_model"], "source_key": r["source_key"], "source_category": audit.SOURCE_CATEGORY} for r in audit.closed_catalog()]
        rows.extend({"metric_model": f"OTHER{i}", "source_key": f"other-{i}", "source_category": "Otra"} for i in range(36))
        selected = audit.select_products(rows)
        self.assertEqual(len(selected), 21); self.assertFalse(any(r["source_key"].startswith("other") for r in selected))

    def test_selection_rejects_missing_duplicate_key_wrong_model_and_family(self):
        base = [{"metric_model": r["source_model"], "source_key": r["source_key"], "source_category": audit.SOURCE_CATEGORY} for r in audit.closed_catalog()]
        mutations = [base[:-1], base + [dict(base[0])], [dict(r) for r in base], [dict(r) for r in base]]
        mutations[2][0]["metric_model"] = "S0607E"
        mutations[3][0]["source_category"] = "Otra familia"
        for rows in mutations:
            with self.subTest(rows=len(rows)), self.assertRaises(audit.AuditError): audit.select_products(rows)

    def test_working_height_metric_and_rejections(self):
        product = self.product()
        result, _, _ = audit.field_analysis(product, [self.spec("Altura máxima de trabajo", "9,8 m")])
        self.assertEqual(result["WorkingHeightM"], ("9.8", "safe_candidate"))
        for label, value in (("Maximum working height", "32 ft"), ("Altura de plataforma", "7.8 m")):
            result, _, _ = audit.field_analysis(product, [self.spec(label, value)])
            self.assertEqual(result["WorkingHeightM"][0], "")

    def test_machine_weight_metric_and_rejections(self):
        product = self.product()
        result, _, _ = audit.field_analysis(product, [self.spec("Peso de la máquina", "1580 kg")])
        self.assertEqual(result["MachineWeightKg"][0], "1580")
        for label, value in (("Machine weight", "3500 lbs"), ("Peso de la batería", "30 kg")):
            result, _, _ = audit.field_analysis(product, [self.spec(label, value)])
            self.assertEqual(result["MachineWeightKg"][0], "")

    def test_capacity_valid_and_ambiguous(self):
        product = self.product()
        good = self.spec("Capacidad de plataforma", "230 kg", "kg", capacity="230")
        result, rows, _ = audit.field_analysis(product, [good])
        self.assertEqual(result["MaximumLoadCapacityKg"], ("230", "safe_candidate"))
        self.assertTrue(any(r["source_value"] == "230 kg" for r in rows))
        product["maximum_load_capacity_kg"] = ""
        result, _, _ = audit.field_analysis(product, [good])
        self.assertEqual(result["MaximumLoadCapacityKg"][1], "manual_review")

    def test_power_representable_and_nonrepresentable(self):
        source = self.spec("Fuente de potencia", "24 V")
        result, _, _ = audit.field_analysis(self.product(), [source])
        self.assertEqual(result["PowerSource"], ("electric_24v", "representable_candidate"))
        product = self.product(); product["target_power_source"] = ""
        source["source_value"] = "48 V"
        result, _, warnings = audit.field_analysis(product, [source])
        self.assertEqual(result["PowerSource"][0], ""); self.assertTrue(warnings)

    def test_terrain_year_and_hours_are_not_inferred(self):
        result, _, _ = audit.field_analysis(self.product(), [])
        self.assertEqual(result["TerrainType"], ("", "manual_review"))
        self.assertEqual(result["Year"], ("", "not_provided"))
        self.assertEqual(result["HoursMeter"], ("", "not_provided_not_applicable"))
        result, _, _ = audit.field_analysis(self.product(), [self.spec("Terrain type", "Outdoor"), self.spec("Manufacturing year", "2025", order="2")])
        self.assertEqual(result["TerrainType"][0], "outdoor"); self.assertEqual(result["Year"][0], "2025")

    def test_ambiguous_metric_values_are_manual(self):
        specs = [self.spec("Machine weight", "1000 kg", order="1"), self.spec("Machine weight", "1100 kg", order="2")]
        result, _, _ = audit.field_analysis(self.product(), specs)
        self.assertEqual(result["MachineWeightKg"], ("", "manual_review"))

    def test_safe_relative_rejects_traversal_absolute_and_backslash(self):
        for value in ("../x.pdf", "/x.pdf", "C:/x.pdf", "a\\x.pdf"):
            with self.subTest(value=value), self.assertRaises(audit.AuditError): audit.safe_relative(value)

    def test_pdf_available_shared_hash_and_invalid_signature(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); data = b"%PDF-1.7\nsynthetic"
            path = root / "files/a.pdf"; path.parent.mkdir(); path.write_bytes(data)
            catalog = audit.closed_catalog()[:2]
            selected = [{**r} for r in catalog]
            plan_rows = [{"source_key": r["source_key"], "metric_model": r["source_model"], "datasheet_order": "1",
                "datasheet_status": "available_at_source", "local_file": "files/a.pdf", "sha256": audit.sha(data),
                "size_bytes": str(len(data)), "mime_type": "application/pdf"} for r in selected]
            media_row = {"local_file": "files/a.pdf", "sha256": audit.sha(data), "size_bytes": str(len(data)), "mime_type": "application/pdf"}
            downloads = [{**media_row, "source_key": r["source_key"], "datasheet_order": "1"} for r in selected]
            result = audit.validate_datasheets(selected, {"rows": {"import-datasheets.csv": plan_rows}},
                {"rows": {"media-files.csv": [media_row], "downloaded-datasheets.csv": downloads}}, root)
            self.assertEqual(len(result), 2); self.assertTrue(all(r["products_sharing_physical_file"] == 2 for r in result))
            path.write_bytes(b"not pdf" + data)
            with self.assertRaises(audit.AuditError): audit.validate_datasheets(selected, {"rows": {"import-datasheets.csv": plan_rows}},
                {"rows": {"media-files.csv": [media_row], "downloaded-datasheets.csv": downloads}}, root)

    def test_pdf_hash_mime_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target = root / "a.pdf"; target.write_bytes(b"%PDF-x")
            link = root / "link.pdf"
            try: link.symlink_to(target)
            except OSError: self.skipTest("symlinks unavailable")
            row = {"source_key": self.product()["source_key"], "metric_model": self.product()["source_model"],
                "datasheet_order": "1", "datasheet_status": "available_at_source", "local_file": "link.pdf",
                "sha256": audit.sha(target.read_bytes()), "size_bytes": str(target.stat().st_size), "mime_type": "application/pdf"}
            with self.assertRaises(audit.AuditError): audit.validate_datasheets([self.product()], {"rows": {"import-datasheets.csv": [row]}},
                {"rows": {"media-files.csv": [], "downloaded-datasheets.csv": []}}, root)

    def test_csv_formula_bom_crlf_and_unicode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"
            audit.write_csv(path, ["value"], [{"value": "=SUM(1,2)"}, {"value": "S0607EⅡ"}])
            data = path.read_bytes(); self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\n", data.replace(b"\r\n", b"")); self.assertIn(b"'=SUM", data)
            self.assertIn("Ⅱ", data.decode("utf-8-sig"))

    def test_cli_has_only_three_local_arguments_and_static_no_network(self):
        options = {action.dest for action in audit.build_parser()._actions}
        self.assertEqual(options, {"help", "plan_input", "media_input", "output_dir"})
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("import requests", "import socket", "import urllib", "JEM_NEXUS_ACCESS_TOKEN", '"--apply"', '"--publish"'):
            self.assertNotIn(forbidden, source)

    def test_effects_all_zero_or_false(self):
        self.assertEqual(set(audit.EFFECTS), {"network_used", "api_called", "database_modified", "input_files_modified",
            "files_copied", "products_created", "products_updated", "products_deleted", "specifications_created",
            "datasheets_uploaded", "content_published", "apply_supported", "ready_for_update", "human_review_required"})
        self.assertTrue(audit.EFFECTS["human_review_required"])
        self.assertFalse(any(v for k, v in audit.EFFECTS.items() if k != "human_review_required"))
        self.assertEqual(len(audit.OUTPUT_NAMES), 9)

    def test_deterministic_analysis(self):
        specs = [self.spec("Altura máxima de trabajo", "9.8 m")]
        first = audit.field_analysis(self.product(), specs)
        second = audit.field_analysis(self.product(), specs)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_output_staging_cleanup_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            with self.assertRaises(Exception):
                audit.run(Path(temporary) / "missing-plan", Path(temporary) / "missing-media", output, created_at="2026-01-01T00:00:00+00:00")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
