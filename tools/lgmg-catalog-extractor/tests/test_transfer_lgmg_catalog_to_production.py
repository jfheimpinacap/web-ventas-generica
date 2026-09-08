import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("transfer",HERE/"transfer_lgmg_catalog_to_production.py")
t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)

def capture():
    cats=[{"id":i+1,"name":n,"slug":s} for i,(n,s) in enumerate(t.CATEGORIES)]
    products=[]; images=[]
    for i,m in enumerate(t.MODELS):
        p={"id":100+i,"name":"LGMG "+m,"slug":"lgmg-"+m.lower(),"model":m,"category":cats[i%7]["id"],"brand":9,"product_type":"machinery","condition":"new","stock_status":"on_request","price":None,"price_visible":False,"is_featured":False,"is_published":True}
        image={"id":200+i,"product":p["id"],"image":"/local/"+m+".jpg","is_main":True,"order":0}; p["main_image"]=image; p["images"]=[image]; p["specs"]=[]; products.append(p); images.append(image)
    specs=[]
    for model in ("SR0818E-2","SR1018E-2"):
        pid=next(p["id"] for p in products if p["model"]==model)
        nested=[{"id":500+len(specs)+i,"product":pid,"name":"n"+str(i),"value":str(i),"unit":"mm","order":i} for i in range(29)]
        next(p for p in products if p["id"]==pid)["specs"]=nested; specs += nested
    return {"tool":"JEM-LGMG-transferencia-local","version":"1.0","captured_at":"2026-09-08T03:01:43.619Z","source":"http://localhost:5000","intended_destination":t.API_BASE,
      "production_policy":{"force_is_published_false":True,"force_is_featured_false":True,"force_price_visible_false":True},
      "counts":{"products":57,"images":57,"products_with_sheet":54,"products_without_sheet":3,"categories":7,"brands":1,"specifications":58,"published_local":57,"visible_prices":0,"get_requests":61,"mutating_requests":0},
      "expected_without_sheet":list(t.WITHOUT_SHEET),"requests":[{"method":"GET","status":200} for _ in range(61)],"categories":cats,"brands":[{"id":9,"name":"LGMG","slug":"lgmg"}],"products":products,"technical_sheets":[{"id":i} for i in range(54)]}

class Contracts(unittest.TestCase):
    def test_identity(self): self.assertEqual((t.TOOL_NAME,t.TOOL_VERSION,t.SCHEMA_VERSION,t.PROFILE),("transfer_lgmg_catalog_to_production","1.0.1","1.0","lgmg_local_catalog_57"))
    def test_capture_has_exact_canonical_top_level_and_derives_nested_rows(self):
        d=capture(); self.assertNotIn("images",d); self.assertNotIn("specifications",d)
        source=t.validate_capture(d)
        self.assertEqual((len(source["images"]),len(source["specifications"])),(57,58))
    def test_top_level_derived_collection_is_rejected(self):
        for name in ("images","specifications","specs","main_images","schema_version"):
            d=capture(); d[name]=[]
            with self.subTest(name=name),self.assertRaisesRegex(t.ConflictError,"top_level"):
                t.validate_capture(d)
    def test_capture_and_plan_234(self):
        source=t.validate_capture(capture()); plan=t.build_plan(source)
        self.assertEqual([sum(x["type"]==k for x in plan) for k in ("category","brand","datasheet","product","image","specification")],[7,1,54,57,57,58]); self.assertEqual(len(set(x["operation_key"] for x in plan)),234)
    def test_plan_stable(self): self.assertEqual(t.build_plan(t.validate_capture(capture())),t.build_plan(t.validate_capture(capture())))
    def test_forced_product_policy_and_local_fields_excluded(self):
        p=t.build_plan(t.validate_capture(capture()))[62]["payload"]
        self.assertEqual((p["price"],p["price_visible"],p["is_featured"],p["is_published"]),(None,False,False,False)); self.assertFalse({"id","created_at","updated_at","main_image"}&p.keys())
    def test_aliases_exact(self): self.assertEqual({t.canonical_model(k):k for k in t.ALIASES}, {v:k for k,v in t.ALIASES.items()})
    def test_alias_unknown_rejected(self):
        with self.assertRaises(t.ConflictError): t.canonical_model("S0607-III")
    def test_windows_separator(self): self.assertEqual(t.normalize_entry(r"a\b.pdf"),"a/b.pdf")
    def test_traversal_absolute_drive_rejected(self):
        for value in ("../x","/x",r"C:\x","a/../x"):
            with self.subTest(value=value),self.assertRaises(t.ConflictError): t.normalize_entry(value)
    def test_manifest_fingerprint_has_sorted_final_newline(self): self.assertEqual(t.manifest_fingerprint([("b",2,"y"),("a",1,"x")]),t.sha256(b"a|1|x\nb|2|y\n"))
    def test_header_divergence(self):
        d=capture(); d["tool"]="other"
        with self.assertRaisesRegex(t.ConflictError,"header"): t.validate_capture(d)
    def test_mutating_request_rejected(self):
        d=capture(); d["requests"][0]["method"]="POST"
        with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_secret_rejected(self):
        d=capture(); d["requests"][0]["note"]="Authorization: Bearer abc"
        with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_missing_duplicate_extra_models(self):
        for mutate in (lambda d:d["products"].pop(),lambda d:d["products"].__setitem__(1,{**d["products"][1],"model":d["products"][0]["model"]}),lambda d:d["products"].__setitem__(1,{**d["products"][1],"model":"X"})):
            d=capture(); mutate(d)
            with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_category_brand_relation(self):
        for field,value in (("category",999),("brand",999)):
            d=capture(); d["products"][0][field]=value
            with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_multiple_or_nonmain_image(self):
        d=capture(); d["products"][0]["images"].append(dict(d["products"][0]["images"][0])); d["counts"]["images"]=58
        with self.assertRaises(t.ConflictError): t.validate_capture(d)
        d=capture(); d["products"][0]["images"][0]["is_main"]=False; d["products"][0]["main_image"]=d["products"][0]["images"][0]
        with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_order_bool_noninteger_nonzero(self):
        for value in (True,"0",1):
            d=capture(); d["products"][0]["images"][0]["order"]=value; d["products"][0]["main_image"]=d["products"][0]["images"][0]
            with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_specification_counts(self):
        d=capture(); owner=next(p for p in d["products"] if p["model"]=="SR0818E-2"); spec=owner["specs"].pop(); spec["product"]=d["products"][0]["id"]; d["products"][0]["specs"].append(spec)
        with self.assertRaises(t.ConflictError): t.validate_capture(d)
    def test_main_image_is_not_a_second_derived_image(self):
        source=t.validate_capture(capture())
        self.assertEqual(len(source["images"]),57)
    def test_nested_collections_are_required_and_relations_are_local_to_product(self):
        for field in ("images","specs"):
            d=capture(); del d["products"][0][field]
            with self.subTest(field=field),self.assertRaises(t.ConflictError): t.validate_capture(d)
        d=capture(); d["products"][0]["images"][0]["product"]=d["products"][1]["id"]
        with self.assertRaisesRegex(t.ConflictError,"image_relation"): t.validate_capture(d)
    def test_image_signatures_and_dimensions(self):
        png=b"\x89PNG\r\n\x1a\n"+b"\0"*8+(450).to_bytes(4,"big")+(600).to_bytes(4,"big")
        t.validate_image("M0810JE.png",png,"M0810JE")
        with self.assertRaises(t.ConflictError): t.validate_image("M0810JE.jpg",png,"M0810JE")
    def test_pdf_invalid_empty_encrypted(self):
        for raw in (b"",b"bad",b"%PDF /Encrypt %%EOF"):
            with self.assertRaises(t.ConflictError): t.validate_pdf("x.pdf",raw,"A09JE")
    def test_scanned_ss0607e_pdf(self): t.validate_pdf("Ficha-tecnica-LGMG-SS0607E.pdf",b"%PDF-1.4\nno text\n%%EOF","SS0607E")
    def test_tilde_third_rejected(self):
        with self.assertRaises(t.ConflictError): t.validate_pdf("Ficha-técnica-LGMG-X.pdf",b"%PDF\n%%EOF","X")
    def test_api_origin_closed(self):
        self.assertEqual(t.validate_api_base(t.API_BASE),t.API_BASE)
        for url in ("http://api.jem-nexus.cl","https://localhost","https://127.0.0.1","https://user:x@api.jem-nexus.cl","https://api.jem-nexus.cl/?x=1","https://example.com"):
            with self.subTest(url=url),self.assertRaises(t.ConflictError): t.validate_api_base(url)
    def test_cli_no_rollback_and_confirmation(self):
        opts={a.dest for a in t.parser()._actions}; self.assertNotIn("rollback",opts); self.assertIn("confirm_apply",opts)
    def test_atomic_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"cp.json"; t.atomic_write(p,{"token":"x","state":"ok"}); self.assertEqual(json.loads(p.read_text()),{"state":"ok"}); self.assertEqual(list(Path(td).iterdir()),[p])
    def test_prefix_valid_invalid(self):
        plan=[t.operation("brand","lgmg",{})]; done=[{"operation_key":plan[0]["operation_key"],"index":0,"type":"brand","production_id":2}]; t.validate_prefix(plan,done)
        done[0]["index"]=1
        with self.assertRaises(t.ConflictError): t.validate_prefix(plan,done)
    def test_reconciliation(self):
        self.assertIsNone(t.reconcile([])); self.assertEqual(t.reconcile([{"id":3}])["id"],3)
        with self.assertRaises(t.ConflictError): t.reconcile([{"id":1},{"id":2}])
    def test_sanitize_jwt_everywhere(self):
        value=t.sanitize({"Authorization":"x","nested":["Bearer abc","eyJabc.def.ghi"],"ok":1}); raw=json.dumps(value)
        self.assertNotIn("Bearer",raw); self.assertNotIn("eyJ",raw); self.assertNotIn("Authorization",raw)
    def test_preflight_conflict_and_semantic_root(self):
        state={"categories":[{"id":1,"name":"Maquinarias","slug":"maquinarias","product_type":"machinery","parent":None,"is_active":True}],"brands":[],"products":[],"images":[],"specifications":[],"sheets":[]}; self.assertEqual(t.preflight(state)["root_id"],1)
        state["brands"]=[{"slug":"lgmg"}]
        with self.assertRaises(t.ConflictError): t.preflight(state)
    def test_complete_disallows_apply_resume(self):
        self.assertNotIn("production_transfer_complete",{"production_transfer_partial","production_transfer_in_progress"})

if __name__=="__main__": unittest.main()
