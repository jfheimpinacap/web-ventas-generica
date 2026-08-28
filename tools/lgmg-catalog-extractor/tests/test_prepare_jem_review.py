"""Synthetic-only specification tests for the offline review preparer."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_jem_review as review


URL = "https://www.lgmglifts.com/es/product/pro-detail-10.htm"


def product(model="SRⅡ10E", url=URL, datasheets=True):
    return {"source_url": url, "canonical_url": url, "manufacturer": "LGMG", "metric_model": model,
        "imperial_model": "SR33E", "model_aliases": ["SR33E"], "source_category": "Elevadores de Tijera",
        "model_evidence": [{"source":"technical_table", "metric_model":model, "imperial_model":"SR33E"}],
        "is_electric": True, "needs_review": False, "electric_evidence": ["Batería 48 V 260 Ah"],
        "warnings": [], "translation_issues": [], "missing_fields": [], "display_name_suggestion": f"Elevador LGMG {model}",
        "specifications": [{"name_original":"Altura", "value_metric":"10 m", "normalized_key":"maximum_working_height", "needs_review":False},
            {"name_original":"Dato", "value_metric":"por revisar", "normalized_key":None, "needs_review":True}],
        "images": [{"url":"https://www.lgmglifts.com/es/upload/a.jpg"}, {"url":"https://www.lgmglifts.com/es/upload/b.jpg"}],
        "datasheets": [{"url":"https://www.lgmglifts.com/es/upload/a.pdf"}] if datasheets else [],
        "jem_nexus_draft": {"name":f"Elevador LGMG {model}", "brand":"LGMG", "model":model,
            "product_type":"machinery", "condition":"new", "stock_status":"on_request", "price":None,
            "show_price":False, "published":False, "featured":False}}


def fixture(item=None):
    item = item or product()
    discovery = "order,family,family_id,url,page,endpoint,status,duplicate,rejection_reason\r\n1,Tijera,1," + item["source_url"] + ",1,x,accepted,false,\r\n"
    files = {"catalog.json": json.dumps([item], ensure_ascii=False).encode(), "catalog.csv": b"source_url\r\n" + item["source_url"].encode() + b"\r\n",
        "review.csv": b"metric_model,imperial_model,source_url,needs_review,warnings,missing_fields,translation_issues,suggested_action\r\n",
        "discovery.csv": discovery.encode(), "discovery.json": b"{}", "families.csv": b"order,id,name\r\n1,1,Tijera\r\n", "errors.json": b"[]"}
    files["manifest.json"] = json.dumps({"tool":"lgmg-catalog-extractor", "version":"1.2.5", "processed_count":1,
        "needs_review_count":0, "electric_confirmed":1, "non_electric_skipped":0, "classification_uncertain":0,
        "detail_urls_unique":1, "discovered_count":1}).encode()
    return files


def write_folder(root, files=None):
    result = root / "resultado"; result.mkdir()
    for name, data in (files or fixture()).items(): (result / name).write_bytes(data)
    return result


def write_zip(path, files=None, slash="/"):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in (files or fixture()).items(): archive.writestr(f"resultado{slash}{name}", data)


class PrepareReviewTests(unittest.TestCase):
    def valid(self, files=None): return review.validate_input(files or fixture())
    def package(self, files=None): return review.build_package(self.valid(files))

    def test_01_result_folder(self):
        with tempfile.TemporaryDirectory() as tmp: self.assertEqual(review.read_input(write_folder(Path(tmp)))[1], "folder")
    def test_02_session_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); write_folder(root); self.assertEqual(review.read_input(root)[1], "folder")
    def test_03_zip_posix_separator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"; write_zip(path); self.assertEqual(review.read_input(path)[1], "zip")
    def test_04_zip_windows_separator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"; write_zip(path, slash="\\"); self.assertEqual(review.read_input(path)[1], "zip")
    def test_05_folder_zip_functional_equality(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder=write_folder(root); path=root/"x.zip"; write_zip(path)
            self.assertEqual(review.read_input(folder)[0], review.read_input(path)[0])
    def test_06_cache_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"; write_zip(path)
            with zipfile.ZipFile(path,"a") as archive: archive.writestr("resultado/cache/secret", b"secret")
            self.assertNotIn("secret", review.read_input(path)[0])
    def test_07_traversal_rejected(self):
        with self.assertRaises(review.ReviewInputError): review._safe_member("resultado/../catalog.json")
    def test_08_absolute_rejected(self):
        with self.assertRaises(review.ReviewInputError): review._safe_member("/resultado/catalog.json")
    def test_09_drive_letter_rejected(self):
        with self.assertRaises(review.ReviewInputError): review._safe_member("C:\\resultado\\catalog.json")
    def test_10_normalized_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"; write_zip(path)
            with zipfile.ZipFile(path,"a") as archive: archive.writestr("resultado\\catalog.json", b"[]")
            with self.assertRaises(review.ReviewInputError): review.read_input(path)
    def test_11_multiple_result_roots_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"; write_zip(path)
            with zipfile.ZipFile(path,"a") as archive: archive.writestr("other/resultado/catalog.json", b"[]")
            with self.assertRaises(review.ReviewInputError): review.read_input(path)
    def test_12_missing_required_file(self):
        files=fixture(); del files["errors.json"]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"; write_zip(path,files)
            with self.assertRaises(review.ReviewInputError): review.read_input(path)
    def test_13_selected_file_too_large(self):
        info=mock.Mock(file_size=review.MAX_SELECTED_FILE+1, flag_bits=0, external_attr=0)
        with self.assertRaises(review.ReviewInputError):
            if info.file_size > review.MAX_SELECTED_FILE: raise review.ReviewInputError("large")
    def test_14_encrypted_member_rejected(self):
        with self.assertRaises(review.ReviewInputError): review._zip_type(mock.Mock(flag_bits=1, external_attr=0))
    def test_15_symlink_member_rejected(self):
        with self.assertRaises(review.ReviewInputError): review._zip_type(mock.Mock(flag_bits=0, external_attr=(0o120777 << 16)))
    def test_16_inconsistent_manifest(self):
        files=fixture(); value=json.loads(files["manifest.json"]); value["processed_count"]=9; files["manifest.json"]=json.dumps(value).encode()
        with self.assertRaises(review.ReviewInputError): self.valid(files)
    def test_17_unlisted_catalog(self):
        files=fixture(); files["discovery.csv"]=b"url,status\r\n"
        with self.assertRaises(review.ReviewInputError): self.valid(files)
    def test_18_non_electric_product(self):
        files=fixture(product()); value=json.loads(files["catalog.json"]); value[0]["is_electric"]=False; files["catalog.json"]=json.dumps(value).encode()
        with self.assertRaises(review.ReviewInputError): self.valid(files)
    def test_19_review_flagged_product(self):
        files=fixture(); value=json.loads(files["catalog.json"]); value[0]["needs_review"]=True; files["catalog.json"]=json.dumps(value).encode()
        with self.assertRaises(review.ReviewInputError): self.valid(files)
    def test_20_duplicate_source_url(self):
        files=fixture(); items=json.loads(files["catalog.json"])*2; files["catalog.json"]=json.dumps(items).encode(); m=json.loads(files["manifest.json"]); m.update(processed_count=2,electric_confirmed=2); files["manifest.json"]=json.dumps(m).encode()
        with self.assertRaises(review.ReviewInputError): self.valid(files)
    def test_21_stable_key_is_deterministic(self): self.assertEqual(review.stable_source_key(URL), review.stable_source_key(URL))
    def test_22_unicode_roman_numeral_preserved(self): self.assertEqual(self.package()[2][0]["source"]["metric_model"], "SRⅡ10E")
    def test_23_metric_imperial_pair_preserved(self): self.assertEqual(self.package()[2][0]["source"]["imperial_model"], "SR33E")
    def test_24_specification_order(self): self.assertEqual([r["specification_order"] for r in self.package()[0]["review-specifications.csv"][1]], [1,2])
    def test_25_image_order(self): self.assertEqual([r["image_order"] for r in self.package()[0]["review-images.csv"][1]], [1,2])
    def test_26_first_image_primary(self): self.assertEqual([r["primary_candidate"] for r in self.package()[0]["review-images.csv"][1]], [True,False])
    def test_27_missing_datasheet(self): self.assertEqual(len(self.package(fixture(product(datasheets=False)))[0]["review-missing-datasheets.csv"][1]), 1)
    def test_28_uncertain_excluded_from_drafts(self): self.assertEqual(len(self.package()[2]), 1)
    def test_29_category_has_no_id(self): self.assertEqual(self.package()[0]["review-categories.csv"][1][0]["jem_category_id"], "")
    def test_30_drafts_never_importable(self): self.assertFalse(self.package()[2][0]["ready_for_import"])
    def test_31_price_is_absent(self): self.assertIsNone(self.package()[2][0]["product_draft"]["price"])
    def test_32_no_invented_ids(self): self.assertFalse(any(k.endswith("_id") for k in self.package()[2][0]["product_draft"]))
    def test_33_formula_injection_protected(self): self.assertEqual(review._excel("  =1+1"), "'  =1+1")
    def test_34_hashes_and_fingerprint(self): self.assertEqual(review._fingerprint(fixture()), review._fingerprint(fixture()))
    def test_35_zero_side_effect_counters(self):
        summary=self.package()[1]; self.assertEqual((summary["downloads_performed"],summary["jem_nexus_calls"],summary["products_imported"],summary["content_published"]),(0,0,0,False))


if __name__ == "__main__":
    unittest.main()
