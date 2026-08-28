"""Synthetic unit tests. Run explicitly on Windows; no network is used."""
import csv
import importlib.util
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

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
    def test_node_text_preserves_document_order_without_artificial_spaces(self):
        parser = lgmg.CatalogueParser("https://www.lgmglifts.com/es/product/pro-detail-1.htm")
        parser.feed("<div>antes<strong>S1413</strong>Ⅱ<span>después</span></div>")
        node = next(parser.root.descendants("div"))
        self.assertEqual(node.text, "antesS1413Ⅱdespués")

    def test_model_rows_are_identified_by_the_first_cell(self):
        cases = (
            ("<tr><td>Modelos</td><td><span>SR1218E</span></td><td><strong>SR4069E</strong></td></tr>", ("SR1218E", "SR4069E")),
            ("<tr><td>Modelo métrico (imperial)</td><td>SR1218E(SR4069E)</td></tr>", ("SR1218E", "SR4069E")),
            ("<tr><td>MODELOS</td><td><strong>S1413</strong>Ⅱ</td><td><strong>S4650Ⅱ</strong></td></tr>", ("S1413Ⅱ", "S4650Ⅱ")),
            ("<tr><td>MODÈLE:</td><td>M0407TE</td><td>M1230TE</td></tr>", ("M0407TE", "M1230TE")),
        )
        for row, expected in cases:
            parser = lgmg.CatalogueParser("https://www.lgmglifts.com/es/product/pro-detail-1.htm")
            parser.feed(f"<section class='pro_detail'><table class='datalist'>{row}</table></section>")
            evidence = lgmg.normalize_models("", parser.rows)["model_evidence"]
            self.assertEqual((evidence[-1]["metric_model"], evidence[-1]["imperial_model"]), expected)

        result = lgmg.normalize_models("SR1218E(SR4069E)", [["Medidas", "Métrique", "Impériale"]])
        self.assertEqual([item["source"] for item in result["model_evidence"]], ["source_product_title"])

    def test_partial_and_complete_model_evidence_conflicts_only_on_present_values(self):
        matching = (
            [["Modelos", "SR1218E"]],
            [["Modelos", "SR1218E", "SR4069E"]],
        )
        for rows in matching:
            result = lgmg.normalize_models("SR1218E(SR4069E)", rows)
            self.assertFalse(result["needs_review"]); self.assertEqual(result["warnings"], [])
        for rows in ([["Modelos", "SR1323E"]], [["Modelos", "SR1323E", "SR4390E"]]):
            result = lgmg.normalize_models("SR1218E(SR4069E)", rows)
            self.assertTrue(result["needs_review"])
            self.assertIn("Conflicto entre fuentes estructuradas para el modelo", result["warnings"])

    def test_known_pairs_and_unicode_roman_numerals(self):
        for pair in ("S1413Ⅱ(S4650Ⅱ)", "SR1218E(SR4069E)", "T20JE(T65JE)", "M0407TE(M1230TE)"):
            product = lgmg.parse_product(detail(pair), "https://www.lgmglifts.com/es/product/pro-detail-1.htm")
            expected = pair.replace(")", "").split("(")
            self.assertEqual((product["metric_model"], product["imperial_model"]), tuple(expected))
            self.assertFalse(product["needs_review"]); self.assertEqual(product["warnings"], [])

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

    def test_strong_electric_and_weak_power_evidence(self):
        positive = ("24V 145Ah", "48 V DC 315 Ah", "80 V CC 375 Ah", "Batería de litio", "Batería de plomo-ácido")
        weak = ("24 V", "Fuente de potencia genérica", "25kW/33.5hp")
        for value in positive:
            specs = lgmg.parse_specs([["Fuente de potencia", value]])
            self.assertIs(lgmg.classify_electric(None, specs)[0], True, value)
        for value in weak:
            specs = lgmg.parse_specs([["Fuente de potencia", value]])
            self.assertIsNone(lgmg.classify_electric(None, specs)[0], value)

    def test_combustion_conflicts_and_evidence_are_preserved(self):
        for value in ("Kubota 18.2kW/24.4hp", "Deutz D2.9L4 / Kubota V2403", "Motor diesel", "Motor diésel"):
            specs = lgmg.parse_specs([["Fuente de potencia", value]])
            self.assertIs(lgmg.classify_electric(None, specs)[0], False, value)
        suffix_product = lgmg.parse_product(
            detail("ABC10E(ABC30E)").replace("48V batería", "Kubota 18.2kW/24.4hp"),
            "https://www.lgmglifts.com/es/product/pro-detail-40.htm",
        )
        self.assertIs(suffix_product["is_electric"], False)
        conflicts = (
            detail().replace("<div class='tit'>SR1218E(SR4069E)</div>",
                             "<div class='tit'>Equipo eléctrico SR1218E(SR4069E)</div>").replace("48V batería", "Kubota V2403"),
            detail().replace("48V batería", "Batería 48 V 260 Ah</td></tr><tr><th>Fuente de potencia</th><td>Deutz D2.9L4"),
        )
        for document in conflicts:
            product = lgmg.parse_product(document, "https://www.lgmglifts.com/es/product/pro-detail-41.htm")
            self.assertIsNone(product["is_electric"])
            self.assertIn("Conflicto entre evidencia eléctrica y de combustión; clasificación pendiente", product["warnings"])
            self.assertTrue(any("bater" in item.casefold() or "eléctr" in item.casefold() for item in product["electric_evidence"]))
            self.assertTrue(any("kubota" in item.casefold() or "deutz" in item.casefold() for item in product["electric_evidence"]))

    def test_electric_only_flow_separates_confirmed_combustion_and_uncertain(self):
        urls = [f"https://www.lgmglifts.com/es/product/pro-detail-{number}.htm" for number in (51, 52, 53)]
        documents = (
            detail("BAT10E(BAT30E)"),
            detail("ENG10E(ENG30E)").replace("48V batería", "Kubota 18.2kW/24.4hp"),
            detail("UNK10E(UNK30E)").replace("<tr><th>Fuente de potencia</th><td>48V batería</td></tr>", ""),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); seed = root / "seed.txt"; seed.write_text("\n".join(urls), encoding="utf-8")
            output = root / "output"
            fetched = mock.Mock(side_effect=[b"User-agent: *\nAllow: /\n", *(item.encode() for item in documents)])
            with mock.patch.object(lgmg.Fetcher, "fetch", fetched):
                self.assertEqual(lgmg.main(["--seed-file", str(seed), "--output-dir", str(output),
                                            "--max-products", "3", "--electric-only"]), 0)
            catalog = lgmg.json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            manifest = lgmg.json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            errors = lgmg.json.loads((output / "errors.json").read_text(encoding="utf-8"))
            with (output / "catalog.csv").open(encoding="utf-8-sig", newline="") as stream:
                catalog_rows = list(csv.DictReader(stream))
            with (output / "review.csv").open(encoding="utf-8-sig", newline="") as stream:
                review_rows = list(csv.DictReader(stream))
            self.assertEqual([item["metric_model"] for item in catalog], ["BAT10E"])
            self.assertEqual([item["metric_model"] for item in catalog_rows], ["BAT10E"])
            self.assertEqual([item["metric_model"] for item in review_rows], ["UNK10E"])
            self.assertEqual({key: manifest[key] for key in ("processed_count", "electric_confirmed", "non_electric_skipped",
                "skipped_count", "classification_uncertain", "images_downloaded", "datasheets_downloaded")},
                {"processed_count": 1, "electric_confirmed": 1, "non_electric_skipped": 1, "skipped_count": 1,
                 "classification_uncertain": 1, "images_downloaded": 0, "datasheets_downloaded": 0})
            self.assertEqual(errors, []); self.assertFalse(manifest["jem_nexus_called"] or manifest["content_published"])
            self.assertEqual(fetched.call_count, 4)

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


CONFIG = """seajs.config({base:'/es/resources/web/', paths:{js:'js'}, alias:{'js/pro_list':'js/pro_list'}});"""
PRODUCT_DATA = """flag:'pro', min1:data1, max1:data2, min2:data3, max2:data4,
min3:data5, max3:data6, min4:data7, max4:data8, catId:catId, key:key,
nowPage:nowPage, gmzhi:gmzhi"""
OFFICIAL_MODULE = """
var catId='', data1='', data2='', data3='', data4='', data5='', data6='', data7='', data8='', key='';
var gmzhi=1, nowPage=1;
function searchParam(){ $.ajax({url:seajs.root + '/ext/ajax_proList.jsp', type:'get', dataType:'html',
  data:{flag:'param', catId:catId, gmzhi:gmzhi}}); }
function searchPro(){ $.post(seajs.root + "/ext/ajax_proList.jsp", {%s}, function(data){
  if(nowPage == 1){ $("#container").html(data); } else { $("#container").append(data); }
}); }
""" % PRODUCT_DATA


def run_dynamic_discovery(families, pages, max_products):
    boxes = "".join(f"<div class='box' data-id='{key}'>{name}</div>" for key, name in families)
    index = (f"<script id='seajsConfig' src='/es/resources/web/seajs.config.js' domain='{lgmg.SEAJ_DOMAIN}'></script>"
             "<script>seajs.use('js/pro_list')</script>"
             f"<section class='channel_content pro_list'><div class='type_box'>{boxes}</div></section>").encode()
    endpoint_calls = []

    def controlled(url, kind, **kwargs):
        if kind == "listing": return index, "text/html"
        if kind == "config": return CONFIG.encode(), "application/javascript"
        if kind == "module": return OFFICIAL_MODULE.encode(), "application/javascript"
        params = kwargs["parameters"]
        marker = (str(params["catId"]), int(params["nowPage"])); endpoint_calls.append(marker)
        links = "".join(f"<a href='/es/product/pro-detail-{value}.htm'>Ficha</a>" for value in pages.get(marker, ()))
        return links.encode(), "text/html"

    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "output"
        arguments = ["--start-url", "https://www.lgmglifts.com/es/product/pro-list-377.htm",
                     "--output-dir", str(output), "--discovery-mode", "dynamic", "--discovery-only",
                     "--max-products", str(max_products)]
        with mock.patch.object(lgmg.Fetcher, "fetch", return_value=b"User-agent: *\nAllow: /\n") as fetch, \
             mock.patch.object(lgmg.Fetcher, "fetch_controlled", side_effect=controlled):
            exit_code = lgmg.main(arguments)
        result = {
            "exit_code": exit_code,
            "fetch_calls": fetch.call_count,
            "endpoint_calls": endpoint_calls,
            "report": lgmg.json.loads((output / "discovery.json").read_text(encoding="utf-8")),
            "manifest": lgmg.json.loads((output / "manifest.json").read_text(encoding="utf-8")),
        }
        with (output / "discovery.csv").open(encoding="utf-8-sig", newline="") as stream:
            result["rows"] = list(csv.DictReader(stream))
        return result


class DynamicInspectionTests(unittest.TestCase):
    def test_strict_limit_stops_within_first_page(self):
        result = run_dynamic_discovery(
            (("377", "Tijeras"),),
            {("377", 1): ("1", "2", "3", "4", "5")},
            3,
        )
        self.assertEqual([row["url"].rsplit("-", 1)[-1] for row in result["rows"]], ["1.htm", "2.htm", "3.htm"])
        self.assertEqual(result["endpoint_calls"], [("377", 1)])
        self.assertEqual(result["fetch_calls"], 1)
        self.assertEqual(result["report"]["families"][0]["status"], "stopped_by_limit")
        self.assertEqual((result["report"]["details_found"], result["report"]["details_unique"]), (3, 3))
        self.assertEqual((result["manifest"]["discovered_count"], result["manifest"]["detail_urls_discovered"],
                          result["manifest"]["detail_urls_unique"]), (3, 3, 3))

    def test_strict_limit_across_families_ignores_duplicates(self):
        first = tuple(str(value) for value in range(1, 22)); second = tuple(str(value) for value in range(22, 31))
        result = run_dynamic_discovery(
            (("377", "Familia A"), ("378", "Familia B"), ("379", "Familia C")),
            {("377", 1): first + first, ("378", 1): second + second, ("379", 1): ("31",)},
            25,
        )
        families = result["report"]["families"]
        self.assertEqual([(row["id"], row["unique"], row["status"]) for row in families],
                         [("377", 21, "complete_empty_page"), ("378", 4, "stopped_by_limit")])
        self.assertEqual(len(result["rows"]), 25)
        self.assertTrue(result["rows"][-1]["url"].endswith("pro-detail-25.htm"))
        self.assertNotIn(("379", 1), result["endpoint_calls"])
        self.assertEqual((result["report"]["details_found"], result["report"]["details_unique"]), (25, 25))
        self.assertEqual((result["manifest"]["requested_count"], result["manifest"]["discovered_count"],
                          result["manifest"]["detail_urls_discovered"], result["manifest"]["detail_urls_unique"]),
                         (25, 25, 25, 25))

    def test_natural_exhaustion_below_limit_remains_dynamic_listing(self):
        result = run_dynamic_discovery(
            (("377", "Familia A"), ("378", "Familia B")),
            {("377", 1): ("1", "2", "2"), ("378", 1): ("3", "4")},
            10,
        )
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(result["report"]["status"], "dynamic_listing")
        self.assertNotIn("stopped_by_limit", [family["status"] for family in result["report"]["families"]])
        self.assertEqual((result["report"]["details_found"], result["report"]["details_unique"]), (4, 4))
        self.assertEqual((result["manifest"]["discovered_count"], result["manifest"]["detail_urls_discovered"],
                          result["manifest"]["detail_urls_unique"]), (4, 4, 4))

    def test_detects_official_seajs_config_structurally(self):
        documents = (
            '''<script src="/es/resources/web/seajs.config.js" id="seajsConfig"
                       domain="https://www.lgmglifts.com/es"></script>''',
            "<SCRIPT DOMAIN='https://www.lgmglifts.com/es' ID='seajsConfig' SRC='/es/resources/web/seajs.config.js'></SCRIPT>",
        )
        for document in documents:
            with self.subTest(document=document):
                self.assertEqual(
                    lgmg.detect_seajs_config(document, "https://www.lgmglifts.com/es/product/pro-list-377.htm"),
                    "https://www.lgmglifts.com/es/resources/web/seajs.config.js",
                )

    def test_seajs_config_requires_exactly_one_script(self):
        valid = "<script id='seajsConfig' src='/es/resources/web/seajs.config.js' domain='https://www.lgmglifts.com/es'></script>"
        for document in ("", valid + valid, valid.replace("script", "link")):
            with self.subTest(document=document), self.assertRaises(lgmg.DiscoveryError):
                lgmg.detect_seajs_config(document, "https://www.lgmglifts.com/es/product/pro-list-377.htm")

    def test_seajs_config_rejects_missing_attributes_and_unofficial_domain(self):
        template = "<script id='seajsConfig' src='{src}' domain='{domain}'></script>"
        cases = (("", lgmg.SEAJ_DOMAIN), ("/es/resources/web/seajs.config.js", ""),
                 ("/es/resources/web/seajs.config.js", "https://evil.example/es"),
                 ("/es/resources/web/seajs.config.js", "http://www.lgmglifts.com/es"),
                 ("/es/resources/web/seajs.config.js", "https://www.lgmglifts.com:444/es"),
                 ("/es/resources/web/seajs.config.js", "https://user@www.lgmglifts.com/es"),
                 ("/es/resources/web/seajs.config.js", "https://www.lgmglifts.com/es?x=1"),
                 ("/es/resources/web/seajs.config.js", "https://www.lgmglifts.com/es#x"))
        for src, domain in cases:
            with self.subTest(src=src, domain=domain), self.assertRaises(lgmg.DiscoveryError):
                lgmg.detect_seajs_config(template.format(src=src, domain=domain), "https://www.lgmglifts.com/es/product/pro-list-377.htm")

    def test_seajs_config_rejects_unsafe_or_old_sources(self):
        sources = (
            "http://www.lgmglifts.com/es/resources/web/seajs.config.js",
            "https://www.lgmglifts.com:444/es/resources/web/seajs.config.js",
            "https://user:pass@www.lgmglifts.com/es/resources/web/seajs.config.js",
            "https://evil.example/es/resources/web/seajs.config.js",
            "/es/resources/web/seajs.config.js?x=1", "/es/resources/web/seajs.config.js#x",
            "/es/resources/../resources/web/seajs.config.js",
            "/es/resources/web/js/seajs.config.js",
        )
        for src in sources:
            document = f"<script id='seajsConfig' src='{src}' domain='{lgmg.SEAJ_DOMAIN}'></script>"
            with self.subTest(src=src), self.assertRaises(lgmg.DiscoveryError):
                lgmg.detect_seajs_config(document, "https://www.lgmglifts.com/es/product/pro-list-377.htm")

    def test_detects_only_expected_seajs_module(self):
        self.assertEqual(lgmg.detect_seajs_module("<script>seajs.use('js/pro_list')</script>"), "js/pro_list")
        for source in ("", "seajs.use('js/other')", "seajs.use('js/pro_list');seajs.use('js/other')"):
            with self.assertRaises(lgmg.DiscoveryError): lgmg.detect_seajs_module(source)

    def test_resolves_literal_config(self):
        self.assertEqual(lgmg.resolve_seajs_module(CONFIG), "https://www.lgmglifts.com/es/resources/web/js/pro_list.js")

    def test_resolves_official_root_config_with_comments(self):
        source = '''seajs.config({
          base: seajs.root + "/resources/modules",
          paths: {"js": seajs.root + "/resources/web/js", "lib": seajs.root + "/resources/web/lib",},
          alias: {"audio": "audio/audio", // comentario
                  "seajs-localcache": "seajs/seajs-localcache",},
        });'''
        self.assertEqual(
            lgmg.resolve_seajs_module(source, "js/pro_list", lgmg.SEAJ_DOMAIN),
            "https://www.lgmglifts.com/es/resources/web/js/pro_list.js",
        )
        reordered = '''seajs.config({alias:{}, paths:{js : seajs.root+"/resources/web/js"},
                                     base : seajs.root + "/resources/modules"});'''
        self.assertEqual(lgmg.resolve_seajs_module(reordered),
                         "https://www.lgmglifts.com/es/resources/web/js/pro_list.js")

    def test_comment_stripper_preserves_strings_and_newlines(self):
        source = "alias:{url:'https://example.test/a//b',/* block\ncomment */name:'ok'}// end\n"
        stripped = lgmg._strip_javascript_comments(source)
        self.assertIn("'https://example.test/a//b'", stripped)
        self.assertEqual(stripped.count("\n"), source.count("\n"))
        self.assertNotIn("block", stripped)

    def test_comment_stripper_rejects_unterminated_content_and_templates(self):
        for source in ("/* unterminated", "'unterminated", '"unterminated', "`template`"):
            with self.subTest(source=source), self.assertRaises(lgmg.DiscoveryError):
                lgmg._strip_javascript_comments(source)

    def test_root_value_accepts_only_official_shape(self):
        invalid = (
            'window.location.origin + "/resources/web/js"',
            'domain + "/resources/web/js"',
            'getRoot() + "/resources/web/js"',
            'seajs.root + variable',
            'seajs.root + "/resources/web" + variable',
            'seajs.root || "/resources/web/js"',
        )
        for value in invalid:
            source = f"seajs.config({{paths:{{js:{value}}},alias:{{}}}})"
            with self.subTest(value=value), self.assertRaises(lgmg.DiscoveryError):
                lgmg.resolve_seajs_module(source)

    def test_root_suffix_validation_rejects_unsafe_paths(self):
        suffixes = (
            "/other/web/js", "https://evil.example/resources/web/js", "/resources/web/js?x=1",
            "/resources/web/js#x", "/resources/../web/js", "/resources//web/js",
            "/resources/web\\js", "/resources/web/\x01js",
        )
        for suffix in suffixes:
            source = f'''seajs.config({{paths:{{js:seajs.root + "{suffix}"}},alias:{{}}}})'''
            with self.subTest(suffix=suffix), self.assertRaises(lgmg.DiscoveryError):
                lgmg.resolve_seajs_module(source)

    def test_alias_remains_literal_only(self):
        source = '''seajs.config({paths:{js:seajs.root + "/resources/web/js"},
                    alias:{"js/pro_list":seajs.root + "/resources/web/js/pro_list"}})'''
        with self.assertRaises(lgmg.DiscoveryError):
            lgmg.resolve_seajs_module(source)

    def test_ambiguous_or_residual_config_is_rejected(self):
        duplicate = CONFIG + CONFIG
        residue = "seajs.config({paths:{js:'js' hidden},alias:{}})"
        for source in (duplicate, residue):
            with self.subTest(source=source), self.assertRaises(lgmg.DiscoveryError):
                lgmg.resolve_seajs_module(source)

    def test_validated_domain_is_the_only_root_source(self):
        source = '''seajs.config({paths:{js:seajs.root + "/resources/web/js"},alias:{}})'''
        self.assertEqual(lgmg.resolve_seajs_module(source, seajs_root=lgmg.SEAJ_DOMAIN),
                         "https://www.lgmglifts.com/es/resources/web/js/pro_list.js")
        with self.assertRaises(lgmg.DiscoveryError):
            lgmg.resolve_seajs_module(source, seajs_root="https://evil.example/es")

    def test_controlled_http_and_network_errors_are_sanitized_and_not_cached(self):
        errors = (
            HTTPError(lgmg.SEAJ_CONFIG_URL, 404, "Not Found", {}, BytesIO(b"secret body")),
            HTTPError(lgmg.SEAJ_CONFIG_URL, 403, "Forbidden", {}, BytesIO(b"secret body")),
            URLError("credential-bearing server detail"),
            TimeoutError("timed out with server detail"),
        )
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "cache"
            fetcher = lgmg.Fetcher(cache, 0, 5, "test")
            for error in errors:
                opener = mock.Mock(); opener.open.side_effect = error
                with self.subTest(error=type(error).__name__), mock.patch.object(lgmg, "build_opener", return_value=opener):
                    with self.assertRaises(lgmg.DiscoveryError) as raised:
                        fetcher.fetch_controlled(lgmg.SEAJ_CONFIG_URL, "config")
                    message = str(raised.exception)
                    self.assertIn("config:", message)
                    self.assertNotIn("secret", message)
            self.assertEqual(list(cache.glob("*")), [])

    def test_dynamic_config_failure_writes_diagnostics_and_returns_three(self):
        index = b"""<script id='seajsConfig' src='/es/resources/web/seajs.config.js'
            domain='https://www.lgmglifts.com/es'></script><script>seajs.use('js/pro_list')</script>"""
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            controlled = mock.Mock(side_effect=[(index, "text/html"), lgmg.DiscoveryError("config: HTTP 404 al solicitar recurso controlado")])
            arguments = ["--start-url", "https://www.lgmglifts.com/es/product/pro-list-377.htm",
                         "--output-dir", str(output), "--discovery-mode", "dynamic", "--discovery-only"]
            with mock.patch.object(lgmg.Fetcher, "fetch", return_value=b"User-agent: *\nAllow: /\n"), \
                 mock.patch.object(lgmg.Fetcher, "fetch_controlled", controlled):
                self.assertEqual(lgmg.main(arguments), 3)
            manifest = lgmg.json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            discovery = lgmg.json.loads((output / "discovery.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["discovery_status"], "dynamic_inspection_required")
            self.assertEqual(discovery["config_url"], lgmg.SEAJ_CONFIG_URL)
            self.assertEqual((manifest["images_downloaded"], manifest["datasheets_downloaded"]), (0, 0))
            self.assertFalse(manifest["jem_nexus_called"] or manifest["content_published"])
            expected = ("manifest.json", "discovery.json", "discovery.csv", "families.csv",
                        "catalog.json", "catalog.csv", "review.csv", "errors.json")
            self.assertTrue(all((output / name).is_file() for name in expected))

    def test_invalid_cli_arguments_keep_argparse_exit_code(self):
        with self.assertRaises(SystemExit) as raised:
            lgmg.build_parser().parse_args([])
        self.assertEqual(raised.exception.code, 2)

    def test_literal_object_accepts_safe_key_forms_and_layout(self):
        source = """paths: {
            js: 'js',
            $resource: "modules",
        } alias: { "js/pro_list": "js/pro_list" }"""
        self.assertEqual(lgmg._literal_object(source, "paths"), {"js": "js", "$resource": "modules"})
        self.assertEqual(lgmg._literal_object(source, "alias"), {"js/pro_list": "js/pro_list"})
        self.assertEqual(
            lgmg._literal_object("alias:{'js/pro_list':'js/pro_list'}", "alias"),
            {"js/pro_list": "js/pro_list"},
        )

    def test_literal_object_rejects_unsafe_quoted_keys(self):
        keys = (
            "/js/pro_list", "js/pro_list/", "js//pro_list", ".", "..", "../pro_list",
            "js/../pro_list", r"js\pro_list", "https://example.com/module", "js/pro_list?x=1",
            "js/pro_list#fragment", "js pro_list",
        )
        for key in keys:
            with self.subTest(key=key), self.assertRaises(lgmg.DiscoveryError):
                lgmg._literal_object(f"alias:{{'{key}':'js/pro_list'}}", "alias")

    def test_literal_object_rejects_nonliteral_values_and_residue(self):
        bodies = (
            "js/pro_list:'js/pro_list'",
            "'js/pro_list':moduleName",
            "'js/pro_list':'js/' + 'pro_list'",
            "'js/pro_list':'js/pro_list' hidden",
        )
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(lgmg.DiscoveryError):
                lgmg._literal_object(f"alias:{{{body}}}", "alias")

    def test_module_scope_rejects_cross_origin_and_traversal(self):
        for source in (
            "seajs.config({base:'https://evil.example/es/resources/',alias:{'js/pro_list':'js/pro_list'}})",
            "seajs.config({base:'/es/resources/web/',alias:{'js/pro_list':'../pro_list'}})",
        ):
            with self.assertRaises(lgmg.DiscoveryError): lgmg.resolve_seajs_module(source)

    def test_html_cannot_pose_as_javascript(self):
        with self.assertRaises(lgmg.DiscoveryError): lgmg.validate_javascript("<!doctype html><title>Error</title>")

    def test_official_parameter_ajax_is_excluded_and_product_post_selected(self):
        operation = lgmg.parse_listing_module(OFFICIAL_MODULE)
        self.assertEqual(operation["endpoint"], lgmg.LISTING_ENDPOINT_URL)
        self.assertEqual((operation["method"], operation["body_format"], operation["response_container"]),
                         ("POST", "application/x-www-form-urlencoded", "html"))
        self.assertEqual((operation["category_parameter"], operation["page_parameter"]), ("catId", "nowPage"))
        self.assertEqual((operation["initial_page"], operation["page_size_parameter"]), (1, None))
        self.assertEqual(operation["parameters"]["flag"], "pro")
        self.assertEqual(operation["parameters"]["gmzhi"], 1)
        self.assertTrue(all(operation["parameters"][key] == "" for key in
                            ("min1", "max1", "min2", "max2", "min3", "max3", "min4", "max4", "key")))

    def test_ambiguous_external_authenticated_and_unknown_methods_fail(self):
        cases = (
            OFFICIAL_MODULE + OFFICIAL_MODULE,
            OFFICIAL_MODULE.replace("seajs.root + \"/ext/ajax_proList.jsp\"", "'https://evil.example/ext/ajax_proList.jsp'"),
            OFFICIAL_MODULE.replace("/ext/ajax_proList.jsp\"", "/ext/alternate.jsp\""),
            OFFICIAL_MODULE.replace("function searchParam", "token='secret'; function searchParam"),
            OFFICIAL_MODULE.replace("$.post", "$.get"),
            OFFICIAL_MODULE.replace("catId:catId", "catId:makeCategory()"),
        )
        for source in cases:
            with self.assertRaises(lgmg.DiscoveryError): lgmg.parse_listing_module(source)

    def test_product_schema_is_closed_and_order_independent(self):
        reordered = OFFICIAL_MODULE.replace("{%s}" % PRODUCT_DATA, "{%s}" % ",".join(reversed(PRODUCT_DATA.split(","))))
        self.assertEqual(set(lgmg.parse_listing_module(reordered)["parameters"]),
                         set(lgmg.parse_listing_module(OFFICIAL_MODULE)["parameters"]))
        for source in (OFFICIAL_MODULE.replace("gmzhi:gmzhi", "gmzhi:gmzhi, extra:''"),
                       OFFICIAL_MODULE.replace(", gmzhi:gmzhi", ""),
                       OFFICIAL_MODULE.replace("key:key", "key:key, key:key")):
            with self.assertRaises(lgmg.DiscoveryError): lgmg.parse_listing_module(source)

    def test_post_comments_whitespace_and_balanced_callback_are_safe(self):
        source = OFFICIAL_MODULE.replace("$.post(", "/* product */ $ . post (\n").replace(
            "if(nowPage == 1)", "if(nowPage == 1 /* comma, brace } */)")
        operation = lgmg.parse_listing_module(source)
        self.assertEqual(operation["method"], "POST")
        incomplete = OFFICIAL_MODULE.replace("}); }\n", " }\n")
        with self.assertRaises(lgmg.DiscoveryError): lgmg.parse_listing_module(incomplete)

    def test_dynamic_endpoint_and_initializers_are_rejected(self):
        cases = (OFFICIAL_MODULE.replace('seajs.root + "/ext/ajax_proList.jsp"', "seajs.root + endpoint"),
                 OFFICIAL_MODULE.replace("var gmzhi=1", "var gmzhi=getMetric()"),
                 OFFICIAL_MODULE.replace("var gmzhi=1", "var gmzhi=`1`"),
                 OFFICIAL_MODULE.replace("var gmzhi=1", "var gmzhi=localStorage.metric"))
        for source in cases:
            with self.assertRaises(lgmg.DiscoveryError): lgmg.parse_listing_module(source)

    def test_family_extraction_requires_type_box_box_and_preserves_order(self):
        names = (("377", "Elevadores de Tijera"), ("378", "Elevador Eléctrico RT de Tijera"),
                 ("379", "Elevadores de Brazo Articulado"), ("380", "Elevadores de Brazo Telescópico"),
                 ("735", "Elevador Mástil Vertical"), ("736", "Elevador de Tijera Sobre Orugas"),
                 ("739", "Manipuladores Telescópicos"), ("999", "Familia futura"))
        boxes = "".join(f"<div class='box box1' data-id='{key}'>{name}</div>" for key, name in names)
        document = ("<section class='channel_content pro_list'><div class='left'><div data-id='1'>Métrico</div>"
                    "<div data-id='2'>Imperial</div></div><div class='type_box'>" + boxes +
                    "</div><div class='box' data-id='888'>Fuera</div></section><div class='type_box'><div class='box' data-id='777'>Global</div></div>")
        parser = lgmg.CatalogueParser("https://www.lgmglifts.com/es/product/pro-list-377.htm"); parser.feed(document)
        self.assertEqual([(family["id"], family["name"]) for family in parser.families], list(names))

    def test_html_json_html_and_structured_json_responses(self):
        family = {"id": "7", "name": "Tijeras"}; base = "https://www.lgmglifts.com/es/product/pro-list-377.htm"
        payloads = (
            ("<a href='/es/product/pro-detail-10.htm'>Uno</a>", "text/html"),
            ('{"html":"<a href=\\"/es/product/pro-detail-11.htm\\">Dos</a>"}', "application/json"),
            ('{"records":[{"detailUrl":"/es/product/pro-detail-12.htm"}]}', "application/json"),
        )
        for payload, content_type in payloads:
            accepted, rejected = lgmg.parse_dynamic_response(payload, content_type, base, family, 1)
            self.assertEqual(len(accepted), 1); self.assertEqual(rejected, [])

    def test_detail_filter_is_strict_and_global_links_are_rejected(self):
        payload = "<a href='/es/'>Inicio</a><a href='/es/product/pro-list-1.htm'>Lista</a><a href='/es/product/pro-detail-ABC_1.htm?q=bad'>Query</a><a href='/es/product/pro-detail-9.htm'>Ficha</a>"
        accepted, rejected = lgmg.parse_dynamic_response(payload, "text/html", "https://www.lgmglifts.com/es/product/pro-list-377.htm", {"id":"1","name":"A"}, 1)
        self.assertEqual([row["url"] for row in accepted], ["https://www.lgmglifts.com/es/product/pro-detail-9.htm"])
        self.assertEqual(len(rejected), 3)

    def test_deduplication_is_stable_across_pages_and_families(self):
        rows = [{"url":"https://www.lgmglifts.com/es/product/pro-detail-1.htm", "family":"A"},
                {"url":"https://www.lgmglifts.com/es/product/pro-detail-1.htm", "family":"A"},
                {"url":"https://www.lgmglifts.com/es/product/pro-detail-1.htm", "family":"B"}]
        unique = lgmg.deduplicate_discovery(rows)
        self.assertEqual(len(unique), 1); self.assertEqual([r["duplicate"] for r in rows], [False, True, True])

    def test_hard_limits_and_inventory_flag(self):
        self.assertEqual((lgmg.HARD_MAX_PAGES, lgmg.HARD_MAX_PRODUCTS), (50, 250))
        parser = lgmg.build_parser()
        args = parser.parse_args(["--start-url", "https://www.lgmglifts.com/es/product/pro-list-377.htm", "--output-dir", "/tmp/safe/out", "--inventory-all"])
        self.assertTrue(args.inventory_all); self.assertEqual(args.discovery_mode, "static")

    def test_family_name_alone_is_not_electric_evidence(self):
        electric, evidence = lgmg.classify_electric("Elevadores eléctricos", [], "Modelo ABC10")
        self.assertIsNone(electric); self.assertEqual(evidence, [])

    def test_uncertain_product_remains_reviewable(self):
        product = lgmg.parse_product(detail("ABC10E(ABC30E)", "Elevadores eléctricos").replace("<tr><th>Fuente de potencia</th><td>48V batería</td></tr>", ""), "https://www.lgmglifts.com/es/product/pro-detail-8.htm")
        self.assertIsNone(product["is_electric"]); self.assertTrue(product["needs_review"])

    def test_output_writers_cover_discovery_files_and_safe_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lgmg.write_json(root / "discovery.json", {"status":"dynamic_inspection_required"})
            lgmg.write_csv(root / "discovery.csv", ["url"], [{"url":"x"}])
            lgmg.write_csv(root / "families.csv", ["id"], [{"id":"1"}])
            manifest = {"discovery_status":"dynamic_listing", "images_downloaded":0, "datasheets_downloaded":0,
                        "jem_nexus_called":False, "content_published":False}
            lgmg.write_json(root / "manifest.json", manifest)
            self.assertTrue(all((root / name).is_file() for name in ("discovery.json","discovery.csv","families.csv","manifest.json")))
            self.assertFalse(manifest["jem_nexus_called"] or manifest["content_published"])

    def test_discovery_only_cli_is_explicit(self):
        args = lgmg.build_parser().parse_args(["--start-url", "https://www.lgmglifts.com/es/product/pro-list-377.htm",
            "--output-dir", "/tmp/safe/out", "--discovery-mode", "dynamic", "--discovery-only"])
        self.assertTrue(args.discovery_only); self.assertFalse(args.download_images or args.download_datasheets)

if __name__ == "__main__": unittest.main()
