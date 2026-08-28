"""Synthetic tests for the authorised media downloader; no sockets or DNS."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import download_jem_review_media as media

IMAGE = "https://www.lgmglifts.com/es/upload/images/a.jpg"
PDF = "https://www.lgmglifts.com/es/upload/file/a.pdf"


def csv_bytes(fields, rows):
    out = io.StringIO(newline="")
    import csv
    writer = csv.DictWriter(out, fields, lineterminator="\r\n")
    writer.writeheader(); writer.writerows(rows)
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def fixture():
    key = "lgmg-0123456789abcdef"
    products = [{"selection":"", "source_key":key, "metric_model":"SRⅡ10E", "approved_name":"",
        "approved_category":"", "published":"false", "ready_for_import":"false"}]
    images = [{"source_key":key,"metric_model":"SRⅡ10E","image_order":"1","source_url":IMAGE,
        "primary_candidate":"true","rights_status":"pending_confirmation","download_status":"not_downloaded","local_file":"","review_decision":""}]
    sheets = [{"source_key":key,"metric_model":"SRⅡ10E","datasheet_order":"1","source_url":PDF,
        "rights_status":"pending_confirmation","download_status":"not_downloaded","local_file":"","review_decision":""}]
    missing = []
    drafts = [{"source_key":key,"ready_for_import":False,"product_draft":{"published":False}}]
    raw = {
        "review-products.csv": csv_bytes(products[0].keys(), products),
        "review-images.csv": csv_bytes(images[0].keys(), images),
        "review-datasheets.csv": csv_bytes(sheets[0].keys(), sheets),
        "review-missing-datasheets.csv": csv_bytes(["source_key","metric_model"], missing),
        "jem-review-drafts.json": json.dumps(drafts).encode(),
    }
    generated = [{"name":n,"size":len(v),"sha256":hashlib.sha256(v).hexdigest()} for n,v in raw.items()]
    raw["review-manifest.json"] = json.dumps({"tool":media.SOURCE_TOOL,"version":"1.0.0",
        "input_fingerprint_sha256":"a"*64,"counts":{"products_in_review":1,"image_references":1,
        "datasheet_references":1,"products_without_datasheets":0},"generated_files":generated}).encode()
    return raw


def folder(root, raw=None):
    package = root / "review-package"; package.mkdir()
    for name,data in (raw or fixture()).items(): (package/name).write_bytes(data)
    return package


class Response:
    def __init__(self, body, content_type="text/plain", status=200, headers=None):
        self.body=io.BytesIO(body); self.headers={"Content-Type":content_type, **(headers or {})}; self.status=status
    def read(self, size=-1): return self.body.read(size)
    def __enter__(self): return self
    def __exit__(self, *args): return False


class FakeFetcher:
    def __init__(self, responses): self.responses=list(responses); self.urls=[]
    def open(self, url):
        self.urls.append(url); value=self.responses.pop(0)
        if isinstance(value, Exception): raise value
        return value


class MediaDownloaderTests(unittest.TestCase):
    def test_01_confirmation_required_and_zero_network(self):
        args=argparse.Namespace(confirm_media_rights=False)
        with self.assertRaises(media.MediaError): media.run(args, FakeFetcher([]))

    def test_02_read_review_package_folder(self):
        with tempfile.TemporaryDirectory() as tmp: self.assertEqual(media.read_input(folder(Path(tmp)))[1], "folder")

    def test_03_read_session_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder(root); self.assertEqual(media.read_input(root)[1], "folder")

    def test_04_read_windows_zip_without_extracting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.zip"
            with zipfile.ZipFile(path,"w") as archive:
                for name,data in fixture().items(): archive.writestr("review-package\\"+name,data)
            self.assertEqual(media.read_input(path)[1], "zip")

    def test_05_fingerprint_is_deterministic(self): self.assertEqual(media.package_fingerprint(fixture()), media.package_fingerprint(fixture()))

    def test_06_manifest_fingerprint_malformed(self):
        raw=fixture(); value=json.loads(raw["review-manifest.json"]); value["input_fingerprint_sha256"]="bad"; raw["review-manifest.json"]=json.dumps(value).encode()
        with self.assertRaises(media.MediaError): media.validate_package(raw)

    def test_07_tampered_selected_file(self):
        raw=fixture(); raw["review-images.csv"] += b"x"
        with self.assertRaises(media.MediaError): media.validate_package(raw)

    def test_08_external_host(self):
        with self.assertRaises(media.MediaError): media.validate_url("https://example.com/es/upload/images/a.jpg","image")

    def test_09_subdomain(self):
        with self.assertRaises(media.MediaError): media.validate_url("https://cdn.www.lgmglifts.com/es/upload/images/a.jpg","image")

    def test_10_http(self):
        with self.assertRaises(media.MediaError): media.validate_url(IMAGE.replace("https:","http:"),"image")

    def test_11_credentials(self):
        with self.assertRaises(media.MediaError): media.validate_url(IMAGE.replace("www.","u:p@www."),"image")

    def test_12_alternate_port(self):
        with self.assertRaises(media.MediaError): media.validate_url(IMAGE.replace(".com",".com:444"),"image")

    def test_13_query_and_fragment(self):
        for suffix in ("?x=1","#x"):
            with self.assertRaises(media.MediaError): media.validate_url(IMAGE+suffix,"image")

    def test_14_traversal_and_backslash(self):
        for url in (IMAGE.replace("/a.jpg","/../a.jpg"), IMAGE.replace("/a.jpg","\\a.jpg")):
            with self.assertRaises(media.MediaError): media.validate_url(url,"image")

    def test_15_wrong_image_path(self):
        with self.assertRaises(media.MediaError): media.validate_url(PDF.replace(".pdf",".jpg"),"image")

    def test_16_wrong_pdf_path(self):
        with self.assertRaises(media.MediaError): media.validate_url(IMAGE.replace(".jpg",".pdf"),"datasheet")

    def test_17_external_redirect(self):
        handler=media.StrictRedirect()
        with self.assertRaises(media.MediaError): handler.redirect_request(mock.Mock(),None,302,"",{},"https://evil.test/a.jpg")

    def test_18_http_downgrade_redirect(self):
        handler=media.StrictRedirect()
        with self.assertRaises(media.MediaError): handler.redirect_request(mock.Mock(),None,302,"",{},IMAGE.replace("https:","http:"))

    def test_19_redirect_limit(self):
        handler=media.StrictRedirect(); handler.count=media.MAX_REDIRECTS
        with self.assertRaises(media.MediaError): handler.redirect_request(mock.Mock(),None,302,"",{},IMAGE)

    def test_20_robots_allowed(self):
        fetch=FakeFetcher([Response(b"User-agent: *\nAllow: /es/upload/\n")])
        self.assertTrue(media.validate_robots(fetch,"agent"))

    def test_21_robots_forbidden(self):
        fetch=FakeFetcher([Response(b"User-agent: *\nDisallow: /es/upload/\n")])
        with self.assertRaises(media.MediaError): media.validate_robots(fetch,"agent")

    def test_22_robots_invalid(self):
        with self.assertRaises(media.MediaError): media.validate_robots(FakeFetcher([Response(b"nonsense")]),"agent")

    def test_23_valid_jpeg(self): self.assertEqual(media.detect_content(b"\xff\xd8\xffx","image/jpeg",IMAGE,"image"),("image/jpeg",".jpg"))
    def test_24_valid_png(self): self.assertEqual(media.detect_content(b"\x89PNG\r\n\x1a\n","image/png",IMAGE.replace(".jpg",".png"),"image")[0],"image/png")
    def test_25_valid_webp(self): self.assertEqual(media.detect_content(b"RIFFxxxxWEBP","image/webp",IMAGE.replace(".jpg",".webp"),"image")[0],"image/webp")
    def test_26_valid_pdf(self): self.assertEqual(media.detect_content(b"%PDF-1.7","application/pdf",PDF,"datasheet")[0],"application/pdf")

    def test_27_html_as_image_and_pdf(self):
        for kind,url in (("image",IMAGE),("datasheet",PDF)):
            with self.assertRaises(media.RemoteError): media.detect_content(b"<html>","text/html",url,kind)

    def test_28_mime_incompatible(self):
        with self.assertRaises(media.RemoteError): media.detect_content(b"\xff\xd8\xff", "text/html", IMAGE, "image")

    def test_29_octet_stream_magic(self): self.assertEqual(media.detect_content(b"%PDF-", "application/octet-stream", PDF, "datasheet")[0],"application/pdf")

    def test_30_empty_response_removes_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"x.part-target"
            with self.assertRaises(media.RemoteError): media.stream_download(FakeFetcher([Response(b"", "image/jpeg")]),IMAGE,"image",path,0)
            self.assertFalse(Path(str(path)+".part").exists())

    def test_31_content_length_image_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            response=Response(b"x","image/jpeg",headers={"Content-Length":str(media.MAX_IMAGE+1)})
            with self.assertRaises(media.RemoteError): media.stream_download(FakeFetcher([response]),IMAGE,"image",Path(tmp)/"x",0)

    def test_32_content_length_pdf_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            response=Response(b"x","application/pdf",headers={"Content-Length":str(media.MAX_PDF+1)})
            with self.assertRaises(media.RemoteError): media.stream_download(FakeFetcher([response]),PDF,"datasheet",Path(tmp)/"x",0)

    def test_33_type_total_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(media.RemoteError): media.stream_download(FakeFetcher([Response(b"\xff\xd8\xff","image/jpeg")]),IMAGE,"image",Path(tmp)/"x",media.MAX_IMAGE_TOTAL)

    def test_34_filename_sanitized_and_roman(self):
        roman_tokens=("i","ii","iii","iv","v","vi","vii","viii","ix","x","xi","xii")
        cases=[("SRⅡ 10 E","sr-ii-10-e"),("S1413Ⅱ","s1413-ii"),("ⅡSR","ii-sr"),
            ("SR1218E","sr1218e"), *( (f"A{roman}B",f"a-{token}-b")
                for roman_set in ("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ","ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹⅺⅻ")
                for roman,token in zip(roman_set,roman_tokens) )]
        for model,expected in cases:
            with self.subTest(model=model):
                self.assertEqual(media.slug(model,"fallback"),expected)
                self.assertNotIn("--",media.slug(f"/{model}\\","fallback"))

        row={"metric_model":"SRⅡ 10/E","source_key":"lgmg-0123456789abcdef","image_order":"1"}
        short=hashlib.sha256(IMAGE.encode()).hexdigest()[:10]
        self.assertEqual(media.local_name(row,"image",IMAGE,".jpg"),f"media/images/lgmg-sr-ii-10-e-01-{short}.jpg")
        self.assertEqual(media.local_name(row,"datasheet",PDF,".pdf"),
            f"media/datasheets/lgmg-sr-ii-10-e-ficha-tecnica-{hashlib.sha256(PDF.encode()).hexdigest()[:10]}.pdf")
        for unsafe in ("../Ⅱ/..", "\\Ⅱ\\", "///", ""):
            with self.subTest(unsafe=unsafe):
                name=media.local_name({**row,"metric_model":unsafe},"image",IMAGE,".jpg")
                self.assertNotIn("..",name); self.assertNotIn("\\",name)
                self.assertNotIn("",name.split("/")); self.assertTrue(name.rsplit("/",1)[-1])

    def test_35_filename_collision_avoided(self):
        row={"metric_model":"X","source_key":"lgmg-0123456789abcdef","image_order":"1"}
        self.assertNotEqual(media.local_name(row,"image",IMAGE,".jpg"),media.local_name(row,"image",IMAGE.replace("a.jpg","b.jpg"),".jpg"))

    def test_36_content_disposition_is_ignored(self):
        row={"metric_model":"X","source_key":"lgmg-0123456789abcdef","image_order":"1"}
        self.assertNotIn("evil",media.local_name(row,"image",IMAGE,".jpg"))

    def test_37_timeout_retried(self):
        with mock.patch.object(media,"stream_download",side_effect=[TimeoutError(),({"ok":1})]) as call:
            result,attempts=media.fetch_with_retries(None,IMAGE,"image",Path("x"),0,lambda _:None)
        self.assertEqual((result,attempts),({"ok":1},2)); self.assertEqual(call.call_count,2)

    def test_38_429_retried(self):
        error=urllib.error.HTTPError(IMAGE,429,"",{"Retry-After":"0"},None)
        with mock.patch.object(media,"stream_download",side_effect=[error,{"ok":1}]):
            self.assertEqual(media.fetch_with_retries(None,IMAGE,"image",Path("x"),0,lambda _:None)[1],2)

    def test_39_404_not_retried(self):
        error=urllib.error.HTTPError(IMAGE,404,"",{},None)
        with mock.patch.object(media,"stream_download",side_effect=error) as call:
            with self.assertRaises(media.RemoteError): media.fetch_with_retries(None,IMAGE,"image",Path("x"),0,lambda _:None)
        self.assertEqual(call.call_count,1)

    def test_40_retry_limit(self):
        with mock.patch.object(media,"stream_download",side_effect=TimeoutError()) as call:
            with self.assertRaises(media.RemoteError): media.fetch_with_retries(None,IMAGE,"image",Path("x"),0,lambda _:None)
        self.assertEqual(call.call_count,3)

    def test_41_atomic_state_has_no_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"state.json"; media.atomic_json(path,{"x":1})
            self.assertTrue(path.is_file()); self.assertFalse(Path(str(path)+".part").exists())

    def test_42_resume_fingerprint_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp); validated=media.validate_package(fixture()); state=media._new_state(validated); state["input_fingerprint_sha256"]="b"*64
            media.atomic_json(out/"media-download-state.json",state)
            with self.assertRaises(media.MediaError): media.load_state(out,validated,True)

    def test_43_resume_completed_file_not_repeated_inventory(self):
        validated=media.validate_package(fixture()); state=media._new_state(validated)
        self.assertEqual(len(state["items"]),2); self.assertEqual(len({x["url"] for x in state["items"]}),2)

    def test_44_resume_tampered_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp); validated=media.validate_package(fixture()); state=media._new_state(validated); item=state["items"][0]
            item.update(completed=True,status="completed",local_file="media/images/x.jpg",size_bytes=1,sha256="0"*64)
            (out/"media/images").mkdir(parents=True); (out/item["local_file"]).write_bytes(b"x"); media.atomic_json(out/"media-download-state.json",state)
            with self.assertRaises(media.MediaError): media.load_state(out,validated,True)

    def test_45_formula_injection(self): self.assertEqual(media._excel("=1+1"),"'=1+1")

    def test_46_limits_and_zero_side_effect_constants(self):
        self.assertEqual((media.MAX_IMAGE_URLS,media.MAX_PDF_URLS,media.MAX_REDIRECTS),(500,200,5))

    def test_47_output_fields_cover_associations_files_failures_manifest(self):
        source=Path(media.__file__).read_text(encoding="utf-8")
        for name in ("downloaded-images.csv","downloaded-datasheets.csv","media-files.csv","media-failures.csv","media-manifest.json"):
            self.assertIn(name,source)

    def test_48_manifest_declares_zero_jem_import_publish(self):
        source=Path(media.__file__).read_text(encoding="utf-8")
        self.assertIn('"jem_nexus_called":False',source); self.assertIn('"products_imported":0',source); self.assertIn('"content_published":False',source)

    def test_49_missing_datasheets_preserved(self):
        validated=media.validate_package(fixture()); self.assertEqual(validated["missing"],[])

    def test_50_uncertain_key_cannot_enter_media(self):
        raw=fixture(); text=raw["review-images.csv"].decode("utf-8").replace("lgmg-0123456789abcdef","lgmg-ffffffffffffffff")
        raw["review-images.csv"]=text.encode(); value=json.loads(raw["review-manifest.json"])
        for item in value["generated_files"]:
            if item["name"]=="review-images.csv": item.update(size=len(raw["review-images.csv"]),sha256=hashlib.sha256(raw["review-images.csv"]).hexdigest())
        raw["review-manifest.json"]=json.dumps(value).encode()
        with self.assertRaises(media.MediaError): media.validate_package(raw)


if __name__ == "__main__": unittest.main()
