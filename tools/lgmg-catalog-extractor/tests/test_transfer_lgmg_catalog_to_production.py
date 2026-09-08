import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
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

def png_image(width,height):
    return b"\x89PNG\r\n\x1a\n"+b"\0"*8+width.to_bytes(4,"big")+height.to_bytes(4,"big")

def jpeg_image(width,height):
    return b"\xff\xd8\xff\xc0\x00\x08\x08"+height.to_bytes(2,"big")+width.to_bytes(2,"big")+b"\x01\xff\xd9"

class Contracts(unittest.TestCase):
    def test_identity(self): self.assertEqual((t.TOOL_NAME,t.TOOL_VERSION,t.SCHEMA_VERSION,t.PROFILE),("transfer_lgmg_catalog_to_production","1.0.3","1.0","lgmg_local_catalog_57"))
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
    def test_prefixed_image_model_parser_and_canonicalization(self):
        cases=(("Maquinas LGMG/LGMG-A09JE.jpg","A09JE","A09JE"),
               ("Maquinas LGMG/LGMG-S0607-II.jpg","S0607-II","S0607"),
               ("Maquinas LGMG/LGMG-M0810JE.png","M0810JE","M0810JE"))
        for name,physical,canonical in cases:
            with self.subTest(name=name):
                self.assertTrue(Path(name).stem.startswith("LGMG-"))
                self.assertEqual(t.parse_image_model(name),physical)
                with mock.patch.object(t,"canonical_model",wraps=t.canonical_model) as resolve:
                    self.assertEqual(resolve(t.parse_image_model(name)),canonical)
                    resolve.assert_called_once_with(physical)
    def test_invalid_image_model_contract_is_rejected(self):
        invalid=("Maquinas LGMG/A09JE.jpg","Maquinas LGMG/lgmg-A09JE.jpg",
                 "Maquinas LGMG/LGMG-.jpg","Maquinas LGMG/LGMG-LGMG-A09JE.jpg",
                 "Maquinas LGMG/Principal-LGMG-A09JE.jpg","Maquinas LGMG/LGMG-X.jpg",
                 "Maquinas LGMG/LGMG-A09JE-extra.jpg","Maquinas LGMG/LGMG-A09JE.webp",
                 "Other/LGMG-A09JE.jpg","Maquinas LGMG/nested/LGMG-A09JE.jpg")
        for name in invalid:
            with self.subTest(name=name),self.assertRaises(t.ConflictError):
                t.canonical_model(t.parse_image_model(name))
    def test_all_prefixed_physical_image_names_resolve_to_exact_cohort(self):
        inverse={canonical:physical for physical,canonical in t.ALIASES.items()}
        names=[f"Maquinas LGMG/LGMG-{inverse.get(model,model)}.{('png' if model=='M0810JE' else 'jpg')}" for model in t.MODELS]
        resolved=[t.canonical_model(t.parse_image_model(name)) for name in names]
        self.assertEqual(len(names),57)
        self.assertEqual(set(resolved),set(t.MODELS))
        self.assertEqual(len(set(resolved)),57)
        self.assertIn("A09JE-2",resolved)
        self.assertEqual(len(t.ALIASES),12)
    def test_synthetic_package_audit_accepts_all_57_prefixed_images(self):
        inverse={canonical:physical for physical,canonical in t.ALIASES.items()}
        capture_bytes=json.dumps(capture(),ensure_ascii=False,separators=(",",":")).encode()
        with tempfile.TemporaryDirectory() as td:
            package=Path(td)/t.PACKAGE_NAME
            with zipfile.ZipFile(package,"w") as archive:
                def write_regular(name,data):
                    info=zipfile.ZipInfo(name); info.external_attr=(stat.S_IFREG|0o644)<<16
                    archive.writestr(info,data)
                write_regular(t.JSON_NAME,capture_bytes)
                for model in t.MODELS:
                    physical=inverse.get(model,model)
                    ext="png" if model=="M0810JE" else "jpg"
                    image=png_image(600,451) if model=="M0810JE" else jpeg_image(600,451)
                    write_regular(f"Maquinas LGMG/LGMG-{physical}.{ext}",image)
                    if model not in t.WITHOUT_SHEET:
                        write_regular(f"Fichas tecnicas LGMG/Ficha-tecnica-LGMG-{physical}.pdf",b"pdf")
            raw=package.read_bytes(); entries=[]
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for info in archive.infolist():
                    data=archive.read(info)
                    entries.append((t.normalize_entry(info.filename),len(data),t.sha256(data)))
            expected={"name":t.PACKAGE_NAME,"size":len(raw),"sha":t.sha256(raw),
                      "entries":112,"json_size":len(capture_bytes),"json_sha":t.sha256(capture_bytes),
                      "manifest":t.manifest_fingerprint(entries)}
            with mock.patch.object(t,"validate_pdf"):
                audited=t.audit_package(package,expected)
            self.assertEqual(set(audited["image_files"]),set(t.MODELS))
            self.assertEqual(len(audited["image_files"]),57)
            self.assertEqual(len(audited["sheet_files"]),54)
            self.assertEqual(len(t.build_plan(audited["source"],audited)),234)
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
    def test_simulated_dry_run_source_has_zero_mutating_requests(self):
        source=capture()
        self.assertEqual(source["counts"]["mutating_requests"],0)
        self.assertEqual({request["method"] for request in source["requests"]},{"GET"})
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
    def test_png_image_size_is_width_height(self):
        self.assertEqual(t._image_size(png_image(600,451)),("png",(600,451)))
    def test_allowed_horizontal_image_dimensions(self):
        for width,height in ((600,450),(600,451),(800,601)):
            with self.subTest(size=(width,height)):
                t.validate_image("LGMG-A09JE.jpg",jpeg_image(width,height),"A09JE")
        t.validate_image("LGMG-M0810JE.png",png_image(600,451),"M0810JE")
    def test_transposed_and_noncontract_image_dimensions_are_rejected(self):
        dimensions=((450,600),(451,600),(601,800),(599,451),(600,449),(700,500),(801,601),(800,602))
        for width,height in dimensions:
            with self.subTest(size=(width,height)),self.assertRaisesRegex(
                    t.ConflictError,rf"^image_dimensions:LGMG-A09JE\.jpg:{width}x{height}$"):
                t.validate_image("/private/catalog/LGMG-A09JE.jpg",jpeg_image(width,height),"A09JE")
    def test_image_format_model_extension_contracts(self):
        png=png_image(600,451); jpeg=jpeg_image(600,451)
        cases=(("LGMG-A09JE.png",png,"A09JE"),("LGMG-M0810JE.png",jpeg,"M0810JE"),
               ("LGMG-M0810JE.jpg",png,"M0810JE"),("LGMG-A09JE.jpg",b"not-image","A09JE"))
        for name,data,model in cases:
            with self.subTest(name=name),self.assertRaises(t.ConflictError):
                t.validate_image(name,data,model)
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
