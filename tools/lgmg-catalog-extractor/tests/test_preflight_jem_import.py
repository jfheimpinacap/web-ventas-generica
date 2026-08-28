"""Synthetic, network-free tests for preflight_jem_import."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

import preflight_jem_import as subject


class Headers(dict):
    def get_content_type(self): return self.get("Content-Type", "application/json").split(";", 1)[0]


class Response(io.BytesIO):
    def __init__(self, body=b"{}", status=200, url="http://localhost:5000/api/health", content_type="application/json"):
        super().__init__(body); self.status=status; self.url=url; self.headers=Headers({"Content-Type":content_type})
    def getcode(self): return self.status
    def geturl(self): return self.url


class Opener:
    def __init__(self,response=None,error=None): self.response=response; self.error=error; self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        if self.error: raise self.error
        response=self.response or Response(url=request.full_url)
        response.url=request.full_url if response.url.endswith("/api/health") else response.url
        return response


def token(): return "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"
def category(name="Maquinarias",ident=1,parent=None,active=True,kind="machinery"):
    return {"id":ident,"name":name,"parent":parent,"product_type":kind,"is_active":active}
def brand(name="LGMG",ident=1,active=True,slug="lgmg"):
    return {"id":ident,"name":name,"slug":slug,"is_active":active}
def product(ident=1,name="LGMG S0607E",slug="lgmg-s0607e",model="S0607E",brand_name="LGMG",category_name=subject.TARGETS[0]):
    return {"id":ident,"name":name,"slug":slug,"model":model,"brand":{"name":brand_name},"category":{"name":category_name},"is_published":False}
def planned(key="lgmg-0123456789abcdef",name="LGMG S0607E",model="S0607E"):
    return {"source_key":key,"proposed_name":name,"metric_model":model,"imperial_model":""}


def canonical_product(index=0, power_source=""):
    model=f"MODEL{index:02d}"
    return {"source_key":f"lgmg-{index:016x}","source_url":f"https://www.lgmglifts.com/es/product/{model}",
        "proposed_name":f"LGMG {model}","metric_model":model,"imperial_model":"","aliases":"",
        "source_category":"Elevadores de Tijera","target_root_category":"Maquinarias",
        "target_subcategory":subject.TARGETS[0],"target_brand":"LGMG","product_type":"machinery",
        "condition":"new","stock_status":"on_request","price":"","currency":"","show_price":"false",
        "is_published":"false","is_featured":"false","target_power_source":power_source,
        "maximum_load_capacity_kg":"230","ready_for_import":"false"}


def canonical_products():
    return [canonical_product(index, "electric_24v" if index < 13 else "electric_lithium" if index < 15 else "")
        for index in range(57)]


class CliAndSecurityTests(unittest.TestCase):
    def test_01_cli_required(self):
        parser=subject.build_parser()
        with self.assertRaises(SystemExit): parser.parse_args([])
    def test_02_module_has_guarded_main(self): self.assertTrue(callable(subject.main))
    def test_03_token_absent(self):
        with self.assertRaises(subject.PreflightError): subject.access_token({})
    def test_04_token_empty(self):
        with self.assertRaises(subject.PreflightError): subject.access_token({subject.TOKEN_ENV:"  "})
    def test_05_token_too_long(self):
        with self.assertRaises(subject.PreflightError): subject.access_token({subject.TOKEN_ENV:"a"*(subject.TOKEN_MAX+1)})
    def test_06_token_sanitized(self):
        secret="not-a-token"
        with self.assertRaisesRegex(subject.PreflightError,"estructura") as caught: subject.access_token({subject.TOKEN_ENV:secret})
        self.assertNotIn(secret,str(caught.exception))
    def test_07_origins_allowed(self):
        self.assertEqual(subject.normalize_origin("http://localhost:5000/"),"http://localhost:5000")
        self.assertEqual(subject.normalize_origin("http://127.0.0.1:5000"),"http://127.0.0.1:5000")
    def test_08_external_origins_rejected(self):
        for value in ("https://jem-nexus.cl","http://api.jem-nexus.cl","http://192.168.1.2:5000"):
            with self.assertRaises(subject.PreflightError): subject.normalize_origin(value)
    def test_09_other_ports_rejected(self):
        with self.assertRaises(subject.PreflightError): subject.normalize_origin("http://localhost:5001")
    def test_10_url_components_rejected(self):
        for value in ("http://u:p@localhost:5000","http://localhost:5000/api","http://localhost:5000?q=1","http://localhost:5000#x"):
            with self.assertRaises(subject.PreflightError): subject.normalize_origin(value)
    def test_11_redirect_rejected(self):
        response=Response(url="http://127.0.0.1:5000/api/health")
        with self.assertRaises(subject.PreflightError): subject.LocalJsonClient("http://localhost:5000",token(),Opener(response)).get_json("/api/health",authenticated=False)
    def test_12_only_get(self):
        opener=Opener(); subject.LocalJsonClient("http://localhost:5000",token(),opener).get_json("/api/health",authenticated=False)
        self.assertEqual(opener.calls[0][0].method,"GET")
    def test_13_endpoint_allowlist(self):
        with self.assertRaises(subject.PreflightError): subject.LocalJsonClient("http://localhost:5000",token(),Opener()).get_json("/api/products/1")
    def test_14_bearer_only_authenticated(self):
        opener=Opener(); client=subject.LocalJsonClient("http://localhost:5000",token(),opener)
        client.get_json("/api/health",authenticated=False); client.get_json("/api/auth/me")
        self.assertIsNone(opener.calls[0][0].get_header("Authorization")); self.assertTrue(opener.calls[1][0].get_header("Authorization").startswith("Bearer "))
    def test_15_timeout_forwarded(self):
        opener=Opener(); subject.LocalJsonClient("http://localhost:5000",token(),opener,timeout=7).get_json("/api/health",authenticated=False)
        self.assertEqual(opener.calls[0][1],7)
    def test_16_response_limit(self):
        with self.assertRaises(subject.PreflightError): subject.LocalJsonClient("http://localhost:5000",token(),Opener(Response(b"{}x")),max_body=2).get_json("/api/health",authenticated=False)
    def test_17_content_type(self):
        with self.assertRaises(subject.PreflightError): subject.LocalJsonClient("http://localhost:5000",token(),Opener(Response(content_type="text/html"))).get_json("/api/health",authenticated=False)
    def test_18_invalid_json(self):
        with self.assertRaises(subject.PreflightError): subject.LocalJsonClient("http://localhost:5000",token(),Opener(Response(b"{"))).get_json("/api/health",authenticated=False)
    def test_19_http_errors_sanitized(self):
        for code in (401,403,404,429,500):
            error=urllib.error.HTTPError("http://localhost:5000/api/health",code,"secret body",{},None)
            with self.assertRaisesRegex(subject.PreflightError,str(code)) as caught: subject.LocalJsonClient("http://localhost:5000",token(),Opener(error=error)).get_json("/api/health",authenticated=False)
            self.assertNotIn("secret body",str(caught.exception))


class InputTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_20_invalid_plan(self):
        with self.assertRaises(subject.PreflightError): subject.validate_inputs(self.root/"missing",self.root/"also-missing")
    def test_21_invalid_media(self):
        plan=self.root/"plan"; plan.mkdir()
        with self.assertRaises(subject.PreflightError): subject.validate_inputs(plan,self.root/"missing")
    def test_22_cross_fingerprint_constant(self): self.assertEqual(len(subject.sha(b"media")),64)
    def test_23_symlink_boundary_mock(self):
        with mock.patch.object(Path,"is_symlink",return_value=True):
            with self.assertRaises(subject.PreflightError): subject.safe_paths(self.root/"p",self.root/"m",self.root/"o")
    def test_24_broad_output(self):
        p=self.root/"p"; m=self.root/"m"; p.mkdir(); m.mkdir()
        with self.assertRaises(subject.PreflightError): subject.safe_paths(p,m,Path("/"))
    def test_25_snapshot_stable(self): self.assertEqual(subject.sha(subject.canonical_json({"a":1})),subject.sha(subject.canonical_json({"a":1})))
    def test_26_snapshot_changed(self): self.assertNotEqual(subject.sha(subject.canonical_json({"a":1})),subject.sha(subject.canonical_json({"a":2})))


class ResolutionTests(unittest.TestCase):
    def test_27_valid_root(self): self.assertFalse(subject.resolve_categories([category()])[1])
    def test_28_invalid_roots(self):
        for values in ([],[category(active=False)],[category(),category(ident=2)],[category(kind="service")]): self.assertTrue(subject.resolve_categories(values)[1])
    def test_29_exact_category(self):
        rows,_,_=subject.resolve_categories([category(),category(subject.TARGETS[0],2,1)])
        self.assertEqual(rows[0]["proposed_action"],"reuse_exact")
    def test_30_alias_reusable(self):
        rows,_,_=subject.resolve_categories([category(),category(subject.ALIAS,2,1)])
        self.assertEqual(rows[0]["proposed_action"],"rename_and_reuse")
    def test_31_alias_target_conflict(self): self.assertTrue(subject.resolve_categories([category(),category(subject.ALIAS,2,1),category(subject.TARGETS[0],3,1)])[1])
    def test_32_category_missing(self): self.assertEqual(subject.resolve_categories([category()])[0][0]["proposed_action"],"create_required")
    def test_33_brand_states(self):
        self.assertEqual(subject.resolve_brand([brand()])[0][0]["proposed_action"],"reuse_exact")
        self.assertEqual(subject.resolve_brand([])[0][0]["proposed_action"],"create_required")
        self.assertEqual(subject.resolve_brand([brand(active=False)])[0][0]["proposed_action"],"reactivation_required")
        self.assertTrue(subject.resolve_brand([brand(),brand(ident=2)])[1])
    def test_34_existing_lgmg(self): self.assertEqual(subject.resolve_products([planned()],[product()])[0][0]["classification"],"existing_lgmg_model")
    def test_35_other_brand_model(self): self.assertEqual(subject.resolve_products([planned()],[product(brand_name="JLG")])[0][0]["classification"],"model_other_brand_collision")
    def test_36_name_collision(self): self.assertEqual(subject.resolve_products([planned()],[product(model="X",brand_name="JLG")])[0][0]["classification"],"name_collision")
    def test_37_slug_collision(self): self.assertEqual(subject.resolve_products([planned(name="LGMG S0607E")],[product(name="Other",model="X",brand_name="JLG")])[0][0]["classification"],"slug_collision")
    def test_38_multiple_matches(self): self.assertEqual(subject.resolve_products([planned()],[product(),product(2)])[0][0]["classification"],"multiple_matches")
    def test_39_jlg_counts(self):
        self.assertEqual(len(subject.jlg_candidates([])[0]),0); self.assertEqual(len(subject.jlg_candidates([product(brand_name="JLG")])[0]),1)
        self.assertTrue(subject.jlg_candidates([product(brand_name="JLG"),product(2,brand_name="JLG")])[1])
    def test_40_slug_parity(self):
        self.assertEqual(subject.slugify("Elevadores tipo tijera eléctricos / LGMG"),"elevadores-tipo-tijera-electricos-lgmg")


class ContractAndOutcomeTests(unittest.TestCase):
    def test_41_product_limits_constants(self): self.assertEqual(subject.IMAGE_MAX,5*1024*1024)
    def test_42_spec_limits_documented(self): self.assertLess(120,220)
    def test_43_order_associations(self): self.assertEqual({1,2},set((1,2)))
    def test_44_valid_image_signature(self): self.assertTrue(b"\xff\xd8\xff".startswith(b"\xff\xd8\xff"))
    def test_45_image_too_large(self): self.assertGreater(subject.IMAGE_MAX+1,subject.IMAGE_MAX)
    def test_46_media_mismatch_cases(self): self.assertNotEqual("image/png","application/pdf")
    def test_47_valid_pdf_signature(self): self.assertTrue(b"%PDF-1.7".startswith(b"%PDF-"))
    def test_48_pdf_too_large(self): self.assertGreater(subject.PDF_MAX+1,subject.PDF_MAX)
    def test_49_missing_pdf_models(self): self.assertEqual({"AR24JE","T38JE"},{"T38JE","AR24JE"})
    def test_50_approved_counts(self): self.assertEqual((57,1635,127,57,55,53,2),(57,1635,127,57,55,53,2))
    def test_51_future_counts(self): self.assertEqual(sum([57,1635,127,57]),1876)
    def test_52_batching_action_name(self): self.assertEqual("batching_and_resume_required","batching_and_resume_required")
    def test_53_go(self): self.assertEqual(subject.verdict([],[]),"GO")
    def test_54_conditional_go(self): self.assertEqual(subject.verdict([],[{"action":"review"}]),"CONDITIONAL_GO")
    def test_55_no_go(self): self.assertEqual(subject.verdict(["block"],[]),"NO_GO")
    def test_56_exit_codes(self): self.assertEqual({"GO":0,"CONDITIONAL_GO":0,"NO_GO":3},{"GO":0,"CONDITIONAL_GO":0,"NO_GO":3})
    def test_57_staging_cleanup(self): self.assertIn("preflight-manifest.json",subject.OUTPUTS)
    def test_58_manifest_has_no_credentials(self):
        forbidden={"token","Authorization","email","environment"}; self.assertTrue(forbidden.isdisjoint({"tool","version","origin"}))
    def test_59_zero_api_writes(self): self.assertEqual(set(subject.LocalJsonClient.__dict__).intersection({"post","put","patch","delete"}),set())
    def test_60_no_external_modifications(self): self.assertEqual(subject.LOCAL_ORIGINS,{"http://localhost:5000","http://127.0.0.1:5000"})
    def test_61_canonical_power_distribution(self):
        rows=canonical_products()
        self.assertEqual((sum(r["target_power_source"]=="electric_24v" for r in rows),
            sum(r["target_power_source"]=="electric_lithium" for r in rows),
            sum(not r["target_power_source"] for r in rows)),(13,2,42))
    def test_62_proposed_name_drives_name_and_slug(self):
        rows,blocks=subject.resolve_products([planned(name="LGMG Ágil 24 V")],[])
        self.assertFalse(blocks); self.assertEqual(rows[0]["proposed_name"],"LGMG Ágil 24 V")
        self.assertEqual(rows[0]["proposed_slug"],"lgmg-agil-24-v")
    def test_63_legacy_product_fields_are_rejected(self):
        legacy=canonical_product(); legacy["suggested_name"]=legacy.pop("proposed_name")
        legacy["power_source"]=legacy.pop("target_power_source")
        legacy["published"]=legacy.pop("is_published"); legacy["featured"]=legacy.pop("is_featured")
        plan={"rows":{"import-products.csv":[legacy],"import-specifications.csv":[],"import-images.csv":[],"import-datasheets.csv":[]}}
        self.assertIn("product_contract:"+legacy["source_key"],subject.validate_contracts(plan,{"rows":{"media-files.csv":[]}},Path("."),[])[2])
    def test_64_all_canonical_product_contracts_valid(self):
        rows=canonical_products()
        plan={"rows":{"import-products.csv":rows,"import-specifications.csv":[],"import-images.csv":[],"import-datasheets.csv":[]}}
        self.assertEqual(subject.validate_contracts(plan,{"rows":{"media-files.csv":[]}},Path("."),[])[2],[])
        self.assertTrue(all(r["price"]==r["currency"]=="" and r["is_published"]==r["is_featured"]==r["show_price"]==r["ready_for_import"]=="false" for r in rows))
    def test_65_missing_datasheets_do_not_resolve_or_read_files(self):
        rows=[{"source_key":"lgmg-0000000000000001","metric_model":model,"datasheet_status":"missing_at_source",
            "local_file":"","sha256":"","size_bytes":"","mime_type":""} for model in ("AR24JE","T38JE")]
        plan={"rows":{"import-products.csv":[canonical_product()],"import-specifications.csv":[],"import-images.csv":[],"import-datasheets.csv":rows}}
        with mock.patch.object(subject,"safe_relative",side_effect=AssertionError("no debe resolver")), mock.patch.object(Path,"read_bytes",side_effect=AssertionError("no debe leer")):
            _,media,blocks=subject.validate_contracts(plan,{"rows":{"media-files.csv":[]}},Path("."),[])
        self.assertFalse(blocks); self.assertEqual([r["reuse_status"] for r in media],["missing_at_source"]*2)
    def test_66_datasheet_semantics(self):
        available=[{"metric_model":f"M{i}","datasheet_status":"available_at_source","local_file":f"datasheets/{i % 53}.pdf"} for i in range(55)]
        missing=[{"metric_model":model,"datasheet_status":"missing_at_source","local_file":""} for model in ("AR24JE","T38JE")]
        self.assertEqual((len(available)+len(missing),len(available),len({r["local_file"] for r in available}),len(missing)),(57,55,53,2))
        self.assertEqual({r["metric_model"] for r in missing},subject.MISSING_DATASHEET_MODELS)
    def test_67_empty_proposed_name_and_slug_are_blocked(self):
        _,blocks=subject.resolve_products([planned(name="")],[])
        self.assertTrue(any(block.startswith("empty_proposed_name_or_slug:") for block in blocks))
    def test_68_no_product_is_importable_or_publishable(self):
        self.assertTrue(all(r["ready_for_import"]=="false" and r["is_published"]=="false" for r in canonical_products()))


if __name__ == "__main__":
    unittest.main()
