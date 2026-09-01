import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("remaining_audit", HERE / "audit_lgmg_remaining_catalog.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class RemainingAuditTests(unittest.TestCase):
    def products(self):
        pairs = audit.model_source_keys()
        rows = [{"source_key": key, "metric_model": model, "source_category": "Elevadores de Tijera"}
                for model, key in pairs]
        for family_index, family in enumerate(audit.FAMILIES):
            for index in range(6):
                model = ("AR24JE" if family_index == 1 and index == 0 else
                         "T38JE" if family_index == 2 and index == 0 else f"M{family_index}{index}Ⅱ")
                rows.append({"source_key": f"lgmg-r{family_index}{index:014d}", "metric_model": model,
                    "source_category": family, "proposed_name": "=source name"})
        return rows

    def test_cli_has_exactly_three_required_options(self):
        with self.assertRaises(SystemExit): audit.parse_args([])
        parsed = audit.parse_args(["--plan-input", "p", "--media-input", "m", "--output-dir", "o"])
        self.assertEqual(vars(parsed), {"plan_input": "p", "media_input": "m", "output_dir": "o"})
        with self.assertRaises(SystemExit): audit.parse_args(["--plan-input", "p", "--media-input", "m", "--output-dir", "o", "--extra"])

    def test_static_offline_surface(self):
        source = (HERE / "audit_lgmg_remaining_catalog.py").read_text(encoding="utf-8")
        for forbidden in ("import urllib", "import requests", "import socket", "JEM_NEXUS_ACCESS_TOKEN", "--" + "apply", "--" + "publish", "api-base-url"):
            self.assertNotIn(forbidden, source)

    def test_approved_fingerprints_are_exact_and_non_null(self):
        self.assertEqual(audit.APPROVED_PLAN_FINGERPRINT, "75d68378dcd7bf77b19f9c7f0e60806085deaecadf2b7fa70e3102812be4bcb7")
        self.assertEqual(audit.APPROVED_MEDIA_FINGERPRINT, "b16d7f40250cc9b7a1b4affe029d0a87bba4355968e289fdab99ddbb4d656c9b")

    def test_counts_and_outputs_are_closed(self):
        self.assertEqual(list(audit.EXPECTED_COUNTS.values()), [57, 1635, 127, 57, 7, 1, 44, 7])
        self.assertEqual(len(audit.OUTPUT_NAMES), 9)
        self.assertEqual(len(set(audit.OUTPUT_NAMES)), 9)

    def test_closed_cohort_is_read_from_existing_constant(self):
        pairs = audit.model_source_keys()
        self.assertEqual(len(pairs), 21)
        source = (HERE / "audit_lgmg_remaining_catalog.py").read_text(encoding="utf-8")
        self.assertIn('"MODEL_SOURCE_KEYS"', source)
        self.assertNotIn(pairs[0][1], source)

    def test_exact_pair_split_is_21_plus_36_and_ordered(self):
        rows = self.products(); scope, processed, remaining = audit.split_scope(rows)
        self.assertEqual((len(processed), len(remaining), len(scope)), (21, 36, 57))
        self.assertEqual([r["source_key"] for r in scope], [r["source_key"] for r in rows])
        self.assertEqual({r["source_category"] for r in remaining}, set(audit.FAMILIES))

    def test_name_or_model_alone_does_not_match(self):
        rows = self.products(); rows[0]["source_key"] = "lgmg-wrong00000000000"
        with self.assertRaisesRegex(audit.AuditError, "cohorte cerrada"):
            audit.split_scope(rows)

    def test_all_six_category_mappings_and_names_are_exact(self):
        self.assertEqual(audit.FAMILIES["Elevador Mástil Vertical"][0], "Elevadores tipo mástil vertical")
        self.assertEqual(audit.FAMILIES["Manipuladores Telescópicos"][1], "Manipulador telescópico eléctrico LGMG")
        for family, (subcategory, prefix) in audit.FAMILIES.items():
            self.assertTrue(subcategory and prefix.endswith("LGMG"), family)

    def test_unicode_model_is_not_normalized(self):
        model = "S0812EⅡ-sufijo"
        prefix = audit.FAMILIES["Elevador Mástil Vertical"][1]
        self.assertEqual(f"{prefix} {model}".split()[-1], model)

    def test_approval_key_and_aggregate_are_deterministic(self):
        row = {"source_key": "k", "source_category": "f", "metric_model": "MⅡ",
            "proposed_target_subcategory": "s", "proposed_target_model": "MⅡ", "proposed_target_name": "n"}
        media = {"primary": ("x.jpg", "1" * 64, 3, "image/jpeg"), "datasheet": ("", "", "", ""), "datasheet_status": "missing_at_source"}
        first = audit.approval_key(row, media, "p", "m")
        self.assertEqual(first, audit.approval_key(dict(reversed(list(row.items()))), media, "p", "m"))
        self.assertEqual(len(first), 64)
        self.assertEqual(audit.sha(audit.canonical([first])), audit.sha(audit.canonical([first])))

    def test_image_and_pdf_signatures(self):
        valid = [(b"\xff\xd8\xffx", "image/jpeg", ".jpg", "image"),
            (b"\x89PNG\r\n\x1a\n", "image/png", ".png", "image"),
            (b"RIFF1234WEBP", "image/webp", ".webp", "image"), (b"%PDF-1.7", "application/pdf", ".pdf", "datasheet")]
        for args in valid: audit._validate_signature(*args)
        with self.assertRaises(audit.AuditError): audit._validate_signature(b"GIF", "image/jpeg", ".jpg", "image")
        with self.assertRaises(audit.AuditError): audit._validate_signature(b"not pdf", "application/pdf", ".pdf", "datasheet")

    def test_only_known_missing_datasheets(self):
        self.assertEqual(audit.MISSING_DATASHEETS, {"AR24JE", "T38JE"})

    def test_formula_protection_and_csv_wire_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.csv"
            audit.write_csv(path, ("value",), [{"value": "=1+1"}, {"value": "Ⅱ"}])
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf")); self.assertIn(b"\r\n", data)
            self.assertIn(b"'=1+1", data); self.assertIn("Ⅱ".encode(), data)

    def test_safe_relative_rejects_traversal_absolute_drive_and_backslash(self):
        for value in ("../x", "/x", "C:/x", "a\\b", "a/./b", ""):
            with self.subTest(value=value), self.assertRaises(audit.AuditError): audit.safe_relative(value)
        self.assertEqual(audit.safe_relative("media/images/a.jpg"), "media/images/a.jpg")

    def test_paths_reject_symlinks_overlap_and_nonempty_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = root / "plan"; media = root / "media"; out = root / "out"
            plan.mkdir(); media.mkdir(); out.mkdir(); (out / "occupied").write_text("x")
            with self.assertRaises(audit.AuditError): audit.safe_paths(plan, media, out)
            (out / "occupied").unlink(); audit.safe_paths(plan, media, out)
            with self.assertRaises(audit.AuditError): audit.safe_paths(plan, media, plan / "nested")
            link = root / "link"; link.symlink_to(plan, target_is_directory=True)
            with self.assertRaises(audit.AuditError): audit.safe_paths(link, media, out)

    def test_manifest_effect_contract_is_zero(self):
        source = (HERE / "audit_lgmg_remaining_catalog.py").read_text(encoding="utf-8")
        for literal in ('"network_called": False', '"api_called": False', '"database_modified": False',
                '"products_created": 0', '"images_uploaded": 0', '"credentials_persisted": False'):
            self.assertIn(literal, source)

    def test_staging_is_cleaned_when_writer_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"; output.mkdir()
            with self.assertRaises(Exception): audit.write_outputs(output, {}, {}, {}, "fixed")
            self.assertEqual(list(output.iterdir()), [])

    def test_hardened_media_findings_cover_mismatch_size_and_shared_files(self):
        records = [
            {"metric_model": "SR1018E-2", "datasheet": {"sha256": "d" * 64,
                "size_bytes": 100, "filename": "SR0818E-2.pdf", "text": "Ficha SR0818E-2"},
                "images": [{"sha256": "i" * 64, "filename": "sr1018e.jpg", "is_primary": True}]},
            {"metric_model": "SR0818E-2", "datasheet": {"sha256": "d" * 64,
                "size_bytes": 100, "filename": "SR0818E-2.pdf", "text": "Ficha SR0818E-2"},
                "images": [{"sha256": "x" * 64, "filename": "sr0818e.jpg", "is_primary": True}]},
            {"metric_model": "H625E", "datasheet": {"sha256": "h" * 64,
                "size_bytes": audit.MAX_DATASHEET_BYTES + 1, "filename": "H625E.pdf", "text": "Ficha H625E"},
                "images": [{"sha256": "h" * 64, "filename": "h625e.jpg", "is_primary": True}]},
        ]
        findings = audit.analyze_media_findings(records)
        self.assertIn("datasheet_model_mismatch", findings["SR1018E-2"])
        self.assertIn("datasheet_shared_across_products", findings["SR1018E-2"])
        self.assertIn("datasheet_exceeds_backend_limit", findings["H625E"])

    def test_all_images_shared_and_primary_filename_other_model_require_review(self):
        records = [
            {"metric_model": "A13JE", "datasheet": {}, "images": [
                {"sha256": "1" * 64, "filename": "a13je.jpg", "is_primary": True},
                {"sha256": "2" * 64, "filename": "shared.jpg", "is_primary": False}]},
            {"metric_model": "A14JE", "datasheet": {}, "images": [
                {"sha256": "1" * 64, "filename": "a13je.jpg", "is_primary": True},
                {"sha256": "2" * 64, "filename": "shared.jpg", "is_primary": False}]},
        ]
        findings = audit.analyze_media_findings(records)
        self.assertIn("all_images_shared_across_products", findings["A13JE"])
        self.assertIn("all_images_shared_across_products", findings["A14JE"])
        self.assertIn("primary_filename_mentions_other_model", findings["A14JE"])

    def test_shared_secondary_only_does_not_block(self):
        records = [
            {"metric_model": "A13JE", "datasheet": {}, "images": [
                {"sha256": "1" * 64, "filename": "a13je.jpg", "is_primary": True},
                {"sha256": "s" * 64, "filename": "shared.jpg", "is_primary": False}]},
            {"metric_model": "A14JE", "datasheet": {}, "images": [
                {"sha256": "2" * 64, "filename": "a14je.jpg", "is_primary": True},
                {"sha256": "s" * 64, "filename": "shared.jpg", "is_primary": False}]},
        ]
        findings = audit.analyze_media_findings(records)
        self.assertNotIn("all_images_shared_across_products", findings["A13JE"])
        self.assertNotIn("all_images_shared_across_products", findings["A14JE"])


if __name__ == "__main__":
    unittest.main()
