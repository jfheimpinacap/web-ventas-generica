"""Synthetic unit tests. Run explicitly on Windows; no network is used."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / "extract_lgmg.py"
spec = importlib.util.spec_from_file_location("extract_lgmg", MODULE)
lgmg = importlib.util.module_from_spec(spec); spec.loader.exec_module(lgmg)


def detail(model="SR1218E(SR4069E)", category="Elevador Eléctrico RT de Tijera"):
    crumb = f"<a href='/es/product/pro-list-378.htm'>{category}</a>" if category else ""
    return f"""<html><head><title>SR4069E-ELEVADOR-LGMG</title></head><body>
<nav><a href='/es/product/pro-list-9.htm'>Menú contaminante</a><table><tr><td>Ajena</td><td>No</td></tr></table></nav>
<div class='crumbs r'><a href='/es' class='home'></a><a href='/es/product/pro-list-377.htm'>PRODUCTOS</a>{crumb}<span>{model}</span></div>
<section class='channel_content pro_detail pro_detail_down'>
<div class='pro_detail01'><div class='left l'><div class='infor'><div class='tit'>{model}</div></div></div>
<div class='right r fix'><div class='right_r'><div class='ul_box'><img bigSrc='/es/upload/images/a.jpg' alt='A'><img data-src='/es/upload/images/b.png'></div></div><div class='right_l'><img src='/es/upload/images/a.jpg'></div></div></div>
<div class='pro_detail02'><div class='right_b imgZoom'><img src='/es/upload/images/c.webp'></div><div class='right_t imgZoom'><img src='/es/upload/images/video.jpg'></div></div>
<table class='datalist'><tr><th>Modelo métrico (imperial)</th><td>{model}</td></tr><tr><th>Fuente de potencia</th><td>48V batería</td></tr></table>
<div class='new_box'><div class='tit'>Ficha técnica:</div><div class='country'><a href='/es/upload/file/ficha.pdf'><span>Spanish</span></a></div></div>
<div class='new_box'><div class='tit'>Catálogo completo de LGMG:</div><a href='/es/upload/file/general.pdf'>Spanish</a></div>
<div class='related'><img src='/es/upload/images/related.jpg'><a href='/es/product/pro-detail-99.htm'>Relacionado</a></div>
</section><footer><img src='/es/upload/images/logo.png'></footer></body></html>"""


class ParsingTests(unittest.TestCase):
    def test_known_pairs_and_unicode_roman_numerals(self):
        for pair in ("S1413Ⅱ(S4650Ⅱ)", "SR1218E(SR4069E)", "T20JE(T65JE)", "M0407TE(M1230TE)"):
            product = lgmg.parse_product(detail(pair), "https://www.lgmglifts.com/es/product/pro-detail-1.htm")
            expected = pair.replace(")", "").split("(")
            self.assertEqual((product["metric_model"], product["imperial_model"]), tuple(expected))

    def test_document_title_never_supplies_translated_model(self):
        product = lgmg.parse_product(detail(), "https://www.lgmglifts.com/es/product/pro-detail-1.htm")
        self.assertEqual(product["source_page_title"], "SR4069E-ELEVADOR-LGMG")
        self.assertEqual(product["source_product_title"], "SR1218E(SR4069E)")
        self.assertEqual(lgmg._models("SR4069E-ELEVADOR"), (None, None))

    def test_structural_category_specs_images_and_datasheet(self):
        product = lgmg.parse_product(detail(), "https://www.lgmglifts.com/es/product/pro-detail-1.htm")
        self.assertEqual(product["source_category"], "Elevador Eléctrico RT de Tijera")
        self.assertEqual(len(product["specifications"]), 2)
        self.assertEqual([i["url"].rsplit("/", 1)[-1] for i in product["images"]], ["a.jpg", "b.png", "c.webp"])
        self.assertEqual([d["name"] for d in product["datasheets"]], ["ficha.pdf"])
        self.assertIn("terreno irregular", product["display_name_suggestion"])

    def test_missing_category_requires_review(self):
        product = lgmg.parse_product(detail(category=""), "https://www.lgmglifts.com/es/product/pro-detail-1.htm")
        self.assertIsNone(product["source_category"]); self.assertTrue(product["needs_review"])

    def test_electric_uncertain_not_suffix_based(self):
        html = detail("ABC10E(ABC30E)", "Elevadores de Brazo Telescópico").replace("<tr><th>Fuente de potencia</th><td>48V batería</td></tr>", "")
        product = lgmg.parse_product(html, "https://www.lgmglifts.com/es/product/pro-detail-4.htm")
        self.assertIsNone(product["is_electric"]); self.assertNotIn("eléctrico", product["display_name_suggestion"])

    def test_listing_scope_dynamic_and_static(self):
        parser = lgmg.CatalogueParser("https://www.lgmglifts.com/es/product/pro-list-377.htm")
        parser.feed("<a href='/es/product/pro-detail-1.htm'>Global</a><section class='pro_list channel_content'><ul id='container'></ul></section>")
        self.assertEqual(parser.links, [])
        parser = lgmg.CatalogueParser("https://www.lgmglifts.com/es/product/pro-list-377.htm")
        parser.feed("<a href='/es/product/pro-detail-1.htm'>Global</a><section class='channel_content pro_list'><ul id='container'><li><a href='/es/product/pro-detail-2.htm'>Real</a></li></ul></section>")
        self.assertEqual(parser.links, ["https://www.lgmglifts.com/es/product/pro-detail-2.htm"])


class SafetyTests(unittest.TestCase):
    def test_url_rejected(self):
        with self.assertRaises(ValueError): lgmg.canonical_url("http://www.lgmglifts.com/es/product/pro-detail-1.htm")
        with self.assertRaises(ValueError): lgmg.canonical_url("https://evil.example/es/product/pro-detail-1.htm")

    def test_redirect_outside_host_rejected(self):
        with self.assertRaises(ValueError): lgmg.SafeRedirectHandler().redirect_request(None, None, 302, "", {}, "https://evil.example/x")

    def test_download_requires_confirmation(self):
        args = type("Args", (), {"download_images": True, "download_datasheets": False, "confirm_image_rights": False})()
        with self.assertRaises(ValueError): lgmg.validate_download_flags(args)

    def test_dangerous_outputs_rejected(self):
        with self.assertRaises(ValueError): lgmg.validate_output_dir("/")
        with self.assertRaises(ValueError): lgmg.validate_output_dir(str(Path.home()))
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(lgmg.validate_output_dir(str(Path(temp) / "sample")), Path(temp).resolve() / "sample")

if __name__ == "__main__": unittest.main()
