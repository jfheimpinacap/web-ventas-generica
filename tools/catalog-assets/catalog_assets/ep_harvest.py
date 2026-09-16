from __future__ import annotations

import csv
import json
import re
import time
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .paths import atomic_write, safe_path
from .sources import COLUMNS
from .validation import validate_public_url

EP_START = "https://ep-equipment.com/es/productos/"
GAM_LISTINGS = tuple(
    "https://online.gamrentals.com/cl/826-ep" + (f"?page={page}" if page > 1 else "")
    for page in range(1, 5)
)
FAMILIES = {"SERIE X2", "SERIE X3", "SERIE X5", "SERIE F"}
MODEL_FIELDS = ("target_brand","model","category","official_model_name","ep_listing_url","ep_product_url","gam_product_url","ep_image_candidates","ep_pdf_candidates","missing_image","missing_pdf","gam_fallback_needed","confidence","status","notes")
CANDIDATE_FIELDS = ("target_brand","model","category","asset_type","asset_role","source_name","source_role","page_url","asset_url","expected_mime","expected_extension","language","priority","model_evidence","confidence","disposition","http_status","observed_mime","validation_status","notes")

def _key(value: str) -> str:
    # Only case, whitespace/hyphen and outside punctuation are ignored.
    value=value.strip().strip(".,;:()[]{}").upper()
    return re.sub(r"[\s-]+", "", value)

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]; self.assets=[]; self._anchor=None; self._text=[]; self.title=""
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); tag=tag.lower()
        if tag=="a": self._anchor=attrs; self._text=[]
        if tag=="img":
            url=attrs.get("data-src") or attrs.get("src")
            if url and not any(x in (attrs.get("class","")+" "+url).lower() for x in ("logo","icon","banner","favicon")):
                self.assets.append(("image",url,attrs.get("alt","")))
        model=attrs.get("data-model") or attrs.get("data-product-model")
        href=attrs.get("data-product-url") or (attrs.get("href") if model else None)
        if model and href: self.items.append((model,href,attrs.get("data-category","")))
    def handle_data(self,data):
        if self._anchor is not None: self._text.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self._anchor is not None:
            text=" ".join("".join(self._text).split()); href=self._anchor.get("href","")
            classes=self._anchor.get("class","").lower()
            model=self._anchor.get("data-model") or self._anchor.get("data-product-model")
            if href and (model or "product" in classes or "producto" in classes):
                self.items.append((model or text,href,self._anchor.get("data-category","")))
            if href.lower().split("?",1)[0].endswith(".pdf") or "ficha" in text.lower():
                self.assets.append(("technical_sheet",href,text))
            self._anchor=None; self._text=[]

def _parse(body: bytes, base: str) -> PageParser:
    parser=PageParser(); parser.feed(body.decode("utf-8",errors="replace"))
    parser.items=list(dict.fromkeys((n.strip(),urljoin(base,u),c.strip()) for n,u,c in parser.items if n.strip() and u))
    parser.assets=list(dict.fromkeys((t,urljoin(base,u),e.strip()) for t,u,e in parser.assets if u))
    return parser

def _csv_bytes(fields,rows):
    import io
    stream=io.StringIO(newline=""); writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")

def _fetch(transport,url,timeout,max_bytes):
    validate_public_url(url,transport.resolve)
    response=transport.get(url,headers={"Accept":"text/html,application/xhtml+xml"},timeout=timeout,max_bytes=max_bytes)
    validate_public_url(response.final_url,transport.resolve)
    if response.status != 200: raise ValueError(f"HTTP {response.status}: {url}")
    mime=(response.headers.get("content-type") or response.headers.get("Content-Type") or "").split(";",1)[0].lower()
    if mime and mime not in {"text/html","application/xhtml+xml","text/plain","application/octet-stream"}: raise ValueError(f"MIME HTML inválido: {mime}")
    return response

def _allowed_product(url: str, source: str) -> bool:
    parsed=urlsplit(url)
    if source=="EP": return parsed.scheme=="https" and parsed.hostname in {"ep-equipment.com","www.ep-equipment.com"} and parsed.path.startswith("/es/productos/")
    return parsed.scheme=="https" and parsed.hostname=="online.gamrentals.com" and parsed.path.startswith("/cl/")

def _seed_path(): return Path(__file__).parents[1]/"fixtures"/"gam-ep-models-2026-09-16.csv"

def _authorize_robots(transport,robots_url,targets,timeout,max_bytes):
    validate_public_url(robots_url,transport.resolve)
    response=transport.get(robots_url,headers={"Accept":"text/plain"},timeout=timeout,max_bytes=min(max_bytes,512_000))
    validate_public_url(response.final_url,transport.resolve)
    if response.status in {404,410}: return
    if response.status != 200: raise ValueError(f"robots bloqueado HTTP {response.status}: {robots_url}")
    parser=urllib.robotparser.RobotFileParser(); parser.set_url(robots_url); parser.parse(response.body.decode("utf-8",errors="replace").splitlines())
    if any(not parser.can_fetch("catalog-assets/1.0",target) for target in targets): raise ValueError("robots prohíbe harvest-ep")

def load_seed():
    with _seed_path().open(encoding="utf-8-sig",newline="") as handle: return list(csv.DictReader(handle))

def harvest_ep(root,transport,request_delay=1.0,max_pages=100,max_models=39,max_bytes=5_000_000,timeout=20.0):
    if request_delay < 0 or max_pages < 1 or max_models < 1: raise ValueError("límites harvest-ep inválidos")
    research=safe_path(root,"_control/research"); research.mkdir(parents=True,exist_ok=True)
    checkpoint_path=safe_path(root,"_control/research/ep-harvest-checkpoint.json")
    checkpoint={"format_version":1,"completed_listings":[],"live_items":[],"products":{}}
    if checkpoint_path.exists(): checkpoint=json.loads(checkpoint_path.read_text(encoding="utf-8"))
    completed=set(checkpoint.get("completed_listings",[])); requests=0
    authorized=set(checkpoint.get("robots_authorized",[]))
    for source,robots,targets in (("GAM","https://online.gamrentals.com/robots.txt",GAM_LISTINGS),("EP","https://ep-equipment.com/robots.txt",(EP_START,))):
        if source not in authorized:
            _authorize_robots(transport,robots,targets,timeout,max_bytes); requests+=1; authorized.add(source)
            checkpoint["robots_authorized"]=sorted(authorized)
            atomic_write(checkpoint_path,(json.dumps(checkpoint,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),root)
    for listing in GAM_LISTINGS[:max_pages]:
        if listing in completed: continue
        response=_fetch(transport,listing,timeout,max_bytes); requests+=1
        parsed=_parse(response.body,response.final_url)
        page=GAM_LISTINGS.index(listing)+1
        for position,(name,url,category) in enumerate(parsed.items,1):
            checkpoint["live_items"].append({"observed_name":name,"url":url,"category":category,"listing":listing,"position":position,"page":page})
        checkpoint["completed_listings"].append(listing); completed.add(listing)
        atomic_write(checkpoint_path,(json.dumps(checkpoint,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),root)
        if request_delay: time.sleep(request_delay)
    seed=load_seed(); seed_by_key={_key(r["canonical_candidate"]):r for r in seed}; live=checkpoint.get("live_items",[])
    live_by_key={_key(r["observed_name"]):r for r in live}
    added=sorted(r["observed_name"] for k,r in live_by_key.items() if k not in seed_by_key)
    removed=sorted(r["observed_name"] for k,r in seed_by_key.items() if k not in live_by_key)
    renamed=sorted({f'{seed_by_key[k]["observed_name"]} -> {live_by_key[k]["observed_name"]}' for k in seed_by_key.keys() & live_by_key.keys() if seed_by_key[k]["observed_name"] != live_by_key[k]["observed_name"]})
    if checkpoint.get("ep_catalog"):
        ep_items=checkpoint["ep_catalog"]
    else:
        ep_response=_fetch(transport,EP_START,timeout,max_bytes); requests+=1
        ep_items=[list(x) for x in _parse(ep_response.body,ep_response.final_url).items]
        checkpoint["ep_catalog"]=ep_items
        atomic_write(checkpoint_path,(json.dumps(checkpoint,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),root)
    ep_by_key={}
    for name,url,category in ep_items: ep_by_key.setdefault(_key(name),[]).append((name,url,category))
    inventory=[]; candidates=[]; source_rows=[]
    concrete=[r for r in seed if r["disposition"]=="OBSERVED"][:max_models]
    for seed_row in seed:
        model=seed_row["canonical_candidate"]; family=seed_row["disposition"]=="REVIEW"; live_row=live_by_key.get(_key(model),{})
        matches=ep_by_key.get(_key(model),[]) if not family and live_row else []
        ep_url=matches[0][1] if len(matches)==1 and _allowed_product(matches[0][1],"EP") else ""
        proposed_gam=live_row.get("url",""); gam_url=proposed_gam if proposed_gam and _allowed_product(proposed_gam,"GAM") else ""
        ep_assets=[]; gam_assets=[]
        if not family and model in {r["canonical_candidate"] for r in concrete}:
            product_key=_key(model)
            saved=checkpoint["products"].get(product_key)
            if saved: ep_assets=saved.get("ep_assets",[]); gam_assets=saved.get("gam_assets",[])
            else:
                if ep_url:
                    page=_fetch(transport,ep_url,timeout,max_bytes); requests+=1; ep_assets=[list(x) for x in _parse(page.body,page.final_url).assets]
                if gam_url:
                    page=_fetch(transport,gam_url,timeout,max_bytes); requests+=1; gam_assets=[list(x) for x in _parse(page.body,page.final_url).assets]
                checkpoint["products"][product_key]={"ep_assets":ep_assets,"gam_assets":gam_assets,"ep_url":ep_url,"gam_url":gam_url}
                atomic_write(checkpoint_path,(json.dumps(checkpoint,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),root)
                if request_delay: time.sleep(request_delay)
        ep_types={x[0] for x in ep_assets}
        selected=[("EP","primary",ep_url,x) for x in ep_assets]
        selected += [("GAM","fallback",gam_url,x) for x in gam_assets if x[0] not in ep_types]
        for source,role,page_url,(kind,url,evidence) in selected:
            candidates.append({"target_brand":"EP","model":model,"category":seed_row["category"],"asset_type":kind,"asset_role":"primary" if source=="EP" else "fallback","source_name":source,"source_role":role,"page_url":page_url,"asset_url":url,"expected_mime":"image/*" if kind=="image" else "application/pdf","expected_extension":"" if kind=="image" else ".pdf","language":"es","priority":0 if source=="EP" else 100,"model_evidence":evidence or model,"confidence":"HIGH","disposition":"REVIEW","http_status":"","observed_mime":"","validation_status":"VALIDATION_DEFERRED","notes":"direct asset discovered on exact model page; binary validation pending"})
            source_rows.append({"target_brand":"EP","model":model,"source_name":source,"source_role":role,"page_url":page_url,"asset_type":kind,"asset_url":url,"priority":0 if source=="EP" else 100,"expected_language":"es","enabled":"false","notes":"VALIDATION_DEFERRED; exact model page; direct asset discovered"})
        inventory.append({"target_brand":"EP","model":model,"category":seed_row["category"],"official_model_name":matches[0][0] if len(matches)==1 else "","ep_listing_url":EP_START,"ep_product_url":ep_url,"gam_product_url":gam_url,"ep_image_candidates":sum(x[0]=="image" for x in ep_assets),"ep_pdf_candidates":sum(x[0]=="technical_sheet" for x in ep_assets),"missing_image":str("image" not in ep_types).lower(),"missing_pdf":str("technical_sheet" not in ep_types).lower(),"gam_fallback_needed":str(any(x[0] not in ep_types for x in gam_assets)).lower(),"confidence":"REVIEW" if family or len(matches)!=1 else "HIGH","status":"FAMILY_REVIEW" if family else ("MATCHED" if len(matches)==1 else "PENDING_LOCAL_HARVEST"),"notes":seed_row["notes"]})
    source_rows.sort(key=lambda r:(r["model"].casefold(),int(r["priority"]),r["asset_type"],r["asset_url"]))
    atomic_write(research/"ep-model-inventory.csv",_csv_bytes(MODEL_FIELDS,inventory),root)
    atomic_write(research/"ep-asset-candidates.csv",_csv_bytes(CANDIDATE_FIELDS,candidates),root)
    atomic_write(safe_path(root,"_control/fuentes.csv"),_csv_bytes(COLUMNS,source_rows),root)
    summary={"format_version":1,"seed_models":len(seed),"live_models":len(live_by_key),"added":added,"removed":removed,"renamed":renamed,"ambiguous_families":sorted(FAMILIES),"sources":len(source_rows),"requests_this_run":requests,"assets_downloaded":0}
    audit_summary={key:value for key,value in summary.items() if key!="requests_this_run"}
    audit="# Recolección local EP/GAM\n\n"+json.dumps(audit_summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    atomic_write(research/"ep-source-audit.md",audit.encode("utf-8"),root)
    atomic_write(checkpoint_path,(json.dumps(checkpoint,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode(),root)
    return summary
