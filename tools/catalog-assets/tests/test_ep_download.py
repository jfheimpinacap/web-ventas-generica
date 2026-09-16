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
from catalog_assets.ep_harvest import CHECKPOINT_VERSION, harvest_ep
from catalog_assets.ep_download import load_ep_plan
from catalog_assets.paths import initialize
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
        return Response(206 if headers.get("Range") else 200, body, {"content-type": mime}, url)


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


if __name__ == "__main__":
    unittest.main()
