"""Synthetic unit tests. Run explicitly on Windows; no network is used."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / "extract_lgmg.py"
spec = importlib.util.spec_from_file_location("extract_lgmg", MODULE)
lgmg = importlib.util.module_from_spec(spec); spec.loader.exec_module(lgmg)

PAIR_HTML = """<html><head><link rel='canonical' href='https://www.lgmglifts.com/es/product/pro-detail-1.htm'></head>
<body><h1>S0607E-2 (S1932E-2)</h1><nav class='breadcrumb'>Inicio Elevadores de Tijera</nav>
<table><tr><th>Modelo métrico (imperial)</th><td>S0607E-2 (S1932E-2)</td></tr>
<tr><th>Altura máxima de trabajo</th><td>7.8 m</td><td>25 ft 7 in</td></tr>
<tr><th>Fuente de potencia</th><td>24V batería</td></tr></table>
<img data-src='/upload/s0607.png' alt='original'><img src='/upload/s0607.png'></body></html>"""

class ParsingTests(unittest.TestCase):
    def test_metric_imperial_pair_table_and_lazy_image(self):
        product = lgmg.parse_product(PAIR_HTML, "https://www.lgmglifts.com/es/product/pro-detail-1.htm")
        self.assertEqual((product["metric_model"], product["imperial_model"]), ("S0607E-2", "S1932E-2"))
        self.assertEqual(product["specifications"][1]["normalized_key"], "maximum_working_height")
        self.assertEqual(len(product["images"]), 1); self.assertTrue(product["is_electric"])

    def test_single_model(self):
        product = lgmg.parse_product("<h1>SR1218D</h1>", "https://www.lgmglifts.com/es/product/pro-detail-2.htm")
        self.assertEqual(product["metric_model"], "SR1218D"); self.assertIsNone(product["imperial_model"])

    def test_ambiguous_pair_needs_review(self):
        product = lgmg.parse_product("<h1>SS0507E (SS1432E)</h1>", "https://www.lgmglifts.com/es/product/pro-detail-3.htm")
        self.assertTrue(product["needs_review"])

    def test_electric_uncertain_not_suffix_based(self):
        product = lgmg.parse_product("<h1>ABC10E</h1>", "https://www.lgmglifts.com/es/product/pro-detail-4.htm")
        self.assertIsNone(product["is_electric"])

    def test_discovery_order_and_deduplication(self):
        p = lgmg.CatalogueParser("https://www.lgmglifts.com/es/product/pro-list-377.htm")
        p.feed("<a href='pro-detail-1.htm'>A</a><a href='pro-detail-1.htm'>A</a><a href='pro-detail-2.htm'>B</a>")
        self.assertEqual(len(lgmg.dedupe(p.links)), 2)

class SafetyTests(unittest.TestCase):
    def test_url_rejected(self):
        with self.assertRaises(ValueError): lgmg.canonical_url("http://www.lgmglifts.com/es/product/pro-detail-1.htm")
        with self.assertRaises(ValueError): lgmg.canonical_url("https://evil.example/es/product/pro-detail-1.htm")

    def test_redirect_outside_host_rejected(self):
        handler = lgmg.SafeRedirectHandler()
        with self.assertRaises(ValueError): handler.redirect_request(None, None, 302, "", {}, "https://evil.example/x")

    def test_filename_sanitized(self): self.assertEqual(lgmg.safe_filename("../S0607 E!*"), "s0607-e")

    def test_download_requires_confirmation(self):
        args = type("Args", (), {"download_images": True, "download_datasheets": False, "confirm_image_rights": False})()
        with self.assertRaises(ValueError): lgmg.validate_download_flags(args)

    def test_dangerous_outputs_rejected(self):
        with self.assertRaises(ValueError): lgmg.validate_output_dir("/")
        with self.assertRaises(ValueError): lgmg.validate_output_dir(str(Path.home()))
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(lgmg.validate_output_dir(str(Path(temp) / "sample")), Path(temp).resolve() / "sample")

if __name__ == "__main__": unittest.main()
