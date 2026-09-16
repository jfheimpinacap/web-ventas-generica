from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catalog_assets.cli import initial_files, main
from catalog_assets.ep_download import RESULT_FIELDS
from catalog_assets.ep_local_import import MISSING_SHEETS, EpLocalError, load_assets, product_payload, validate_base_url
from catalog_assets.paths import initialize

JPEG = b"\xff\xd8\xffsynthetic\xff\xd9"
PDF = b"%PDF-1.4\nsynthetic\n%%EOF\n"


class FakeTransport:
    def __init__(self, brand=True):
        self.calls=[]
        self.values={
            "/api/categories?include_inactive=true":[{"id":1,"slug":"maquinaria","product_type":"machinery","is_active":True,"parent_id":None}],
            "/api/brands?include_inactive=true":([{"id":2,"name":"EP","slug":"ep"}] if brand else []),
            "/api/products?include_unpublished=true":[], "/api/product-images":[], "/api/technical-sheets/":[]}
    def request(self, method, endpoint, token, **kwargs):
        self.calls.append((method,endpoint,token,kwargs))
        return self.values[endpoint]


class EpLocalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)/"Maquinas"
        initialize(self.root,initial_files())
        models=sorted(MISSING_SHEETS | {f"MODEL{i:02d}" for i in range(30)})
        rows=[]
        for index,model in enumerate(models):
            image=self.root/"EP/Imagenes modelos EP"/f"EP-{index}.jpg"; image.parent.mkdir(parents=True,exist_ok=True); image.write_bytes(JPEG[:-2]+str(index).encode()+JPEG[-2:])
            rows.append(self.row(model,"image",image))
            if model not in MISSING_SHEETS:
                sheet=self.root/"EP/fichas-tecnicas EP"/f"EP-{index}.pdf"; sheet.parent.mkdir(parents=True,exist_ok=True); sheet.write_bytes(PDF[:-6]+str(index).encode()+PDF[-6:])
                rows.append(self.row(model,"technical_sheet",sheet))
        control=self.root/"_control/ep-download-results.csv"
        with control.open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=RESULT_FIELDS); writer.writeheader(); writer.writerows(rows)
    def tearDown(self): self.temp.cleanup()
    def row(self,model,kind,path):
        return {"source":"EP","target_brand":"EP","model":model,"asset_type":kind,"asset_url":"https://example.invalid","page_url":"https://example.invalid","path":path.relative_to(self.root).as_posix(),"bytes":str(path.stat().st_size),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"state":"DOWNLOADED","detail":""}

    def test_closed_report_yields_35_35_30_5_and_ignores_foreign_rows(self):
        accepted,omitted=load_assets(self.root)
        self.assertEqual((65,35,30), (len(accepted),sum(x["type"]=="image" for x in accepted),sum(x["type"]=="technical_sheet" for x in accepted)))
        self.assertEqual(MISSING_SHEETS,{x["model"] for x in accepted if x["type"]=="image"}-{x["model"] for x in accepted if x["type"]=="technical_sheet"})
        self.assertEqual([],omitted)

    def test_dry_run_is_get_only_writes_plan_and_never_serializes_token(self):
        transport=FakeTransport(); token="TOP-SECRET"
        with patch.dict(os.environ,{"JEM_NEXUS_LOCAL_READ_TOKEN":token},clear=True):
            code=main(["--root",str(self.root),"import-ep-local","--dry-run","--base-url","http://127.0.0.1:8000"],transport)
        self.assertEqual(0,code); self.assertTrue(all(x[0]=="GET" for x in transport.calls)); self.assertEqual(5,len(transport.calls))
        plan=(self.root/"_control/ep-local-import/ep-local-import-plan.json").read_text()
        self.assertNotIn(token,plan); payload=json.loads(plan)
        self.assertEqual((35,35,30,5),tuple(payload["counts"][x] for x in ("models","images","technical_sheets","missing_sheets")))
        self.assertTrue(all(o["payload"]["name"]==f"EP {o['model']}" and not o["payload"]["is_published"] for o in payload["operations"]))
        self.assertFalse(any("description" in o["payload"] or "spec" in o["payload"] for o in payload["operations"]))

    def test_brand_creation_is_planned_and_missing_token_prevents_network(self):
        transport=FakeTransport(False)
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,"JEM_NEXUS_LOCAL_READ_TOKEN"):
                main(["--root",str(self.root),"import-ep-local","--dry-run","--base-url","http://localhost:80"],transport)
        self.assertEqual([],transport.calls)
        self.assertEqual("ep-model-01",product_payload("MODEL 01",1,2)["slug"])

    def test_rejects_external_missing_port_symlink_bad_hash_and_legacy_path(self):
        for url in ("https://localhost:443","http://localhost","http://10.0.0.1:80","http://u:p@localhost:80","http://localhost:80/#x"):
            with self.assertRaises(EpLocalError): validate_base_url(url)
        report=self.root/"_control/ep-download-results.csv"; text=report.read_text(encoding="utf-8-sig")
        report.write_text(text.replace("DOWNLOADED,", "DOWNLOADED,",1).replace("EP/Imagenes modelos EP/EP-0.jpg", "EP/Fichas tecnicas EP/EP-0.jpg"),encoding="utf-8-sig")
        with self.assertRaisesRegex(EpLocalError,"escenario EP inesperado"): load_assets(self.root)

    def test_wrong_fingerprint_is_blocked_without_mutation(self):
        transport=FakeTransport()
        with patch.dict(os.environ,{"JEM_NEXUS_LOCAL_READ_TOKEN":"r"},clear=True):
            main(["--root",str(self.root),"import-ep-local","--dry-run","--base-url","http://[::1]:8000"],transport)
        transport.calls.clear()
        with patch.dict(os.environ,{"JEM_NEXUS_LOCAL_MUTATION_TOKEN":"m"},clear=True):
            with self.assertRaisesRegex(ValueError,"fingerprint"):
                main(["--root",str(self.root),"import-ep-local","--apply","--base-url","http://[::1]:8000","--confirm-plan-fingerprint","bad"],transport)
        self.assertEqual([],transport.calls)


if __name__ == "__main__": unittest.main()
