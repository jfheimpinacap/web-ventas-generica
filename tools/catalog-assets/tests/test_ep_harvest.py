from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]))
from catalog_assets.cli import Response, initial_files, main
from catalog_assets.ep_harvest import EP_START, GAM_LISTINGS, _key, load_seed
from catalog_assets.paths import initialize
from catalog_assets.sources import read_sources

class MapTransport:
    def __init__(self,pages): self.pages=pages; self.calls=[]
    @staticmethod
    def resolve(host,port,type=None): return [(2,1,6,"",("93.184.216.34",port))]
    def get(self,url,headers,timeout,max_bytes):
        self.calls.append(url); value=self.pages[url]
        if isinstance(value,Response): return value
        return Response(200,value.encode(),{"content-type":"text/html; charset=utf-8"},url)

def listing(name,url): return f'<a class="product-card" data-model="{name}" href="{url}">{name}</a>'
def product(image="",pdf=""):
    return (f'<img class="product_image" src="{image}" alt="producto">' if image else '')+(f'<a href="{pdf}">Descargar Ficha técnica</a>' if pdf else '')

class EpHarvestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)/"Maquinas"; initialize(self.root,initial_files())
    def tearDown(self): self.temp.cleanup()

    def pages(self):
        fixture=Path(__file__).parents[1]/"fixtures"/"ep-harvest"
        read=lambda name:(fixture/name).read_text(encoding="utf-8")
        pages={url:read(f"gam-page-{index}.html") for index,url in enumerate(GAM_LISTINGS,1)}
        pages["https://online.gamrentals.com/robots.txt"]="User-agent: *\nAllow: /cl/"
        pages["https://ep-equipment.com/robots.txt"]="User-agent: *\nAllow: /es/productos/"
        pages[EP_START]=read("ep-catalog.html")
        pages["https://ep-equipment.com/es/productos/efl181/"]=read("ep-complete.html")
        pages["https://online.gamrentals.com/cl/producto/efl181"]=read("gam-efl181.html")
        pages["https://ep-equipment.com/es/productos/ept20-et/"]=read("ep-without-pdf.html")
        pages["https://online.gamrentals.com/cl/producto/ept20-et"]=read("gam-ept20-et.html")
        return pages

    def test_seed_has_exact_universe_and_families(self):
        rows=load_seed(); self.assertEqual(39,len(rows)); self.assertTrue(all(r["target_brand"]=="EP" for r in rows))
        self.assertEqual({r["observed_name"] for r in rows if r["disposition"]=="REVIEW"},{"SERIE X2","SERIE X3","SERIE X5","SERIE F"})
        self.assertEqual({r["gam_listing_page"] for r in rows},set(GAM_LISTINGS))
        self.assertIn("descrito",next(r["notes"] for r in rows if r["observed_name"]=="EPT20-ET"))

    def test_exact_matching_is_conservative(self):
        self.assertEqual(_key(" EPT20-ET "),_key("ept20 et")); self.assertNotEqual(_key("EPT20"),_key("EPT20-ET"))
        self.assertNotEqual(_key("EFL201"),_key("EFL203")); self.assertNotEqual(_key("EPT20-30RT"),_key("EPT20-30RTS"))

    def test_harvest_prefers_ep_and_gam_fills_only_missing_type(self):
        transport=MapTransport(self.pages())
        capture=io.StringIO(); old=sys.stdout; sys.stdout=capture
        try: self.assertEqual(0,main(["--root",str(self.root),"harvest-ep","--allow-public-network","--request-delay","0"],transport))
        finally: sys.stdout=old
        summary=json.loads(capture.getvalue()); self.assertIn("LIVE-NEW",summary["added"]); self.assertIn("EFS101",summary["removed"]); self.assertEqual(0,summary["assets_downloaded"])
        sources=read_sources(self.root/"_control/fuentes.csv"); by_model={}
        for row in sources: by_model.setdefault(row.model,[]).append(row)
        efl=by_model["EFL181"]; self.assertEqual({r.source_name for r in efl},{"EP"}); self.assertEqual({r.asset_type for r in efl},{"image","technical_sheet"})
        et=by_model["EPT20-ET"]; self.assertEqual({(r.source_name,r.asset_type) for r in et},{("EP","image"),("GAM","technical_sheet")})
        self.assertTrue(all(r.target_brand=="EP" and not r.enabled for r in sources)); self.assertFalse(any("LGMG" in str(p) or "JLG" in str(p) for p in (self.root/"_control/research").rglob("*")))
        self.assertFalse(any((self.root/"EP/Imagenes modelos EP").iterdir())); self.assertFalse(any((self.root/"EP/fichas-tecnicas EP").iterdir()))

    def test_checkpoint_resume_idempotence_and_network_guards(self):
        transport=MapTransport(self.pages()); args=["--root",str(self.root),"harvest-ep","--allow-public-network","--request-delay","0"]
        old=sys.stdout; sys.stdout=io.StringIO()
        try:
            self.assertEqual(0,main(args,transport)); snapshots={p.name:p.read_bytes() for p in (self.root/"_control/research").iterdir()}
            second=MapTransport({}); self.assertEqual(0,main(args,second)); self.assertEqual([],second.calls)
        finally: sys.stdout=old
        self.assertEqual(snapshots,{p.name:p.read_bytes() for p in (self.root/"_control/research").iterdir()})
        with self.assertRaises(ValueError): main(["--root",str(self.root),"harvest-ep"],MapTransport({}))
        bad=self.pages(); bad[GAM_LISTINGS[0]]=Response(200,b"ok",{"content-type":"application/pdf"},"https://evil.example/x")
        other=Path(self.temp.name)/"Other"; initialize(other,initial_files())
        with self.assertRaises(ValueError): main(["--root",str(other),"harvest-ep","--allow-public-network","--request-delay","0"],MapTransport(bad))

if __name__=="__main__": unittest.main()
