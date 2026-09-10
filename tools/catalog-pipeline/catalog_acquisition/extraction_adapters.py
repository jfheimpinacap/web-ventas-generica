"""Pure, passive HTML extraction adapters; bytes and metadata are injected by callers."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlsplit, urlunsplit

PAGE_TYPES = frozenset({"product", "series", "family", "listing", "document_landing",
                        "unknown", "structure_changed", "parse_failed"})
MAX_BYTES = 2_000_000
MAX_NODES = 20_000
MAX_JSON_DEPTH = 20

@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    locator: str
    text: list[str] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)

class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.root=Node("document",{},"/"); self.stack=[self.root]; self.count=0
    def handle_starttag(self,tag,attrs):
        self.count+=1
        if self.count>MAX_NODES: raise ValueError("html_node_limit_exceeded")
        parent=self.stack[-1]; index=1+sum(x.tag==tag for x in parent.children)
        node=Node(tag,dict(attrs),f"{parent.locator.rstrip('/')}/{tag}[{index}]")
        parent.children.append(node)
        if tag not in {"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}: self.stack.append(node)
    def handle_startendtag(self,tag,attrs): self.handle_starttag(tag,attrs); self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag: self.stack=self.stack[:i]; return
    def handle_data(self,data): self.stack[-1].text.append(data)

def _walk(node):
    for child in node.children: yield child; yield from _walk(child)
def _text(node): return "".join(node.text)+"".join(_text(x) for x in node.children)
def _classes(node): return set(node.attrs.get("class","").lower().split())
def _json_depth(value,depth=0):
    if depth>MAX_JSON_DEPTH: raise ValueError("json_depth_limit_exceeded")
    if isinstance(value,dict):
        for item in value.values(): _json_depth(item,depth+1)
    elif isinstance(value,list):
        for item in value: _json_depth(item,depth+1)

def _candidate_url(raw,base):
    split=urlsplit(urljoin(base,raw)); return urlunsplit((split.scheme.lower(),split.netloc.lower(),split.path,split.query,""))

def _approved_host(host,approved):
    """Compare DNS host names only; ports and URL spelling never grant authority."""
    if not host: return False
    normalized=host.casefold().rstrip(".")
    for value in approved:
        parsed=urlsplit(value if "://" in value else "//"+value)
        candidate=parsed.hostname
        if candidate and candidate.casefold().rstrip(".")==normalized: return True
    return False

class FixtureHtmlExtractionAdapter:
    """Conservative fixture-only rules, never approved as live selectors."""
    adapter_id="generic-passive-html"; adapter_version="1.0.0"; structure_verified=False
    rules_version="fixture-rules-1.0.0"
    rules=({"rule_id":"fixture-page-kind","version":"1.0.0","compatible_sources":["ep","gam"],"page_type":"unknown","target":"page_classification","locator":"[data-page-type]","cardinality":"exactly_one","missing":"classify_unknown","status":"fixture_only","structural_evidence":"fixtures/extraction"},
           {"rule_id":"fixture-raw-fields","version":"1.0.0","compatible_sources":["ep","gam"],"page_type":"product_or_series","target":"raw_field","locator":"[data-field]","cardinality":"zero_or_more","missing":"empty_product_blocks","status":"fixture_only","structural_evidence":"fixtures/extraction"},
           {"rule_id":"fixture-raw-tables","version":"1.0.0","compatible_sources":["ep","gam"],"page_type":"product_or_series","target":"raw_table","locator":"table","cardinality":"zero_or_more","missing":"preserve_absence","status":"fixture_only","structural_evidence":"fixtures/extraction"},
           {"rule_id":"fixture-linked-assets","version":"1.0.0","compatible_sources":["ep","gam"],"page_type":"any_classified","target":"url_candidate","locator":"img,a.document","cardinality":"zero_or_more","missing":"preserve_absence","status":"fixture_only","structural_evidence":"fixtures/extraction"})

    def parse(self,body:bytes,metadata:dict)->dict:
        issues=[]
        if len(body)>MAX_BYTES: return self._failed("parse_failed","content_size_limit_exceeded")
        try: text=body.decode(metadata["encoding"],errors="strict")
        except (UnicodeError,LookupError): return self._failed("parse_failed","invalid_declared_encoding")
        parser=_Document()
        try: parser.feed(text); parser.close()
        except Exception as exc:
            return self._failed("parse_failed",str(exc))
        nodes=list(_walk(parser.root)); marker=next((n for n in nodes if "data-page-type" in n.attrs),None)
        page_type=marker.attrs.get("data-page-type","unknown") if marker else "unknown"
        if page_type not in PAGE_TYPES: page_type="structure_changed"
        if page_type in {"unknown","structure_changed"}: issues.append(self._issue("page_structure_unrecognized",marker.locator if marker else "/"))
        fields=[]; media=[]; documents=[]; tables=[]; jsonld=[]
        for node in nodes:
            if "data-field" in node.attrs:
                fields.append({"source_field_raw":node.attrs["data-field"],"raw_value":_text(node),
                    "raw_unit":node.attrs.get("data-unit"),"locator":node.locator,
                    "scope":{"kind":node.attrs.get("data-scope","unscoped"),"value":node.attrs.get("data-model")},
                    "semantic_hint":None})
            if node.tag=="img":
                for attribute in ("src","data-src"):
                    if node.attrs.get(attribute): media.append(self._media(node,node.attrs[attribute],attribute,metadata))
                if node.attrs.get("srcset"):
                    for value in node.attrs["srcset"].split(","): media.append(self._media(node,value.strip().split()[0],"srcset",metadata))
            if node.tag=="a" and node.attrs.get("href") and ("document" in _classes(node) or node.attrs.get("data-document-kind")):
                documents.append(self._document(node,metadata))
            if node.tag=="script" and node.attrs.get("type","").lower()=="application/ld+json":
                try:
                    value=json.loads(_text(node)); _json_depth(value); jsonld.append({"locator":node.locator,"value":value})
                    media.extend(self._jsonld_media(value,node,metadata))
                except (json.JSONDecodeError,ValueError): issues.append(self._issue("invalid_json_ld",node.locator))
            if node.tag=="table": tables.append(self._table(node,issues))
        if metadata.get("expected_page_type")=="product" and page_type=="listing": issues.append(self._issue("listing_received_as_product",marker.locator if marker else "/",True))
        if metadata.get("expected_page_type")=="product" and page_type=="product" and not fields and not tables:
            issues.append(self._issue("empty_product_extraction",marker.locator if marker else "/",True))
        if page_type=="structure_changed": issues.append(self._issue("source_structure_changed","/",True))
        return {"page_type":page_type,"classification_rule_id":"fixture-page-kind","classification_rule_version":"1.0.0",
                "fields":fields,"tables":tables,"media":media,"documents":documents,"json_ld":jsonld,"issues":issues}

    def _table(self,node,issues):
        rows=[]; occupied={}
        for r,row in enumerate((x for x in _walk(node) if x.tag=="tr")):
            cells=[]; logical_column=0
            for physical_column,cell in enumerate(x for x in row.children if x.tag in {"th","td"}):
                while (r,logical_column) in occupied: logical_column+=1
                rowspan=int(cell.attrs.get("rowspan","1")) if cell.attrs.get("rowspan","1").isdigit() else 1
                colspan=int(cell.attrs.get("colspan","1")) if cell.attrs.get("colspan","1").isdigit() else 1
                cells.append({"row":r,"physical_column":physical_column,"column":logical_column,"kind":"header" if cell.tag=="th" else "value","raw_value":_text(cell),
                              "raw_unit":cell.attrs.get("data-unit"),"rowspan":rowspan,"colspan":colspan,"locator":cell.locator,
                              "model_scope":cell.attrs.get("data-model")})
                for logical_row in range(r,r+rowspan):
                    for column in range(logical_column,logical_column+colspan): occupied[(logical_row,column)]=cell.locator
                logical_column+=colspan
            rows.append({"row":r,"cells":cells})
        column_models={column:cell["model_scope"] for raw_row in rows for cell in raw_row["cells"] if cell["model_scope"]
                       for column in range(cell["column"],cell["column"]+cell["colspan"])}
        ambiguous=[]
        for raw_row in rows:
            for cell in raw_row["cells"]:
                covered_models={column_models.get(column) for column in range(cell["column"],cell["column"]+cell["colspan"])}-{None}
                explicit_scope=next((x for x in _walk(node) if x.locator==cell["locator"]),None)
                if cell["colspan"]>1 and len(covered_models)>1 and not (explicit_scope and (explicit_scope.attrs.get("data-scope") or explicit_scope.attrs.get("data-model"))):
                    ambiguous.append(cell["locator"])
                if cell["kind"]=="value" and cell["model_scope"] is None and len(covered_models)==1:
                    cell["model_scope"]=next(iter(covered_models))
                elif cell["kind"]=="value" and cell["model_scope"] is None and cell["colspan"]==1:
                    cell["model_scope"]=column_models.get(cell["column"])
        for locator in sorted(set(ambiguous)): issues.append(self._issue("ambiguous_merged_cell",locator))
        widths={max((c["column"]+c["colspan"] for c in r["cells"]),default=0) for r in rows}
        irregular=len(widths)>1 or bool(ambiguous)
        if len(widths)>1: issues.append(self._issue("irregular_table",node.locator))
        return {"caption":next((_text(x) for x in node.children if x.tag=="caption"),None),"locator":node.locator,"rows":rows,"irregular":irregular}

    def _media(self,node,raw,attribute,meta):
        resolved=_candidate_url(raw,meta["canonical_url"]); host=urlsplit(resolved).hostname
        classes=_classes(node); kind=next((x for x in ("logo","banner","icon","thumbnail") if x in classes),node.attrs.get("data-image-kind","unknown"))
        scheme=urlsplit(resolved).scheme
        status="rejected_audited" if scheme not in {"http","https"} or kind in {"logo","banner","icon"} else "candidate" if _approved_host(host,meta.get("approved_hosts",[])) else "pending_host_review"
        return {"original_url":raw,"candidate_url":resolved,"referrer":meta["canonical_url"],"locator":node.locator,"source_attribute":attribute,
                "alt_raw":node.attrs.get("alt"),"title_raw":node.attrs.get("title"),"relationship":kind,"model_scope":node.attrs.get("data-model"),
                "host":host,"apparent_extension":resolved.rsplit(".",1)[-1].lower() if "." in urlsplit(resolved).path else None,"scope_status":status}
    def _jsonld_media(self,value,node,meta,path="$"):
        found=[]
        if isinstance(value,dict):
            for key,item in value.items():
                child_path=f"{path}.{key}"
                if key in {"image","thumbnailUrl","contentUrl"}:
                    candidates=item if isinstance(item,list) else [item]
                    for index,candidate in enumerate(candidates):
                        raw=candidate.get("contentUrl") or candidate.get("url") if isinstance(candidate,dict) else candidate
                        if isinstance(raw,str) and raw:
                            synthetic=Node("script",{"data-image-kind":"json_ld"},f"{node.locator}/{child_path}[{index}]")
                            found.append(self._media(synthetic,raw,key,meta))
                    continue
                found.extend(self._jsonld_media(item,node,meta,child_path))
        elif isinstance(value,list):
            for index,item in enumerate(value): found.extend(self._jsonld_media(item,node,meta,f"{path}[{index}]"))
        return found
    def _document(self,node,meta):
        raw=node.attrs["href"]; url=_candidate_url(raw,meta["canonical_url"]); filename=urlsplit(url).path.rsplit("/",1)[-1] or None
        return {"original_url":raw,"candidate_url":url,"referrer":meta["canonical_url"],"locator":node.locator,"link_text_raw":_text(node),
                "apparent_filename":filename,"document_kind":node.attrs.get("data-document-kind","unknown"),"language_hint":node.attrs.get("data-language"),
                "revision_hint":node.attrs.get("data-revision"),"model_scope":node.attrs.get("data-model"),"review_status":"pending"}
    def _issue(self,code,locator,blocking=False): return {"code":code,"locator":locator,"blocking":blocking,"review_status":"required"}
    def _failed(self,page_type,code): return {"page_type":page_type,"classification_rule_id":"fixture-page-kind","classification_rule_version":"1.0.0","fields":[],"tables":[],"media":[],"documents":[],"json_ld":[],"issues":[self._issue(code,"/",True)]}
