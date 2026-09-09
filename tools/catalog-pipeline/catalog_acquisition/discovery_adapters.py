"""Pure HTML adapters. Network access is deliberately impossible from this module."""
from __future__ import annotations
import json,re
from html.parser import HTMLParser
from urllib.parse import urlsplit
from .discovery import DiscoveryLink, LinkEvidence, ParseResult, SourceDefinition, SOURCES
from .urls import UnsafeUrlError, canonicalize

def _text(value:str)->str: return " ".join(value.split())
class StructureChanged(ValueError): pass

class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.links=[]; self.stack=[]; self.scripts=[]; self._script=None; self.breadcrumb=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); self.stack.append((tag,a,[]))
        if tag=="script" and a.get("type","").casefold() in ("application/ld+json","application/json"): self._script=[a,[]]
    def handle_data(self,data):
        for _,_,parts in self.stack: parts.append(data)
        if self._script: self._script[1].append(data)
    def handle_endtag(self,tag):
        if tag=="script" and self._script:
            self.scripts.append((self._script[0],"".join(self._script[1]))); self._script=None
        if not self.stack:return
        opened,attrs,parts=self.stack.pop()
        if opened=="a" and attrs.get("href"):
            self.links.append((attrs,_text("".join(parts))))

class BaseDiscoveryAdapter:
    adapter_id=""; adapter_version=""; source:SourceDefinition
    product_path:re.Pattern[str]; category_path:re.Pattern[str]
    def parse(self,body:bytes,*,base_url:str,content_type:str,encoding:str|None,snapshot_reference:str,expected_products:bool=False)->ParseResult:
        if content_type.split(";",1)[0].casefold() not in ("text/html","application/xhtml+xml"): raise StructureChanged("HTML snapshot required")
        parser=_Document(); parser.feed(body.decode(encoding or "utf-8",errors="replace")); result=ParseResult("listing")
        for attrs,label in parser.links:
            href=attrs["href"]; locator=self._locator(attrs); kind=self._classify(href,attrs)
            evidence=LinkEvidence(base_url,locator,href,snapshot_reference,self.adapter_id+".links",self.adapter_version)
            try: url=canonicalize(href,base_url=base_url,source=self.source).canonical
            except UnsafeUrlError as exc:
                result.links.append(DiscoveryLink(href,None,"blocked" if urlsplit(href).hostname else "ignored",label,label,None,evidence,str(exc))); continue
            if kind=="unknown":
                result.warnings.append("unknown_link_requires_review")
            model=attrs.get("data-model") or None
            result.links.append(DiscoveryLink(href,url,kind,label,label,model,evidence))
            if kind=="category": result.categories.append({"source":self.source.source,"source_role":self.source.role,"source_category_key":url,"name_raw":label,"name_visible":label,"url":url,"parent":None,"breadcrumb":[],"evidence_reference":snapshot_reference,"rule_version":self.adapter_version})
        for attrs,payload in parser.scripts:
            try: decoded=json.loads(payload)
            except json.JSONDecodeError: result.warnings.append("invalid_embedded_json"); continue
            (result.json_ld if attrs.get("type","").casefold()=="application/ld+json" else result.embedded_json).append(decoded)
        candidates=[x for x in result.links if x.kind=="product_candidate"]
        if expected_products and not candidates: raise StructureChanged("expected products but extraction was empty")
        if not parser.links: result.warnings.append("missing_expected_structure")
        return result
    def _locator(self,a):
        if a.get("id"): return "a#"+a["id"]
        if a.get("class"): return "a."+".".join(a["class"].split())
        if a.get("rel"): return "a[rel='"+a["rel"]+"']"
        return "a[href]"
    def _classify(self,href,a):
        path=urlsplit(href).path
        if any(path.lower().endswith(x) for x in (".pdf",".jpg",".jpeg",".png",".webp",".svg")): return "ignored"
        if a.get("rel","").casefold()=="next" or re.search(r"(?:[?&](?:page|p)=\d+|/page/\d+)",href): return "pagination"
        if self.product_path.search(path): return "product_candidate"
        if self.category_path.search(path): return "category"
        return "unknown"

class EPDiscoveryAdapter(BaseDiscoveryAdapter):
    adapter_id="ep.catalog.discovery"; adapter_version="ep-discovery-v1"; source=SOURCES["ep"]
    # Provisional rules are exercised only by structural fixtures; live capture remains blocked until verified.
    product_path=re.compile(r"^/es/productos/[^/]+/[^/]+/?$")
    category_path=re.compile(r"^/es/productos/[^/]+/?$")
class GAMDiscoveryAdapter(BaseDiscoveryAdapter):
    adapter_id="gam.cl.catalog.discovery"; adapter_version="gam-discovery-v1"; source=SOURCES["gam"]
    # Synthetic fixture contract only; this is not a claim about GAM's live structure.
    product_path=re.compile(r"^/cl/826-ep/productos/[^/]+-\d+\.html$")
    category_path=re.compile(r"^/cl/826-ep/?$")

ADAPTERS={"ep":EPDiscoveryAdapter(),"gam":GAMDiscoveryAdapter()}
