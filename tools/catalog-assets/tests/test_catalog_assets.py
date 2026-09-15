from __future__ import annotations

import csv, hashlib, json, os, sys, tempfile, unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]))
from catalog_assets.cli import Response, initial_files, main
from catalog_assets.discovery import association_evidence
from catalog_assets.downloader import download_one
from catalog_assets.inventory import scan
from catalog_assets.naming import asset_basename
from catalog_assets.paths import DIRECTORIES, FILES, initialize, safe_path
from catalog_assets.sources import read_sources
from catalog_assets.validation import detect_binary, validate_public_url

JPEG=b"\xff\xd8\xffpayload\xff\xd9"; PNG=b"\x89PNG\r\n\x1a\ncontent-IEND\xaeB`\x82"
WEBP=b"RIFF\x08\x00\x00\x00WEBPdata"; PDF=b"%PDF-1.7\nobject\n%%EOF\n"

class FakeTransport:
    def __init__(self,responses): self.responses=list(responses); self.calls=[]
    @staticmethod
    def resolve(host,port,type=None): return [(2,1,6,"",("93.184.216.34",port))]
    def get(self,url,headers,timeout,max_bytes): self.calls.append((url,headers)); return self.responses.pop(0)

def response(body,status=200,mime="application/octet-stream",url="https://public.example/item"):
    return Response(status,body,{"content-type":mime},url)

class CatalogAssetsTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)/"Maquinas"; initialize(self.root,initial_files())
    def tearDown(self): self.temp.cleanup()

    def test_exact_structure_and_no_gam(self):
        dirs={p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_dir()}
        self.assertEqual(dirs,set(DIRECTORIES)|{"LGMG","EP","JLG","_pendientes","_control"})
        self.assertFalse(any("GAM" in p.parts for p in self.root.rglob("*")))
        self.assertTrue(all((self.root/f).is_file() for f in FILES))

    def test_source_contract_and_gam_policy(self):
        source=self.root/"_control/fuentes.csv"
        source.write_text(",".join(("target_brand","model","source_name","source_role","page_url","asset_type","asset_url","priority","expected_language","enabled","notes"))+"\nEP,EFL181,GAM,fallback,,image,https://public.example/e.jpg,1,es,true,ok\n",encoding="utf-8")
        self.assertEqual(read_sources(source)[0].target_brand,"EP")
        for bad in ("LGMG,X,GAM,fallback", "JLG,X,GAM,fallback", "EP,X,GAM,primary"):
            source.write_text(",".join(("target_brand","model","source_name","source_role","page_url","asset_type","asset_url","priority","expected_language","enabled","notes"))+f"\n{bad},,image,https://public.example/x.jpg,0,es,true,x\n",encoding="utf-8")
            with self.subTest(bad=bad), self.assertRaises(ValueError): read_sources(source)

    def test_names_and_stable_suffixes_no_overwrite(self):
        self.assertEqual(asset_basename("LGMG","A09JE","image",".jpg"),"LGMG-A09JE.jpg")
        self.assertEqual(asset_basename("EP","EFL 181","technical_sheet",".pdf",2),"Ficha-tecnica-EP-EFL 181-2.pdf")
        self.assertEqual(asset_basename("JLG","1930ES","image",".jpg",2),"JLG-1930ES-2.jpg")
        self.assertEqual(asset_basename("JLG","1930ES","technical_sheet",".pdf"),"Ficha-tecnica-JLG-1930ES.pdf")
        candidate={"url":"https://public.example/x","target_brand":"EP","model":"EFL181"}
        paths=[]
        for body in (JPEG,JPEG+b"x\xff\xd9",JPEG+b"y\xff\xd9"):
            result=download_one(self.root,candidate,FakeTransport([response(body,mime="image/jpeg")]))
            paths.append(result["path"])
        self.assertEqual(paths,["EP/Imagenes modelos EP/EP-EFL181.jpg","EP/Imagenes modelos EP/EP-EFL181-2.jpg","EP/Imagenes modelos EP/EP-EFL181-3.jpg"])

    def test_signatures_html_and_extension_from_bytes(self):
        for body,extension in ((JPEG,".jpg"),(PNG,".png"),(WEBP,".webp"),(PDF,".pdf")):
            with self.subTest(extension=extension): self.assertEqual(detect_binary(body).extension,extension)
        with self.assertRaises(ValueError): detect_binary(b"<html>not an image</html>")
        result=download_one(self.root,{"url":"https://public.example/wrong.pdf","target_brand":"LGMG","model":"A09JE"},FakeTransport([response(PNG,mime="image/png")]))
        self.assertTrue(result["path"].endswith(".png"))

    def test_dedupe_and_idempotence(self):
        candidate={"url":"https://public.example/a.jpg","target_brand":"EP","model":"A"}; transport=FakeTransport([response(JPEG,mime="image/jpeg")])
        first=download_one(self.root,candidate,transport); second=download_one(self.root,candidate,FakeTransport([response(JPEG,mime="image/jpeg")]))
        self.assertEqual(first["state"],"VALID"); self.assertEqual(second["state"],"DUPLICATE")
        self.assertEqual(len(list((self.root/"EP/Imagenes modelos EP").iterdir())),1)

    def test_models_similar_and_ambiguous(self):
        self.assertEqual(association_evidence("photo-A09JE.jpg","A09JE",["A09JE","A09JE-2"]),(True,""))
        self.assertEqual(association_evidence("A09JE and A09JE-2","A09JE",["A09JE","A09JE-2"]),(False,"MODEL_AMBIGUOUS"))
        self.assertEqual(association_evidence("photo-A09J.jpg","A09JE",["A09JE","A09J"]),(False,"MODEL_UNKNOWN"))

    def test_inventory_preserves_and_is_deterministic_excel_csv(self):
        existing=self.root/"LGMG/Imagenes modelos LGMG/original extraño.jpeg"; existing.write_bytes(JPEG); before=existing.read_bytes()
        rows1,pending1=scan(self.root); bytes1=(self.root/"inventario.csv").read_bytes(); scan(self.root); bytes2=(self.root/"inventario.csv").read_bytes()
        self.assertEqual(before,existing.read_bytes()); self.assertEqual(bytes1,bytes2); self.assertTrue(bytes1.startswith(b"\xef\xbb\xbf"))
        with (self.root/"inventario.csv").open(encoding="utf-8-sig") as handle:
            self.assertEqual(list(csv.DictReader(handle))[0]["estado"],"MODEL_UNKNOWN")
        self.assertEqual(pending1[0]["motivo"],"MODEL_UNKNOWN")

    def test_path_traversal_and_symlink_escape(self):
        with self.assertRaises(ValueError): safe_path(self.root,"../escape")
        outside=Path(self.temp.name)/"outside"; outside.mkdir(); link=self.root/"link"
        try: link.symlink_to(outside,target_is_directory=True)
        except OSError: self.skipTest("symlinks no disponibles")
        with self.assertRaises(ValueError): safe_path(self.root,"link/file")

    def test_network_rejections_and_flag(self):
        resolver=lambda host,port,type=None:[(2,1,6,"",("10.0.0.1",port))]
        for url in ("file:///tmp/a","http://localhost/a","http://127.0.0.1/a","http://[::1]/a","https://private.example/a"):
            with self.subTest(url=url), self.assertRaises(ValueError): validate_public_url(url,resolver)
        with self.assertRaises(ValueError): main(["--root",str(self.root),"discover"],FakeTransport([]))

    def test_resume_simulated(self):
        candidate={"url":"https://public.example/file.pdf","target_brand":"EP","model":"EFL"}
        partial=self.root/"_control/parciales"/(hashlib.sha256(candidate["url"].encode()).hexdigest()+".part"); partial.write_bytes(PDF[:8])
        transport=FakeTransport([response(PDF[8:],206,"application/pdf")]); result=download_one(self.root,candidate,transport)
        self.assertEqual(transport.calls[0][1],{"Range":"bytes=8-"}); self.assertEqual(result["state"],"VALID")

    def test_pending_download_stays_pending(self):
        result=download_one(self.root,{"url":"https://public.example/a.jpg","target_brand":"EP","model":""},FakeTransport([response(JPEG,mime="image/jpeg")]),pending=True)
        self.assertTrue(result["path"].startswith("_pendientes/imagenes/"))

    def test_only_root_written_and_no_pipeline_import(self):
        self.assertEqual(main(["--root",str(self.root),"init"]),0)
        package=Path(__file__).parents[1]/"catalog_assets"
        self.assertFalse(any("catalog-pipeline" in p.read_text(encoding="utf-8") for p in package.glob("*.py")))

    def _sources(self, rows):
        path=self.root/"_control/fuentes.csv"
        with path.open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.writer(handle); writer.writerow(("target_brand","model","source_name","source_role","page_url","asset_type","asset_url","priority","expected_language","enabled","notes"))
            for brand,model in rows: writer.writerow((brand,model,brand,"primary","","auto","",0,"es","false","modelo conocido"))

    def test_jlg_legacy_two_pass_and_uncertain_names(self):
        self._sources([("JLG","1930ES")])
        legacy=self.root/"JLG/Maquinas JLG"; legacy.mkdir()
        assets={"1930es.jpg":JPEG,"plataforma-tijera-electrica-1930es.jpg":JPEG+b"2\xff\xd9",
                "ChatGPT Image 5 ago 2026, 20_21_25.png":PNG,
                "Ficha-tecnica-JLG-1930-Comaq-Rental.pdf":PDF}
        for name,data in assets.items(): (legacy/name).write_bytes(data)
        before={p.name:p.read_bytes() for p in legacy.iterdir()}; rows,pending=scan(self.root)
        indexed={r["archivo"]:r for r in rows}
        self.assertEqual(indexed["1930es.jpg"]["modelo"],"1930ES")
        self.assertEqual(indexed["plataforma-tijera-electrica-1930es.jpg"]["modelo"],"1930ES")
        self.assertEqual(indexed["ChatGPT Image 5 ago 2026, 20_21_25.png"]["estado_clasificacion"],"MODEL_UNKNOWN")
        self.assertEqual(indexed["Ficha-tecnica-JLG-1930-Comaq-Rental.pdf"]["estado_clasificacion"],"MODEL_UNKNOWN")
        self.assertTrue(all(r["ubicacion"]=="legacy" for r in rows)); self.assertEqual(before,{p.name:p.read_bytes() for p in legacy.iterdir()})

    def test_lgmg_legacy_accents_and_complete_dash_two_models(self):
        self._sources([("LGMG","SR0818E-2"),("LGMG","SR1218E-2")])
        for folder,model in (("Fichas tecnicas LGMG","SR0818E-2"),("Fichas técnicas LGMG","SR1218E-2")):
            path=self.root/"LGMG"/folder; path.mkdir(exist_ok=True); (path/f"Ficha-técnica-LGMG-{model}.pdf").write_bytes(PDF+model.encode())
        rows,_=scan(self.root); self.assertEqual({r["modelo"] for r in rows},{"SR0818E-2","SR1218E-2"})
        self.assertTrue(all(r["ubicacion"]=="legacy" for r in rows))

    def test_dash_two_ambiguity(self):
        self._sources([("LGMG","A09JE"),("LGMG","A09JE-2")])
        (self.root/"LGMG/Imagenes modelos LGMG/LGMG-A09JE-2.jpg").write_bytes(JPEG)
        rows,_=scan(self.root); self.assertEqual(rows[0]["estado_clasificacion"],"MODEL_AMBIGUOUS")

    def test_manual_model_aliases_and_conflicts(self):
        aliases=self.root/"_control/modelos.csv"
        aliases.write_text("brand,canonical_model,alias,enabled,notes\nJLG,1930ES,1930 E,true,confirmado\n",encoding="utf-8")
        legacy=self.root/"JLG/Maquinas JLG"; legacy.mkdir(); (legacy/"equipo-1930 E.jpg").write_bytes(JPEG)
        rows,_=scan(self.root); self.assertEqual((rows[0]["modelo"],rows[0]["metodo_asociacion"]),("1930ES","manual_alias"))
        aliases.write_text("brand,canonical_model,alias,enabled,notes\nJLG,1930ES,x,true,a\nJLG,other,X,true,b\n",encoding="utf-8")
        with self.assertRaises(ValueError): scan(self.root)

    def test_verify_integrity_vs_strict_and_invalid(self):
        legacy=self.root/"JLG/Maquinas JLG"; legacy.mkdir(); asset=legacy/"unknown.jpg"; asset.write_bytes(JPEG)
        scan(self.root); self.assertEqual(main(["--root",str(self.root),"verify"]),0)
        self.assertEqual(main(["--root",str(self.root),"verify","--strict"]),1)
        asset.write_bytes(b"not an image")
        self.assertEqual(main(["--root",str(self.root),"verify"]),1)
        self.assertEqual(main(["--root",str(self.root),"verify","--strict"]),1)

    def test_duplicate_paths_and_detailed_missing_status(self):
        self._sources([("JLG","1930ES"),("LGMG","A09JE")])
        (self.root/"JLG/Imagenes modelos JLG/JLG-1930ES.jpg").write_bytes(JPEG)
        (self.root/"JLG/fichas-tecnicas JLG/Ficha-tecnica-JLG-1930ES.pdf").write_bytes(PDF)
        (self.root/"LGMG/Imagenes modelos LGMG/LGMG-A09JE.jpg").write_bytes(JPEG+b"a\xff\xd9")
        (self.root/"LGMG/Imagenes modelos LGMG/LGMG-A09JE-3.jpg").write_bytes(JPEG+b"a\xff\xd9")
        scan(self.root)
        from contextlib import redirect_stdout
        import io
        output=io.StringIO()
        with redirect_stdout(output): self.assertEqual(main(["--root",str(self.root),"status"]),0)
        status=json.loads(output.getvalue()); self.assertEqual(status["modelos_sin_pdf"],[{"marca":"LGMG","modelo":"A09JE"}])
        self.assertEqual(status["archivos_duplicados"],1); self.assertIn("ruta_principal",status["duplicados"][0]); self.assertIn("ruta_duplicada",status["duplicados"][0])

if __name__ == "__main__": unittest.main()
