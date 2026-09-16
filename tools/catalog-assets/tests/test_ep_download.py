from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from catalog_assets.cli import Response, initial_files, main
from catalog_assets.downloader import download_one
from catalog_assets.ep_harvest import CHECKPOINT_VERSION, harvest_ep
from catalog_assets.ep_download import RESULT_FIELDS, _materialize, load_ep_plan
from catalog_assets.naming import asset_basename
from catalog_assets.paths import initialize
from catalog_assets.reports import write_csv
from test_ep_harvest import FAMILIES, MISSING_SHEETS, MapTransport, full_pages

JPEG = b"\xff\xd8\xffsynthetic\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\nsynthetic-IEND\x00\x00\x00\x00"
WEBP = b"RIFF\x08\x00\x00\x00WEBPsynthetic"
PDF = b"%PDF-1.4\nsynthetic\n%%EOF\n"


class AssetTransport:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    @staticmethod
    def resolve(host, port, type=None):
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    def get(self, url, headers, timeout, max_bytes):
        self.calls.append((url, dict(headers)))
        value = self.payloads[url]
        if isinstance(value, Exception):
            raise value
        body, mime = value
        response_headers = {} if mime is None else {"content-type": mime}
        return Response(206 if headers.get("Range") else 200, body, response_headers, url)


class EpDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "Maquinas"
        initialize(self.root, initial_files())
        harvest_ep(self.root, MapTransport(full_pages()), request_delay=0)

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, args, transport=None):
        capture = io.StringIO()
        old = sys.stdout
        sys.stdout = capture
        try:
            code = main(["--root", str(self.root), "download-ep-harvest", *args], transport)
        finally:
            sys.stdout = old
        return code, json.loads(capture.getvalue())

    def test_complete_65_candidate_dry_run_is_read_only_and_has_no_network(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        transport = AssetTransport({})
        code, summary = self.invoke(["--dry-run"], transport)
        self.assertEqual(0, code)
        self.assertEqual((35, 35, 30, 65), (summary["concrete_models"], summary["image_candidates"], summary["technical_sheet_candidates"], summary["candidates_total"]))
        self.assertEqual([], summary["models_missing_image"])
        self.assertEqual(sorted(MISSING_SHEETS), summary["models_missing_technical_sheet"])
        self.assertEqual(sorted(FAMILIES), summary["families_excluded"])
        self.assertEqual((0, 0, []), (summary["requests_this_run"], summary["downloaded"], transport.calls))
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_checkpoint_missing_corrupt_and_incompatible_fail_closed(self):
        path = self.root / "_control/research/ep-harvest-checkpoint.json"
        for content, code in ((None, "CHECKPOINT_MISSING"), ("{", "CHECKPOINT_CORRUPT"),
                              (json.dumps({**CHECKPOINT_VERSION, "parser_version": 3}), "CHECKPOINT_INCOMPATIBLE")):
            path.unlink(missing_ok=True)
            if content is not None: path.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, code): self.invoke(["--dry-run"])

    def test_rejects_foreign_target_family_and_unmatched_source(self):
        candidates = self.root / "_control/research/ep-asset-candidates.csv"
        original = candidates.read_text(encoding="utf-8-sig")
        for old, new in (("EP,", "JLG,"), (",EFL181,", ",SERIE X2,"), ("VALIDATION_DEFERRED", "UNKNOWN")):
            candidates.write_text(original.replace(old, new, 1), encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError, "CANDIDATE_NOT_APPROVED"): self.invoke(["--dry-run"])

    def _payloads(self):
        with (self.root / "_control/research/ep-asset-candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        return {r["asset_url"]: (PDF, "application/pdf") if r["asset_type"] == "technical_sheet" else (JPEG, "image/jpeg") for r in rows}

    def test_download_missing_sources_dedupe_and_second_run_is_socket_free(self):
        first = AssetTransport(self._payloads())
        code, summary = self.invoke(["--allow-public-network"], first)
        self.assertEqual(0, code)
        self.assertEqual(5, summary["missing_source"])
        self.assertEqual(65, summary["attempted"])
        self.assertGreater(summary["downloaded"], 0)
        with (self.root / "_control/ep-download-results.csv").open(encoding="utf-8-sig") as handle:
            report = list(csv.DictReader(handle))
        self.assertEqual(5, sum(r["state"] == "MISSING_SOURCE" for r in report))
        by_model = {r["model"]: r for r in report if r["asset_type"] == "image"}
        shared = {"EFL302": "EFL252", "EPT20-30RTS": "EPT20-30RT",
                  "EPT20-35RT": "EPT20-30RT", "EPT20-35RTS": "EPT20-30RT"}
        for model, original in shared.items():
            self.assertEqual(by_model[original]["sha256"], by_model[model]["sha256"])
            self.assertNotEqual(by_model[original]["path"], by_model[model]["path"])
            self.assertEqual(f"EP-{model}.jpg", Path(by_model[model]["path"]).name)
        expected_paths = {r["path"] for r in report if r["path"]}
        manifest = json.loads((self.root / "_control/manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(expected_paths <= {r["path"] for r in manifest["accepted_files"]})
        for filename, field in (("_control/checksums.csv", "ruta_relativa"),
                                ("inventario.csv", "ruta_relativa")):
            with (self.root / filename).open(encoding="utf-8-sig") as handle:
                self.assertTrue(expected_paths <= {r[field] for r in csv.DictReader(handle)})
        capture = io.StringIO(); old_stdout = sys.stdout; sys.stdout = capture
        try:
            verify_code = main(["--root", str(self.root), "verify"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(0, verify_code)
        second = AssetTransport({})
        code, summary = self.invoke(["--allow-public-network"], second)
        self.assertEqual(0, code)
        self.assertEqual([], second.calls)
        self.assertEqual(0, summary["requests_this_run"])
        self.assertEqual(65, summary["already_present"])

    def test_binary_signatures_extension_mismatch_html_truncation_and_failure_exit(self):
        payloads = self._payloads()
        image_urls = [r["asset_url"] for r in load_ep_plan(self.root)["candidates"] if r["asset_type"] == "image"]
        payloads[image_urls[0]] = (PNG, "image/png")
        payloads[image_urls[1]] = (WEBP, "image/webp")
        payloads[image_urls[2]] = (b"<html>error</html>", "text/html")
        code, summary = self.invoke(["--allow-public-network", "--only", "image", "--max-files", "3"], AssetTransport(payloads))
        self.assertEqual(1, code)
        self.assertEqual(1, summary["failed"])
        names = [p.suffix for p in (self.root / "EP/Imagenes modelos EP").iterdir()]
        self.assertIn(".png", names)
        self.assertIn(".webp", names)
        self.assertFalse(any(p.read_bytes().startswith(b"<html") for p in (self.root / "EP/Imagenes modelos EP").iterdir()))

    def test_type_mismatch_network_failure_and_no_lgmg_jlg_changes(self):
        before = {name: list((self.root / name).rglob("*")) for name in ("LGMG", "JLG")}
        payloads = self._payloads()
        first = load_ep_plan(self.root)["candidates"][0]["asset_url"]
        payloads[first] = (PDF, "application/pdf")
        code, summary = self.invoke(["--allow-public-network", "--max-files", "1"], AssetTransport(payloads))
        self.assertEqual((1, 1), (code, summary["failed"]))
        self.assertEqual(before, {name: list((self.root / name).rglob("*")) for name in ("LGMG", "JLG")})

    def test_ep_image_mime_policy_uses_signature_as_authority(self):
        accepted = ((JPEG, "image/jpg", ".jpg"), (JPEG, "image/webp", ".jpg"),
                    (PNG, "image/jpeg", ".png"), (WEBP, "image/png", ".webp"),
                    (JPEG, None, ".jpg"), (JPEG, "application/octet-stream", ".jpg"))
        for index, (body, declared, extension) in enumerate(accepted):
            with self.subTest(declared=declared, extension=extension):
                if body is JPEG:
                    body = b"\xff\xd8\xff" + str(index).encode() + b"\xff\xd9"
                url = f"https://example.com/accepted-{index}.bin"
                outcome = download_one(self.root, {"url": url, "target_brand": "EP",
                    "model": f"MIME-{index}", "expected_kind": "image"},
                    AssetTransport({url: (body, declared)}), normalize_image_mime=True)
                self.assertEqual(extension, Path(outcome["path"]).suffix)
                self.assertIn("declared=", outcome["mime_detail"])
                self.assertIn("detected=", outcome["mime_detail"])

        rejected = ((b"<html>error</html>", "image/jpeg", "INVALID_BINARY"),
                    (JPEG, "text/html", "MIME_CONFLICT"),
                    (PDF, "image/jpeg", "TYPE_MISMATCH"),
                    (JPEG, "application/pdf", "MIME_CONFLICT"))
        for index, (body, declared, error) in enumerate(rejected):
            with self.subTest(declared=declared, error=error):
                url = f"https://example.com/rejected-{index}.bin"
                with self.assertRaisesRegex(ValueError, error):
                    download_one(self.root, {"url": url, "target_brand": "EP",
                        "model": f"BAD-{index}", "expected_kind": "image"},
                        AssetTransport({url: (body, declared)}), normalize_image_mime=True)

    def test_nine_gam_mime_failures_are_normalized(self):
        models = {"CQD15SD", "EFL253", "EFL303", "EFL703-HV-6", "RSC082", "RSC122",
                  "RSC152", "SYG-1016", "WSA161"}
        payloads = self._payloads()
        selected = [r for r in load_ep_plan(self.root)["candidates"]
                    if r["model"] in models and r["asset_type"] == "image"]
        self.assertEqual(models, {r["model"] for r in selected})
        for index, row in enumerate(selected):
            payloads[row["asset_url"]] = (b"\xff\xd8\xffmime" + str(index).encode() + b"\xff\xd9", "image/webp")
        code, summary = self.invoke(["--allow-public-network", "--only", "image"], AssetTransport(payloads))
        self.assertEqual((0, 0), (code, summary["failed"]))
        with (self.root / "_control/ep-download-results.csv").open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        details = {r["model"]: r["detail"] for r in rows if r["model"] in models}
        self.assertEqual(models, set(details))
        self.assertTrue(all("normalized=image-subtype" in detail for detail in details.values()))

    def test_previous_52_4_9_5_report_dry_run_is_read_only_and_socket_free(self):
        candidates = load_ep_plan(self.root)["candidates"]
        rows, sources = [], {}
        for index, row in enumerate(candidates):
            base = {"source": row["source_name"], "target_brand": "EP", "model": row["model"],
                    "asset_type": row["asset_type"], "asset_url": row["asset_url"],
                    "page_url": row["page_url"], "path": "", "bytes": "", "sha256": "",
                    "state": "TYPE_MISMATCH", "detail": "MIME_CONFLICT"}
            if index < 52:
                body = ((b"%PDF-1.4\n" + str(index).encode() + b"\n%%EOF\n") if row["asset_type"] == "technical_sheet"
                        else (b"\xff\xd8\xff" + str(index).encode() + b"\xff\xd9"))
                extension = ".pdf" if row["asset_type"] == "technical_sheet" else ".jpg"
                folder = "fichas-tecnicas EP" if row["asset_type"] == "technical_sheet" else "Imagenes modelos EP"
                path = self.root / "EP" / folder / asset_basename("EP", row["model"], row["asset_type"], extension)
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
                digest = __import__("hashlib").sha256(body).hexdigest()
                base.update(path=path.relative_to(self.root).as_posix(), bytes=str(len(body)), sha256=digest,
                            state="DOWNLOADED", detail="")
                sources[row["asset_type"]] = base
            elif index < 56:
                source = sources[row["asset_type"]]
                base.update(path=source["path"], bytes=source["bytes"], sha256=source["sha256"],
                            state="DUPLICATE", detail="duplicate")
            rows.append(base)
        write_csv(self.root / "_control/ep-download-results.csv", RESULT_FIELDS, rows, self.root)
        before = (self.root / "_control/ep-download-results.csv").read_bytes()
        transport = AssetTransport({})
        code, summary = self.invoke(["--dry-run"], transport)
        self.assertEqual(0, code)
        self.assertEqual((52, 4, 9, 5, 0, 0, True),
            (summary["would_skip_present"], summary["would_materialize_shared"],
             summary["would_retry"], summary["missing_source"], summary["requests_this_run"],
             summary["downloaded"], summary["dry_run"]))
        self.assertEqual([], transport.calls)
        self.assertEqual(before, (self.root / "_control/ep-download-results.csv").read_bytes())
        retry_payloads = {}
        for index, row in enumerate(candidates[56:]):
            body = ((b"%PDF-1.4\nretry" + str(index).encode() + b"\n%%EOF\n")
                    if row["asset_type"] == "technical_sheet"
                    else (b"\xff\xd8\xffretry" + str(index).encode() + b"\xff\xd9"))
            retry_payloads[row["asset_url"]] = (body, "application/pdf" if row["asset_type"] == "technical_sheet" else "image/webp")
        retry_transport = AssetTransport(retry_payloads)
        code, resumed = self.invoke(["--allow-public-network"], retry_transport)
        self.assertEqual((0, 9, 9, 4, 0),
                         (code, resumed["requests_this_run"], resumed["retried"],
                          resumed["materialized_from_existing"], resumed["failed"]))
        self.assertEqual(9, len(retry_transport.calls))
        final_transport = AssetTransport({})
        code, final = self.invoke(["--allow-public-network"], final_transport)
        self.assertEqual((0, 0, 65, []),
                         (code, final["requests_this_run"], final["already_present"], final_transport.calls))

    def test_shared_materialization_never_overwrites_and_uses_stable_suffix(self):
        source = self.root / "EP/Imagenes modelos EP/EP-ORIGINAL.jpg"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(JPEG)
        occupied = source.parent / "EP-SHARED.jpg"
        occupied.write_bytes(PNG)
        row = {"model": "SHARED", "asset_type": "image"}
        first, _, _ = _materialize(self.root, row, source)
        self.assertEqual("EP-SHARED-2.jpg", Path(first).name)
        self.assertEqual(PNG, occupied.read_bytes())
        self.assertNotEqual(source.stat().st_ino, (self.root / first).stat().st_ino)
        second, _, _ = _materialize(self.root, row, source)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
