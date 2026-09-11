"""Exact, evidence-bearing reconciliation. No weak matching and no mutation."""
from __future__ import annotations
import hashlib,json
from .planning import operation
from .projection import build_safe_product_payload, project_candidate

STATES=frozenset({"create","reuse_exact","noop_exact","manual_review_required","blocked","retained_not_imported"})
def result(entity,identity,state,reason,evidence,**extra):
    if state not in STATES: raise ValueError("INVALID_RECONCILIATION_STATE")
    return {"entity":entity,"identity":identity,"state":state,"reason":reason,"evidence":evidence,**extra}
def _exact(items,key,value): return [x for x in items if x.get(key)==value]

def reconcile_category(desired,categories):
    matches=_exact(categories,"slug",desired["slug"])
    if len(matches)>1:return result("category",desired["slug"],"blocked","AMBIGUOUS_CATEGORY",matches)
    if not matches:return result("category",desired["slug"],"create","CATEGORY_ABSENT",[])
    item=matches[0]
    if item.get("parent_id")!=desired.get("parent_id"):return result("category",desired["slug"],"blocked","PARENT_MISMATCH",[item])
    return result("category",desired["slug"],"reuse_exact","EXACT_CATEGORY",[item],observed_id=item["id"])
def reconcile_brand(desired,brands):
    matches=_exact(brands,"slug",desired["slug"])
    if len(matches)>1:return result("brand",desired["slug"],"blocked","AMBIGUOUS_BRAND",matches)
    if not matches:return result("brand",desired["slug"],"create","BRAND_ABSENT",[])
    return result("brand",desired["slug"],"reuse_exact","EXACT_BRAND",matches,observed_id=matches[0]["id"])
def reconcile_supplier(key,suppliers,optional=True):
    if key is None:return result("supplier","none","reuse_exact","OPTIONAL_NULL",[],observed_id=None) if optional else result("supplier","none","blocked","SUPPLIER_REQUIRED",[])
    matches=_exact(suppliers,"name",key)
    if len(matches)!=1:return result("supplier",key,"blocked","AMBIGUOUS_OR_MISSING_SUPPLIER",matches)
    return result("supplier",key,"reuse_exact","EXACT_SUPPLIER",matches,observed_id=matches[0]["id"])
def natural_key(product): return (product.get("product_type","machinery"),product.get("slug"),product.get("model"),product.get("sku"))
def reconcile_product(desired,products):
    candidates=[x for x in products if natural_key(x)==natural_key(desired)]
    if len(candidates)>1:return result("product",desired["canonical_identity"],"blocked","AMBIGUOUS_NATURAL_KEY",candidates)
    if not candidates:return result("product",desired["canonical_identity"],"create","PRODUCT_ABSENT",[])
    observed=candidates[0]; comparable=desired["payload"]
    differences={k:{"desired":v,"observed":observed.get(k)} for k,v in comparable.items() if observed.get(k)!=v}
    if differences:return result("product",desired["canonical_identity"],"manual_review_required","PRODUCT_DIVERGED",[differences,observed])
    if not observed.get("relations_complete",False):return result("product",desired["canonical_identity"],"manual_review_required","RELATIONS_NOT_OBSERVABLE",[observed])
    return result("product",desired["canonical_identity"],"noop_exact","PRODUCT_EXACT",[observed],observed_id=observed["id"])

def reconcile_assets(product,entries):
    media=sorted(product.get("media",[]),key=lambda x:(x.get("role")!="primary",x.get("ordinal",0),x["sha256"]))
    primary=[x for x in media if x.get("role")=="primary"]; secondary=[x for x in media if x.get("role")=="secondary"]
    errors=[]
    if len(primary)!=1: errors.append("PRIMARY_COUNT")
    if len(secondary)>4: errors.append("SECONDARY_LIMIT")
    if primary and any(x["sha256"]==primary[0]["sha256"] for x in secondary): errors.append("DUPLICATE_IMAGE_HASH")
    for asset in media:
        data=entries.get(asset.get("entry_path"))
        if data is None or len(data)!=asset.get("size") or hashlib.sha256(data or b"").hexdigest()!=asset.get("sha256"): errors.append("ASSET_ENTRY_MISMATCH")
    state="blocked" if errors else "create"
    return result("images",product["canonical_identity"],state,errors[0] if errors else "ASSETS_VALID",media),media

def reconcile_document(document,entries,primary):
    data=entries.get(document.get("entry_path")); valid=data is not None and len(data)==document.get("size") and hashlib.sha256(data or b"").hexdigest()==document.get("sha256")
    if not valid:return result("technical_sheet" if primary else "document",document.get("sha256","missing"),"blocked","ASSET_ENTRY_MISMATCH",[document])
    return result("technical_sheet" if primary else "document",document["sha256"],"create" if primary else "retained_not_imported","ASSET_VALID" if primary else "NO_COMPATIBLE_RELATION",[document])

def build_operations(package_view,snapshot,policy):
    products=[]
    for path,data in package_view["entries"].items():
        if path.endswith("producto.json"): products.append(json.loads(data.decode("utf-8",errors="strict")))
    reconciliations=[]; operations=[]; external=[]; reviews=[]; retained=[]
    roots=[x for x in snapshot["collections"]["categories"] if x.get("parent_id") is None and x.get("slug")=="maquinarias"]
    if len(roots)==1: external.append({"scope":"external","namespace":"root","key":"maquinarias","binding_type":"entity_id","value":roots[0]["id"]})
    for product in sorted(products,key=lambda x:x["canonical_identity"]):
        mapping=product.get("category_mapping",{}); category={"name":mapping.get("name"),"slug":mapping.get("slug"),"parent_id":roots[0]["id"] if len(roots)==1 else None,"product_type":mapping.get("product_type","machinery")}
        brand={"name":product.get("brand_code"),"slug":product.get("brand_code","").casefold()}
        cr=reconcile_category(category,snapshot["collections"]["categories"]); br=reconcile_brand(brand,snapshot["collections"]["brands"]); sr=reconcile_supplier(product.get("supplier"),snapshot["collections"]["suppliers"],policy.get("supplier_optional",True)); reconciliations += [cr,br,sr]
        refs=[]; deps=[]
        for entity,want,rec,endpoint in (("category",category,cr,"/api/categories"),("brand",brand,br,"/api/brands")):
            key=want["slug"]
            if rec["state"]=="create":
                required=[{"scope":"external","namespace":"root","key":"maquinarias","binding_type":"entity_id"}] if entity=="category" else []
                payload={"name":want["name"],"slug":key,"is_active":True}
                if entity=="category":payload.update({"parent_id":required[0],"product_type":want["product_type"],"description":None,"order":0})
                op=operation(entity,"create",key,endpoint,payload,required,[{"scope":"produced","namespace":entity,"key":key,"binding_type":"entity_id"}]); operations.append(op); deps.append(op["operation_id"]); refs.append({"scope":"produced","namespace":entity,"key":key,"binding_type":"entity_id"})
            elif rec["state"]=="reuse_exact": external.append({"scope":"external","namespace":entity,"key":key,"binding_type":"entity_id","value":rec["observed_id"]}); refs.append({"scope":"external","namespace":entity,"key":key,"binding_type":"entity_id"})
            else: reviews.append(rec)
        projected=project_candidate({**product.get("structured_fields",{}),"name":product.get("canonical_model"),"model":product.get("canonical_model"),"slug":product["canonical_identity"],"product_type":category["product_type"]})
        if projected["issues"]: reviews.extend(projected["issues"]); continue
        safe=build_safe_product_payload(projected)
        desired={"canonical_identity":product["canonical_identity"],"product_type":category["product_type"],"slug":product["canonical_identity"],"model":product.get("canonical_model"),"sku":product.get("sku"),"payload":{**safe["payload"],"category_id":refs[0] if refs else None,"brand_id":refs[1] if len(refs)>1 else None,"supplier_id":sr.get("observed_id")},"safety_evidence":safe["safety_evidence"]}
        pr=reconcile_product(desired,snapshot["collections"]["products"]); reconciliations.append(pr)
        if pr["state"] in ("blocked","manual_review_required"): reviews.append(pr); continue
        if pr["state"]=="create":
            pop=operation("product","create",product["canonical_identity"],"/api/products",desired["payload"],refs,[{"scope":"produced","namespace":"product","key":product["canonical_identity"],"binding_type":"entity_id"}],deps,[path]); operations.append(pop); product_ref={"scope":"produced","namespace":"product","key":product["canonical_identity"],"binding_type":"entity_id"}; pdeps=[pop["operation_id"]]
            ar,media=reconcile_assets(product,package_view["entries"]); reconciliations.append(ar)
            if ar["state"]=="blocked":reviews.append(ar)
            else:
                for asset in media:
                    multipart={"product_id":product_ref,"file_entry":asset["entry_path"],"sha256":asset["sha256"],"size":asset["size"],"mime":asset["mime"],"alt_text":asset.get("alt_text",""),"is_main":asset["role"]=="primary","order":asset.get("ordinal",0),"source_filename":asset.get("source_filename")}
                    operations.append(operation("image","create",asset["sha256"],"/api/product-images",{"multipart":multipart},[product_ref],depends_on=pdeps,sources=[asset["entry_path"]]))
            for spec in projected["product_specs"]+product.get("product_specs",[]): operations.append(operation("spec","create",product["canonical_identity"]+":"+spec["key"],"/api/product-specs",{"product_id":product_ref,"key":spec["key"],"value":str(spec["value"]),"unit":spec.get("unit"),"order":spec.get("order",0)},[product_ref],depends_on=pdeps,sources=[path]))
            sheet=product.get("technical_sheet")
            if sheet:
                sheet_result=reconcile_document(sheet,package_view["entries"],True); reconciliations.append(sheet_result)
                if sheet_result["state"]=="blocked":reviews.append(sheet_result)
                else: operations.append(operation("technical_sheet","create",sheet["sha256"],"/api/technical-sheets/",{"multipart":{"name":sheet.get("name"),"file_entry":sheet["entry_path"],"sha256":sheet["sha256"],"mime":sheet["mime"]}},depends_on=pdeps,sources=[sheet["entry_path"]]))
        for document in product.get("additional_documents",[]):
            document_result=reconcile_document(document,package_view["entries"],False); retained.append(document_result)
            if document_result["state"]=="blocked":reviews.append(document_result)
    return {"operations":operations,"external_bindings":external,"reconciliations":reconciliations,"reviews":reviews,"retained_documents":retained}
