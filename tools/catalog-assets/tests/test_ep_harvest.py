from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from catalog_assets.cli import Response, initial_files, main
from catalog_assets.ep_harvest import (
    CHECKPOINT_VERSION,
    EP_START,
    FAMILIES,
    GAM_LISTINGS,
    HarvestError,
    _allowed_product,
    _parse,
    harvest_ep,
    load_seed,
    reconcile_title,
)
from catalog_assets.paths import initialize
from catalog_assets.sources import read_sources


class MapTransport:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    @staticmethod
    def resolve(host, port, type=None):
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    def get(self, url, headers, timeout, max_bytes):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Response):
            return value
        return Response(200, value.encode(), {"content-type": "text/html; charset=utf-8"}, url)


def title_for(model):
    shown = "EPT20 ET" if model == "EPT20-ET" else model
    kind = "TRANSPALETA ELÉCTRICA" if model.startswith("EPT") else "EQUIPO INDUSTRIAL"
    return f"{kind} EP {shown}"


def full_pages(no_assets=False):
    rows = load_seed()
    pages = {
        "https://online.gamrentals.com/robots.txt": "User-agent: *\nAllow: /cl/",
        "https://ep-equipment.com/robots.txt": "User-agent: *\nAllow: /es/",
    }
    groups = [[] for _ in GAM_LISTINGS]
    for index, row in enumerate(rows):
        model = row["canonical_candidate"]
        slug = model.lower().replace(" ", "-")
        gam_url = f"https://online.gamrentals.com/cl/ep/{slug}"
        groups[index % 4].append(f'<a class="product-card" data-model="{title_for(model)}" href="{gam_url}">producto</a>')
        if row["disposition"] == "OBSERVED":
            assets = "" if no_assets else f'<main><img class="product_image" src="/img/{slug}.jpg" alt="{model}"><a href="/download/{slug}">Descargar Ficha técnica</a></main>'
            pages[gam_url] = f"<h1>{title_for(model)}</h1>{assets}"
    pages.update({url: "".join(group) for url, group in zip(GAM_LISTINGS, groups)})
    pages[EP_START] = "".join((
        '<article><h3>EFL181</h3><a href="/es/product/efl-181/">Aprende más</a></article>',
        '<article><h3>EPT20-ET</h3><a href="/es/product/ept20-et/">Aprende más</a></article>',
        '<a href="/es/contacto/">Contacto</a>',
    ))
    pages["https://ep-equipment.com/es/product/efl-181/"] = (
        '<main><h1>EFL181</h1><img class="product gallery" src="https://cdn.ep-portal.net/efl181-main.jpg" alt="EFL181">'
        '<a href="https://cdn.ep-portal.net/download?id=181">Descargar hoja de datos</a></main>'
        '<nav><img class="product" src="/logo.jpg" alt="logo"></nav><section class="related"><img class="product" src="/other.jpg" alt="otro"></section>'
    )
    pages["https://ep-equipment.com/es/product/ept20-et/"] = '<main><h1>EPT20-ET</h1><img class="product" src="https://cdn.ep-portal.net/ept20-et.jpg" alt="EPT20-ET"></main>'
    return pages


class EpHarvestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "Maquinas"
        initialize(self.root, initial_files())

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, transport):
        capture = io.StringIO()
        old = sys.stdout
        sys.stdout = capture
        try:
            code = main(["--root", str(self.root), "harvest-ep", "--allow-public-network", "--request-delay", "0"], transport)
        finally:
            sys.stdout = old
        return code, json.loads(capture.getvalue())

    def test_seed_has_exact_universe_and_review_families(self):
        rows = load_seed()
        self.assertEqual(39, len(rows))
        self.assertEqual(FAMILIES, {row["canonical_candidate"] for row in rows if row["disposition"] == "REVIEW"})
        self.assertEqual(35, sum(row["disposition"] == "OBSERVED" for row in rows))

    def test_descriptive_title_reconciliation_and_variants(self):
        seed = load_seed()
        cases = {
            "TRANSPALETA ELÉCTRICA EP EPT20": "EPT20",
            "TRANSPALETA ELÉCTRICA EP EPT20-30RT": "EPT20-30RT",
            "TRANSPALETA ELÉCTRICA EP EPT20-30RTS": "EPT20-30RTS",
            "TRANSPALETA ELÉCTRICA EP EPT20-35RT": "EPT20-35RT",
            "TRANSPALETA ELÉCTRICA EP EPT20-35RTS": "EPT20-35RTS",
            "TRANSPALETA ELÉCTRICA EP EPT20 ET": "EPT20-ET",
            "TRANSPALETA MANUAL EP CBY 30II": "CBY 30II",
            "APILADOR ELÉCTRICO EP ESi161": "ESi161",
            "APILADOR ELÉCTRICO EP KSi201": "KSi201",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual((expected, []), reconcile_title(title, seed))

    def test_longest_complete_match_and_rejects_partial_or_ambiguous(self):
        seed = load_seed()
        self.assertEqual(("EPT20-30RTS", []), reconcile_title("EP EPT20-30RTS", seed))
        self.assertEqual((None, []), reconcile_title("EP EPT20-30RTSX", seed))
        model, conflicts = reconcile_title("Comparar EFL181 con EPT20", seed)
        self.assertIsNone(model)
        self.assertEqual({"EFL181", "EPT20"}, set(conflicts))

    def test_official_card_pairs_heading_with_learn_more_and_scopes_routes(self):
        parser = _parse(b'<article><h3>F4</h3><a href="/es/product/f4/">Aprende m\xc3\xa1s</a></article>', EP_START)
        self.assertEqual([("F4", "https://ep-equipment.com/es/product/f4/", "")], parser.items)
        self.assertTrue(_allowed_product("https://www.ep-equipment.com/es/product/f4/", "EP"))
        self.assertFalse(_allowed_product("https://ep-equipment.com/es/productos/f4/", "EP"))
        self.assertFalse(_allowed_product("https://ep-equipment.com/es/contacto/", "EP"))
        self.assertFalse(_allowed_product("http://ep-equipment.com/es/product/f4/", "EP"))

    def test_product_parser_accepts_contextual_sheet_and_excludes_chrome(self):
        parser = _parse(full_pages()["https://ep-equipment.com/es/product/efl-181/"].encode(), "https://ep-equipment.com/es/product/efl-181/")
        urls = {asset[1] for asset in parser.assets}
        self.assertIn("https://cdn.ep-portal.net/efl181-main.jpg", urls)
        self.assertIn("https://cdn.ep-portal.net/download?id=181", urls)
        self.assertNotIn("https://ep-equipment.com/logo.jpg", urls)
        self.assertNotIn("https://ep-equipment.com/other.jpg", urls)

    def test_all_39_reconcile_and_outputs_prioritize_ep(self):
        transport = MapTransport(full_pages())
        code, summary = self.run_main(transport)
        self.assertEqual(0, code)
        self.assertEqual((39, 39, 35), (summary["live_models"], summary["matched_seed_models"], summary["concrete_models"]))
        self.assertEqual([], summary["added"])
        self.assertEqual([], summary["removed"])
        self.assertEqual([], summary["ambiguous"])
        self.assertEqual(sorted(FAMILIES), summary["review_families"])
        self.assertEqual(0, summary["assets_downloaded"])
        self.assertGreater(summary["sources"], 0)
        sources = read_sources(self.root / "_control/fuentes.csv")
        efl = [row for row in sources if row.model == "EFL181"]
        self.assertEqual({("EP", "image"), ("EP", "technical_sheet")}, {(row.source_name, row.asset_type) for row in efl})
        et = [row for row in sources if row.model == "EPT20-ET"]
        self.assertEqual({("EP", "image"), ("GAM", "technical_sheet")}, {(row.source_name, row.asset_type) for row in et})
        self.assertTrue(all(row.target_brand == "EP" and not row.enabled and "VALIDATION_DEFERRED" in row.notes for row in sources))
        inventory = (self.root / "_control/research/ep-model-inventory.csv").read_text(encoding="utf-8-sig")
        self.assertIn("observed_title", inventory.splitlines()[0])
        self.assertIn("TRANSPALETA ELÉCTRICA EP EPT20 ET", inventory)
        self.assertFalse(any((self.root / "EP/Imagenes modelos EP").iterdir()))
        self.assertFalse(any((self.root / "EP/fichas-tecnicas EP").iterdir()))

    def test_real_added_and_removed_are_post_reconciliation(self):
        pages = full_pages()
        pages[GAM_LISTINGS[0]] = pages[GAM_LISTINGS[0]].replace("EQUIPO INDUSTRIAL EP EFS101", "EQUIPO INDUSTRIAL EP NUEVO-99", 1)
        pages["https://online.gamrentals.com/cl/ep/efs101"] = "<h1>NUEVO-99</h1>"
        _, summary = self.run_main(MapTransport(pages))
        self.assertIn("EQUIPO INDUSTRIAL EP NUEVO-99", summary["added"])
        self.assertIn("EFS101", summary["removed"])

    def test_checkpoint_v1_is_archived_then_compatible_resume_is_idempotent(self):
        checkpoint = self.root / "_control/research/ep-harvest-checkpoint.json"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text('{"format_version":1,"live_items":[{"bad":"derived"}]}', encoding="utf-8")
        first = MapTransport(full_pages())
        self.assertEqual(0, self.run_main(first)[0])
        archives = list(checkpoint.parent.glob("ep-harvest-checkpoint.incompatible-*.json"))
        self.assertEqual(1, len(archives))
        self.assertEqual(1, json.loads(archives[0].read_text())["format_version"])
        current = json.loads(checkpoint.read_text())
        self.assertTrue(all(current[key] == value for key, value in CHECKPOINT_VERSION.items()))
        snapshots = {path.name: path.read_bytes() for path in checkpoint.parent.iterdir()}
        second = MapTransport({})
        self.assertEqual(0, self.run_main(second)[0])
        self.assertEqual([], second.calls)
        self.assertEqual(snapshots, {path.name: path.read_bytes() for path in checkpoint.parent.iterdir()})

    def test_zero_sources_fails_structurally_and_preserves_reports(self):
        previous = b"previous,valid,fuentes\n"
        target = self.root / "_control/fuentes.csv"
        target.write_bytes(previous)
        pages = full_pages(no_assets=True)
        pages[EP_START] = ""
        with self.assertRaises(HarvestError) as caught:
            harvest_ep(self.root, MapTransport(pages), request_delay=0)
        self.assertEqual("HARVEST_NO_ASSET_SOURCES", caught.exception.code)
        self.assertEqual(previous, target.read_bytes())
        self.assertFalse((self.root / "_control/research/ep-source-audit.md").exists())

    def test_no_product_pages_fails_with_distinct_code(self):
        pages = full_pages(no_assets=True)
        pages[EP_START] = ""
        for url in list(pages):
            if "/cl/ep/" in url:
                pages[url] = "<h1>modelo ajeno</h1>"
        with self.assertRaises(HarvestError) as caught:
            harvest_ep(self.root, MapTransport(pages), request_delay=0)
        self.assertEqual("HARVEST_NO_PRODUCT_PAGES", caught.exception.code)

    def test_network_consent_redirect_and_brand_scope_guards(self):
        with self.assertRaisesRegex(ValueError, "--allow-public-network"):
            main(["--root", str(self.root), "harvest-ep"], MapTransport({}))
        bad = full_pages()
        bad[GAM_LISTINGS[0]] = Response(200, b"ok", {"content-type": "text/html"}, "https://evil.example/x")
        with self.assertRaises(ValueError):
            self.run_main(MapTransport(bad))
        source = Path(__file__).parents[1] / "catalog_assets/ep_harvest.py"
        text = source.read_text(encoding="utf-8")
        self.assertNotIn('target_brand": "LGMG"', text)
        self.assertNotIn('target_brand": "JLG"', text)


if __name__ == "__main__":
    unittest.main()
