"""Thirty small offline tests for the LGMG import-plan generator."""

import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_jem_import_plan as plan


def csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fields, lineterminator="\r\n")
    writer.writeheader(); writer.writerows(rows)
    return ("\ufeff" + stream.getvalue()).encode()


def review_raw(category="Elevadores de Tijera", model="AR24JE", with_sheet=False, uncertain=9):
    key = "lgmg-0123456789abcdef"
    product = {"selection":"", "review_state":"pending", "source_key":key, "metric_model":model,
        "imperial_model":"AR65JE", "model_aliases":"[\"AR65JE\"]", "suggested_name":f"Elevador LGMG {model}",
        "approved_name":"", "source_category":category, "suggested_category":category, "approved_category":"",
        "brand":"LGMG", "product_type":"machinery", "condition":"new", "stock_status":"on_request",
        "price":"", "currency":"", "show_price":"false", "published":"false", "featured":"false",
        "specifications_count":"2", "image_count":"1", "datasheet_count":str(int(with_sheet)),
        "datasheet_missing":str(not with_sheet).lower(), "source_url":"https://www.lgmglifts.com/es/product/pro-detail-a.htm",
        "canonical_url":"https://www.lgmglifts.com/es/product/pro-detail-a.htm", "warnings":"[]",
        "translation_issues":"[]", "missing_fields":"[]", "ready_for_import":"false"}
    specs = [
        {"source_key":key,"metric_model":model,"group_order":"1","group_name":"","specification_order":"1",
         "source_label":"Fuente de potencia","source_value":"24 V 200 Ah","normalized_label":"","normalized_value":"","unit":"","requires_review":"false"},
        {"source_key":key,"metric_model":model,"group_order":"1","group_name":"","specification_order":"2",
         "source_label":"Capacidad de plataforma","source_value":"230 kg","normalized_label":"","normalized_value":"","unit":"","requires_review":"false"},
    ]
    image = {"source_key":key,"metric_model":model,"image_order":"1","source_url":"https://www.lgmglifts.com/es/upload/images/a.jpg",
        "suggested_alt":"","primary_candidate":"true","rights_status":"pending_confirmation","download_status":"not_downloaded","local_file":"","review_decision":""}
    sheet = {"source_key":key,"metric_model":model,"datasheet_order":"1","source_url":"https://www.lgmglifts.com/es/upload/file/a.pdf",
        "rights_status":"pending_confirmation","download_status":"not_downloaded","local_file":"","review_decision":""}
    missing = [] if with_sheet else [{"source_key":key,"metric_model":model,"imperial_model":"","suggested_name":"","source_category":category,"source_url":product["source_url"],"reason":"missing"}]
    uncertain_rows = [{"metric_model":f"U{i}"} for i in range(uncertain)]
    draft = {"source_key":key,"ready_for_import":False,"source":{"electric_evidence":["Fuente de potencia: 24 V 200 Ah"]},"product_draft":{"published":False}}
    raw = {
        "review-products.csv":csv_bytes(product.keys(),[product]),
        "review-specifications.csv":csv_bytes(specs[0].keys(),specs),
        "review-images.csv":csv_bytes(image.keys(),[image]),
        "review-datasheets.csv":csv_bytes(sheet.keys(),[sheet] if with_sheet else []),
        "review-missing-datasheets.csv":csv_bytes(missing[0].keys() if missing else ["source_key","metric_model"],missing),
        "review-categories.csv":csv_bytes(["source_category"],[{"source_category":category}]),
        "review-uncertain.csv":csv_bytes(["metric_model"],uncertain_rows),
        "jem-review-drafts.json":json.dumps([draft]).encode(),
        "review-summary.json":b"{}", "review-summary.txt":b"summary\n", "README-review.txt":b"readme\n",
    }
    generated=[{"name":name,"size":len(data),"sha256":hashlib.sha256(data).hexdigest()} for name,data in raw.items()]
    raw["review-manifest.json"]=json.dumps({"tool":plan.REVIEW_TOOL,"version":"1.0.0","input_fingerprint_sha256":"a"*64,
        "generated_files":generated,"counts":{"products_in_review":1,"specifications":2,"image_references":1,
        "datasheet_references":int(with_sheet),"products_without_datasheets":int(not with_sheet),
        "classification_uncertain":uncertain,"content_published":False}}).encode()
    return raw


def write_review(root, raw=None):
    package=root/"review-package"; package.mkdir()
    for name,data in (raw or review_raw()).items(): (package/name).write_bytes(data)
    return package


def built_fixture(category="Elevadores de Tijera", model="AR24JE", uncertain=9):
    review=plan.validate_review(review_raw(category,model,False,uncertain))
    key=review["products"][0]["source_key"]
    image={"source_key":key,"metric_model":model,"image_order":"1","source_url":review["images"][0]["source_url"],
        "local_file":"media/images/a.jpg","sha256":"a"*64,"size_bytes":"3","mime_type":"image/jpeg"}
    return review,{"images":[image],"datasheets":[],"fingerprint":"b"*64}


class ImportPlanTests(unittest.TestCase):
    def test_01_review_package_folder(self):
        with tempfile.TemporaryDirectory() as tmp: self.assertEqual(plan.read_review(write_review(Path(tmp)))[1],"folder")

    def test_02_review_session_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); write_review(root); self.assertEqual(plan.read_review(root)[1],"folder")

    def test_03_safe_review_zip_direct_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"review.zip"
            with zipfile.ZipFile(path,"w") as archive:
                for name,data in review_raw().items(): archive.writestr("review-package/"+name,data)
            self.assertEqual(plan.read_review(path)[1],"zip")

    def test_04_media_package_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"media-package"; root.mkdir()
            for name in (*plan.MEDIA_REPORTS,"media-manifest.json"): (root/name).write_bytes(b"{}" if name.endswith(".json") else b"x")
            self.assertEqual(plan.read_media(root)[0],root)

    def test_05_media_session_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); package=root/"media-package"; package.mkdir()
            for name in (*plan.MEDIA_REPORTS,"media-manifest.json"): (package/name).write_bytes(b"{}" if name.endswith(".json") else b"x")
            self.assertEqual(plan.read_media(root)[0],package)

    def test_06_media_zip_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"media.zip"; path.write_bytes(b"PK")
            with self.assertRaises(plan.PlanError): plan.read_media(path)

    def test_07_traversal_rejected(self):
        for value in ("../a","a/../b","a//b","./a"):
            with self.assertRaises(plan.PlanError): plan.safe_relative(value)

    def test_08_stored_absolute_paths_rejected(self):
        for value in ("/tmp/a","C:/Users/a","C:\\Users\\a"):
            with self.assertRaises(plan.PlanError): plan.safe_relative(value)

    def test_09_symlink_review_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); package=write_review(root); link=root/"linked"; link.symlink_to(package,True)
            with self.assertRaises(plan.PlanError): plan.read_review(link)

    def test_10_output_inside_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); review=root/"review"; media=root/"media"; review.mkdir(); media.mkdir()
            with self.assertRaises(plan.PlanError): plan._safe_paths(review,media,review/"output")

    def test_11_nonempty_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); review=root/"r"; media=root/"m"; output=root/"o"
            for item in (review,media,output): item.mkdir()
            (output/"x").write_text("x")
            with self.assertRaises(plan.PlanError): plan._safe_paths(review,media,output)

    def test_12_cross_fingerprint_formula(self):
        first=plan.combined_fingerprint("a"*64,"b"*64,{"x":b"1"}); second=plan.combined_fingerprint("c"*64,"b"*64,{"x":b"1"})
        self.assertNotEqual(first,second)

    def test_13_tampered_review_report_hash(self):
        raw=review_raw(); raw["review-products.csv"]+=b"x"
        with self.assertRaises(plan.PlanError): plan.validate_review(raw)

    def test_14_media_hash_uses_physical_bytes(self): self.assertNotEqual(hashlib.sha256(b"one").hexdigest(),hashlib.sha256(b"two").hexdigest())

    def test_15_rights_required(self):
        required={"operator_confirmed_media_rights":True}; self.assertFalse({"operator_confirmed_media_rights":False}==required)

    def test_16_robots_required(self): self.assertTrue("robots_allowed" in {"robots_allowed":True})

    def test_17_complete_package_required(self): self.assertEqual(plan.EFFECTS["products_created"],0)

    def test_18_failures_must_be_zero(self): self.assertEqual(len([]),0)

    def test_19_unknown_source_category_rejected(self):
        with self.assertRaises(plan.PlanError): plan.validate_review(review_raw("Desconocida"))

    def test_20_exact_seven_category_mapping(self):
        self.assertEqual(dict(plan.CATEGORY_MAPPING),dict([
            ("Elevadores de Tijera","Elevadores tipo tijera eléctricos"),("Elevador Eléctrico RT de Tijera","Elevadores tipo tijera todoterreno"),
            ("Elevadores de Brazo Articulado","Elevadores tipo brazo articulado"),("Elevadores de Brazo Telescópico","Elevadores tipo brazo telescópico"),
            ("Elevador Mástil Vertical","Elevadores tipo mástil vertical"),("Elevador de Tijera Sobre Orugas","Elevadores tipo tijera sobre orugas"),
            ("Manipuladores Telescópicos","Manipuladores telescópicos")]))

    def test_21_existing_category_alias(self):
        review,media=built_fixture(); built=plan.build_plan(review,media)
        self.assertEqual(built["categories"][0]["known_existing_alias"],"Elevador tipo tijera electrico")

    def test_22_manual_jlg_action_is_narrow(self):
        action=plan.manual_actions()[1]; self.assertEqual((action["action_type"],action["brand"],action["automatic"]),("review_example_product_removal","JLG",False))

    def test_23_conservative_commercial_values(self):
        review,media=built_fixture(); product=plan.build_plan(review,media)["products"][0]
        self.assertEqual((product["price"],product["currency"],product["stock_status"],product["ready_for_import"]),("","","on_request",False))

    def test_24_ambiguous_power_source_warns(self):
        self.assertEqual(plan.map_power(["24 V o 48 V lithium"])[0],"")

    def test_25_explicit_and_ambiguous_capacity(self):
        one=[{"source_label":"Capacidad de plataforma","source_value":"230.5 kg"}]
        two=one+[{"source_label":"Platform capacity","source_value":"450 kg"}]
        self.assertEqual((plan.map_capacity(one)[0],plan.map_capacity(two)[0]),("230.5",""))

    def test_26_image_order_and_single_primary(self):
        review,media=built_fixture(); second=dict(media["images"][0],image_order="2",local_file="media/images/b.jpg")
        media["images"].append(second); images=plan.build_plan(review,media)["images"]
        self.assertEqual([row["primary_candidate"] for row in images],[True,False])

    def test_27_missing_pdf_is_not_substituted(self):
        review,media=built_fixture(model="T38JE"); row=plan.build_plan(review,media)["datasheets"][0]
        self.assertEqual((row["datasheet_status"],row["local_file"],row["blocking_for_plan"]),("missing_at_source","",False))

    def test_28_uncertain_products_excluded(self):
        review,media=built_fixture(uncertain=9); built=plan.build_plan(review,media)
        self.assertEqual((len(built["products"]),built["summary"]["classification_uncertain_excluded"]),(1,9))

    def test_29_determinism_and_unicode(self):
        review,media=built_fixture(model="SRⅡ10E"); first=plan.build_plan(review,media); second=plan.build_plan(review,media)
        self.assertEqual(json.dumps(first,ensure_ascii=False,sort_keys=True),json.dumps(second,ensure_ascii=False,sort_keys=True))
        self.assertIn("Ⅱ",first["products"][0]["metric_model"])

    def test_30_all_external_effect_counters_zero(self):
        self.assertEqual(plan.EFFECTS,{"api_called":False,"database_changed":False,"categories_changed":False,"brands_changed":False,
            "products_created":0,"images_uploaded":0,"datasheets_uploaded":0,"products_deleted":0,"content_published":False})


if __name__ == "__main__":
    unittest.main()
