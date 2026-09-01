import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repair_remaining_media", HERE / "repair_lgmg_remaining_media.py")
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def decisions(decision="pending_human_visual_review", sr_url="", t_url=""):
    return {"schema_version": "1.0", "catalog_approval": {"approved": True, "approval_text": repair.APPROVAL_TEXT},
        "datasheet_repairs": {
            "SR1018E-2": {"action": "replace_from_official_source", "product_page_url": repair.OFFICIAL_PAGES["SR1018E-2"],
                "datasheet_url": sr_url, "expected_model_markers": repair.EXPECTED_MODEL_MARKERS["SR1018E-2"]},
            "T28JE": {"action": "replace_from_official_source", "product_page_url": repair.OFFICIAL_PAGES["T28JE"],
                "datasheet_url": t_url, "expected_model_markers": repair.EXPECTED_MODEL_MARKERS["T28JE"]},
            "H625E": {"action": "exclude_backend_size_limit", "maximum_backend_size_bytes": repair.MAX_DATASHEET_BYTES}},
        "shared_image_decisions": {"A13JE|A14JE": {"decision": decision, "notes": "revisión Ⅱ",
            **({"approved_images": repair.APPROVED_SEPARATE_IMAGES} if decision == "approve_separate_model_images" else {})}}}


def pdf(model=None):
    text = f"BT ({model}) Tj ET\n".encode() if model else b""
    return b"%PDF-1.7\n" + text + b"%%EOF\n"


class Response(io.BytesIO):
    status = 200
    def __init__(self, data, url="https://www.lgmglifts.com/upload/right.pdf", mime="application/pdf"):
        super().__init__(data); self._url=url; self.headers={"Content-Type": mime, "Content-Length": str(len(data))}
    def geturl(self): return self._url
    def getcode(self): return self.status


class Fetcher:
    def __init__(self, response): self.response=response; self.calls=[]
    def open(self, url): self.calls.append(url); return self.response


class RepairRemainingMediaTests(unittest.TestCase):
    def test_cli_has_exactly_five_required_arguments(self):
        with self.assertRaises(SystemExit): repair.parse_args([])
        argv = ["--plan-input", "p", "--media-input", "m", "--remaining-audit-input", "a", "--decisions-input", "d", "--output-dir", "o"]
        self.assertEqual(vars(repair.parse_args(argv)), {"plan_input":"p", "media_input":"m", "remaining_audit_input":"a", "decisions_input":"d", "output_dir":"o"})
        for forbidden in ("--apply", "--publish", "--api-base-url", "--token", "--backend", "--database"):
            with self.assertRaises(SystemExit): repair.parse_args(argv + [forbidden])

    def test_fingerprints_and_closed_outputs(self):
        self.assertEqual(repair.audit_contract.APPROVED_PLAN_FINGERPRINT, "75d68378dcd7bf77b19f9c7f0e60806085deaecadf2b7fa70e3102812be4bcb7")
        self.assertEqual(repair.audit_contract.APPROVED_MEDIA_FINGERPRINT, "b16d7f40250cc9b7a1b4affe029d0a87bba4355968e289fdab99ddbb4d656c9b")
        self.assertEqual(len(repair.OUTPUT_NAMES), 11); self.assertEqual(len(set(repair.OUTPUT_NAMES)), 11)

    def test_decision_approval_is_literal_and_visual_values_closed(self):
        for value in repair.VISUAL_DECISIONS:
            self.assertEqual(repair.validate_decisions(json.dumps(decisions(value)).encode())["shared_image_decisions"]["A13JE|A14JE"]["decision"], value)
        bad = decisions(); bad["catalog_approval"]["approval_text"] += "!"
        with self.assertRaises(repair.RepairError): repair.validate_decisions(json.dumps(bad).encode())

    def test_separate_decision_contract_is_exact_and_fail_closed(self):
        good = decisions("approve_separate_model_images", repair.OFFICIAL_DATASHEETS["SR1018E-2"], repair.OFFICIAL_DATASHEETS["T28JE"])
        self.assertEqual(repair.validate_decisions(json.dumps(good).encode())["shared_image_decisions"]["A13JE|A14JE"]["approved_images"], repair.APPROVED_SEPARATE_IMAGES)
        mutations = []
        for mutate in (lambda x: x["shared_image_decisions"]["A13JE|A14JE"]["approved_images"].pop("A14JE"),
                lambda x: x["shared_image_decisions"]["A13JE|A14JE"]["approved_images"].update({"X": {}}),
                lambda x: x["shared_image_decisions"]["A13JE|A14JE"]["approved_images"]["A13JE"].update(primary_sha256="x"*64),
                lambda x: x["shared_image_decisions"]["A13JE|A14JE"]["approved_images"]["A13JE"]["ordered_sha256"].append(repair.APPROVED_SEPARATE_IMAGES["A13JE"]["ordered_sha256"][0]),
                lambda x: x["shared_image_decisions"]["A13JE|A14JE"]["approved_images"]["A14JE"]["ordered_sha256"].reverse()):
            value = json.loads(json.dumps(good)); mutate(value); mutations.append(value)
        for value in mutations:
            with self.assertRaises(repair.RepairError): repair.validate_decisions(json.dumps(value).encode())

    def test_exact_official_urls_and_alias_markers(self):
        value = decisions("pending_human_visual_review", *repair.OFFICIAL_DATASHEETS.values())
        repair.validate_decisions(json.dumps(value).encode())
        value["datasheet_repairs"]["T28JE"]["datasheet_url"] = "https://www.lgmglifts.com/other.pdf"
        with self.assertRaises(repair.RepairError): repair.validate_decisions(json.dumps(value).encode())
        self.assertEqual(repair.validate_pdf(pdf("T92JE"), "application/pdf", "T28JE",
            expected_markers=repair.EXPECTED_MODEL_MARKERS["T28JE"])[0], "validated_model_content")

    def test_separate_associations_preserve_bytes_and_other_products(self):
        rows=[]
        for model, hashes in (("A13JE", repair.APPROVED_SEPARATE_IMAGES["A13JE"]["ordered_sha256"]),
                ("A14JE", repair.APPROVED_SEPARATE_IMAGES["A13JE"]["ordered_sha256"] + repair.APPROVED_SEPARATE_IMAGES["A14JE"]["ordered_sha256"])):
            for i, digest in enumerate(hashes):
                rows.append({"metric_model":model,"sha256":digest,"association_order":str(i+1),"is_primary":i==0,
                    "relative_path":f"corrected-media/images/{digest}.jpg","warnings":"shared_physical_content","media_review_required":True})
        other={"metric_model":"S0607EⅡ","sha256":"f"*64,"association_order":"1","is_primary":True,
            "relative_path":"corrected-media/images/other.jpg","warnings":"","media_review_required":False}
        rows.append(other)
        result=repair._apply_separate_images(rows,repair.APPROVED_SEPARATE_IMAGES)
        final={m:[r for r in result if r["metric_model"]==m] for m in ("A13JE","A14JE")}
        self.assertEqual([r["sha256"] for r in final["A13JE"]],repair.APPROVED_SEPARATE_IMAGES["A13JE"]["ordered_sha256"])
        self.assertEqual([r["sha256"] for r in final["A14JE"]],repair.APPROVED_SEPARATE_IMAGES["A14JE"]["ordered_sha256"])
        self.assertTrue(final["A13JE"][0]["is_primary"]); self.assertTrue(final["A14JE"][0]["is_primary"])
        self.assertEqual([r for r in result if r["metric_model"]=="S0607EⅡ"],[other])
        broken=json.loads(json.dumps(rows)); broken=[r for r in broken if not (r["metric_model"]=="A14JE" and r["sha256"]==repair.APPROVED_SEPARATE_IMAGES["A14JE"]["ordered_sha256"][1])]
        with self.assertRaises(repair.RepairError): repair._apply_separate_images(broken,repair.APPROVED_SEPARATE_IMAGES)
        bad = decisions("invented")
        with self.assertRaises(repair.RepairError): repair.validate_decisions(json.dumps(bad).encode())

    def test_official_https_url_allowlist(self):
        for value in ("https://www.lgmglifts.com/upload/a.pdf", "https://cdn.lgmglifts.com/a.pdf"):
            self.assertEqual(repair.validate_official_url(value), value)
        for value in ("http://www.lgmglifts.com/a.pdf", "https://evil.test/a.pdf", "https://lgmglifts.com.evil.test/a.pdf", "https://x:pw@lgmglifts.com/a.pdf", "https://lgmglifts.com/../a.pdf"):
            with self.subTest(value=value), self.assertRaises(repair.RepairError): repair.validate_official_url(value)

    def test_safe_relative_rejects_all_unsafe_forms(self):
        for value in ("../x", "/x", "C:/x", "a\\b", "a/./b", ""):
            with self.assertRaises(repair.RepairError): repair.safe_relative(value)
        self.assertEqual(repair.safe_relative("corrected-media/images/x.jpg"), "corrected-media/images/x.jpg")

    def test_paths_reject_overlap_nonempty_symlink_and_special(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan=root/"p"; media=root/"m"; remaining=root/"a"; out=root/"o"; decision=root/"d.json"
            for p in (plan,media,remaining): p.mkdir()
            decision.write_text("{}"); out.mkdir(); (out/"x").write_text("x")
            with self.assertRaises(repair.RepairError): repair.safe_paths(plan,media,remaining,decision,out)
            (out/"x").unlink(); repair.safe_paths(plan,media,remaining,decision,out)
            with self.assertRaises(repair.RepairError): repair.safe_paths(plan,media,remaining,decision,plan/"nested")
            link=root/"link"; link.symlink_to(plan, target_is_directory=True)
            with self.assertRaises(repair.RepairError): repair.safe_paths(link,media,remaining,decision,out)
            if hasattr(os, "mkfifo"):
                fifo=root/"fifo"; os.mkfifo(fifo)
                with self.assertRaises(repair.RepairError): repair.read_regular(fifo,"fifo")

    def test_pdf_signature_mime_html_size_and_truncation(self):
        self.assertEqual(repair.validate_pdf(pdf("SR1018E-2"), "application/pdf", "SR1018E-2", known_models={"SR1018E-2"})[0], "validated_model_content")
        for data,mime in ((b"<html>bad", "application/pdf"), (b"not pdf", "application/pdf"), (b"%PDF-x", "text/html"), (b"%PDF-x", "application/pdf")):
            with self.assertRaises(repair.RepairError): repair.validate_pdf(data,mime,"X")
        with self.assertRaises(repair.RepairError): repair.validate_pdf(b"%PDF-" + b"x"*repair.MAX_DATASHEET_BYTES + b"%%EOF", "application/pdf", "X")

    def test_crossed_models_are_rejected_and_correct_models_accepted(self):
        for expected, wrong in (("SR1018E-2","SR0818E-2"),("T28JE","T22JE")):
            with self.assertRaisesRegex(repair.RepairError, "datasheet_model_mismatch"):
                repair.validate_pdf(pdf(wrong), "application/pdf", expected, known_models={expected,wrong})
            result = repair.validate_pdf(pdf(expected), "application/pdf", expected, known_models={expected,wrong})
            self.assertEqual(result[0], "validated_model_content")

    def test_unextractable_pdf_requires_human_review(self):
        self.assertEqual(repair.validate_pdf(pdf(), "application/pdf", "T28JE")[0], "downloaded_pending_human_content_review")

    def test_download_is_deterministic_and_rejects_external_redirect(self):
        data=pdf("T28JE"); fetch=Fetcher(Response(data))
        result=repair.download_datasheet("https://www.lgmglifts.com/a.pdf","T28JE",{"T28JE"},fetch)
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest()); self.assertEqual(len(fetch.calls),1)
        fetch=Fetcher(Response(data,url="https://evil.test/a.pdf"))
        with self.assertRaises(repair.RepairError): repair.download_datasheet("https://www.lgmglifts.com/a.pdf","T28JE",{"T28JE"},fetch)

    def test_no_network_surface_when_urls_empty(self):
        value=repair.validate_decisions(json.dumps(decisions()).encode())
        self.assertEqual([value["datasheet_repairs"][m]["datasheet_url"] for m in repair.REPAIR_MODELS],["",""])

    def test_h625e_and_missing_datasheet_readiness_semantics(self):
        self.assertEqual(repair.MAX_DATASHEET_BYTES,10485760)
        source=(HERE/"repair_lgmg_remaining_media.py").read_text()
        for literal in ("excluded_backend_size_limit", "missing_at_source", "product_data_approval_status", "ready_for_controlled_import"):
            self.assertIn(literal,source)

    def test_visual_decisions_do_not_invent_approval(self):
        self.assertEqual(repair._visual_status("A13JE","pending_human_visual_review"),("pending_human_visual_review",False))
        self.assertTrue(repair._visual_status("A13JE","approve_shared_images_for_both")[1])
        self.assertFalse(repair._visual_status("A14JE","approve_images_for_a13je_only")[1])

    def test_visual_html_is_local_and_csv_has_all_associations(self):
        products=[{"metric_model":m,"proposed_target_name":f"Nombre {m}","proposed_target_subcategory":"Familia Ⅱ"} for m in ("A13JE","A14JE")]
        images=[]
        for model in ("A13JE","A14JE"):
            images.append({"metric_model":model,"association_order":"1","is_primary":True,"relative_path":"corrected-media/images/x.jpg",
                "original_filename":"a13je.jpg","sha256":"a"*64,"size_bytes":4,"mime":"image/jpeg","width":1,"height":1,
                "shared_products":["A13JE","A14JE"],"filename_model_markers":["A13JE"]})
        result={"products":products,"images":images,"visual_decision":"pending_human_visual_review","visual_notes":"Ⅱ"}
        with tempfile.TemporaryDirectory() as tmp:
            repair._write_visual(Path(tmp),result); html=(Path(tmp)/"A13JE-A14JE-visual-review.html").read_text()
            self.assertNotIn("file://",html); self.assertNotIn("base64",html); self.assertNotIn("<script",html); self.assertIn("corrected-media/images/x.jpg",html)
            rows=repair.csv_rows((Path(tmp)/"A13JE-A14JE-visual-review.csv").read_bytes(),"visual")
            self.assertEqual(len(rows),2); self.assertEqual({r["product_model"] for r in rows},{"A13JE","A14JE"})

    def test_separate_visual_report_has_four_explicit_sections(self):
        products=[{"metric_model":m,"proposed_target_name":m,"proposed_target_subcategory":"Familia"} for m in ("A13JE","A14JE")]
        images=[]
        for model in ("A13JE","A14JE"):
            for i,digest in enumerate(repair.APPROVED_SEPARATE_IMAGES[model]["ordered_sha256"]):
                images.append({"metric_model":model,"association_order":str(i+1),"is_primary":i==0,"relative_path":"corrected-media/images/x.jpg","original_filename":model+".jpg","sha256":digest,"size_bytes":4,"mime":"image/jpeg","width":1,"height":1,"shared_products":[model],"filename_model_markers":[model]})
        result={"products":products,"images":images,"visual_decision":"approve_separate_model_images","visual_notes":"aprobado"}
        with tempfile.TemporaryDirectory() as tmp:
            repair._write_visual(Path(tmp),result); html=(Path(tmp)/"A13JE-A14JE-visual-review.html").read_text()
            for heading in ("Imágenes conservadas para A13JE","Imágenes retiradas de A14JE","Imágenes propias conservadas para A14JE","Nueva imagen principal de A14JE"):
                self.assertIn(heading,html)
            self.assertEqual(len(repair.csv_rows((Path(tmp)/"A13JE-A14JE-visual-review.csv").read_bytes(),"visual")),7)

    def test_csv_bom_crlf_formula_and_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.csv"; repair.write_csv(path,("x",),[{"x":"=1+1"},{"x":"Ⅱ"}]); data=path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf")); self.assertIn(b"\r\n",data); self.assertIn(b"'=1+1",data); self.assertIn("Ⅱ".encode(),data)

    def test_fingerprint_canonicalization_is_deterministic_and_timestamp_free(self):
        first=repair.sha(repair.canonical({"Ⅱ":[1,2],"a":True})); second=repair.sha(repair.canonical({"a":True,"Ⅱ":[1,2]}))
        self.assertEqual(first,second); self.assertEqual(len(first),64)

    def test_manifest_zero_effects_and_no_self_hash_contract(self):
        source=(HERE/"repair_lgmg_remaining_media.py").read_text()
        for literal in ('"api_called": False','"database_modified": False','"products_created": 0','"products_updated": 0','"products_deleted": 0','"images_uploaded": 0','"datasheets_uploaded": 0','"content_published": False'):
            self.assertIn(literal,source)
        self.assertIn('path.name != "repair-manifest.json"',source)

    def test_reports_do_not_contain_secret_field_vocabulary(self):
        source=(HERE/"repair_lgmg_remaining_media.py").read_text().casefold()
        for forbidden in ("jem_nexus_access_token", "bearer ", "refresh token", "cookies"):
            self.assertNotIn(forbidden,source)

    def test_review_required_is_success_verdict_not_conflict(self):
        self.assertIn("REVIEW_REQUIRED",(HERE/"repair_lgmg_remaining_media.py").read_text())
        self.assertNotIn("REVIEW_REQUIRED: ", (HERE/"repair_lgmg_remaining_media.py").read_text())


if __name__ == "__main__": unittest.main()
