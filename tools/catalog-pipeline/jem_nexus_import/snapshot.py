"""Closed, order-independent representation of an observed local JEM API."""
from __future__ import annotations
from catalog_pipeline_common.serialization import canonical_bytes,content_fingerprint

SCHEMA_VERSION="1.0.0"; RULES_VERSION="jem-snapshot-v2"
COLLECTIONS=("categories","brands","suppliers","products","product_images","product_specs","technical_sheets")
READ_TARGETS={"categories":"/api/categories?include_inactive=true","brands":"/api/brands?include_inactive=true","suppliers":"/api/suppliers?include_inactive=true","products":"/api/products?include_unpublished=true","product_images":"/api/product-images","product_specs":"/api/product-specs","technical_sheets":"/api/technical-sheets/"}

class SnapshotError(ValueError):
    def __init__(self,code,detail): self.code=code; super().__init__(detail)

def _integer_relation(item,structured_key,read_key,read_object=False):
    """Resolve one closed pair of relationship spellings without rewriting ``item``."""
    present=[]
    if structured_key in item: present.append(item[structured_key])
    if read_key in item:
        observed=item[read_key]
        if read_object:
            observed=observed.get("id") if isinstance(observed,dict) else observed
        present.append(observed)
    if not present or any(type(value) is not int for value in present) or len(set(present))!=1:
        raise SnapshotError("ORPHAN_RELATION",structured_key)
    return present[0]

def _nullable_integer_relation(item,structured_key,read_key):
    present=[item[key] for key in (structured_key,read_key) if key in item]
    if not present: return None
    if any(value is not None and type(value) is not int for value in present) or len(set(present))!=1:
        raise SnapshotError("ORPHAN_RELATION",structured_key)
    return present[0]

def _collection_sort_key(item):
    """Order valid integer IDs historically and every other JSON ID totally."""
    canonical_item=canonical_bytes(item)
    if isinstance(item,dict) and type(item.get("id")) is int:
        return (0,item["id"],b"",b"",canonical_item)
    present=isinstance(item,dict) and "id" in item
    identifier=item.get("id") if present else None
    kind=("missing" if not present else
          "null" if identifier is None else
          "boolean" if isinstance(identifier,bool) else
          "string" if isinstance(identifier,str) else
          "array" if isinstance(identifier,list) else
          "object" if isinstance(identifier,dict) else
          "number" if isinstance(identifier,(int,float)) else "unsupported")
    canonical_id=canonical_bytes(identifier) if present else b""
    return (1,0,kind.encode("ascii"),canonical_id,canonical_item)

def semantic_fingerprint(snapshot):
    semantic={"schema_version":SCHEMA_VERSION,"rules_version":RULES_VERSION,"contract_fingerprint":snapshot.get("contract_fingerprint"),
              "classification":snapshot.get("classification"),"collections":{k:sorted(snapshot.get("collections",{}).get(k,[]),key=_collection_sort_key) for k in COLLECTIONS},
              "endpoints":sorted(({k:v for k,v in e.items() if k!="captured_at"} for e in snapshot.get("endpoints",[])),key=lambda x:x.get("path",""))}
    return content_fingerprint(semantic)

def validate_snapshot(value,contract_fingerprint=None):
    if value.get("schema_version")!=SCHEMA_VERSION or value.get("complete") is not True: raise SnapshotError("SNAPSHOT_INCOMPLETE","snapshot must be complete v1")
    if value.get("classification") not in ("fixture_only","local_development"): raise SnapshotError("SNAPSHOT_CLASSIFICATION","unsafe classification")
    if contract_fingerprint and value.get("contract_fingerprint")!=contract_fingerprint: raise SnapshotError("CONTRACT_FINGERPRINT","snapshot contract differs")
    collections=value.get("collections",{})
    if set(collections)!=set(COLLECTIONS): raise SnapshotError("ENDPOINT_REQUIRED","all collections are required")
    endpoints=value.get("endpoints",[])
    endpoint_map={e.get("collection"):e.get("path") for e in endpoints if isinstance(e,dict)}
    if len(endpoints)!=len(COLLECTIONS) or endpoint_map!=READ_TARGETS or any(not e.get("complete") or e.get("status")!=200 or "json" not in e.get("mime","").lower() or e.get("pages_received")!=1 or e.get("pages_expected")!=1 for e in endpoints):
        raise SnapshotError("PAGINATION_INCOMPLETE","endpoint evidence is incomplete")
    ids={}
    for name,items in collections.items():
        values=[x.get("id") for x in items]
        if any(type(identifier) is not int or identifier <= 0 for identifier in values) or len(values)!=len(set(values)): raise SnapshotError("DUPLICATE_ID",name)
        if name in ("categories","brands","suppliers","products"):
            folded=[str(x.get("slug",x.get("name",""))).casefold() for x in items]
            if "" in folded or len(folded)!=len(set(folded)): raise SnapshotError("IDENTITY_COLLISION",name)
        ids[name]=set(values)
    for category in collections["categories"]:
        if "parent_id" not in category: raise SnapshotError("RELATION_NOT_OBSERVABLE","category.parent_id")
        parent_id=_nullable_integer_relation(category,"parent_id","parent_id")
        if parent_id is not None and parent_id not in ids["categories"]: raise SnapshotError("ORPHAN_RELATION","category.parent_id")
    for product in collections["products"]:
        if product.get("relations_complete") is not True: raise SnapshotError("RELATION_NOT_OBSERVABLE","product")
        if _integer_relation(product,"category_id","category_id") not in ids["categories"]: raise SnapshotError("ORPHAN_RELATION","product.category_id")
        for field,target in (("brand_id","brands"),("supplier_id","suppliers"),("technical_sheet_id","technical_sheets")):
            relation=_nullable_integer_relation(product,field,field)
            if field not in product: raise SnapshotError("RELATION_NOT_OBSERVABLE","product."+field)
            if relation is not None and relation not in ids[target]: raise SnapshotError("ORPHAN_RELATION","product."+field)
    for name in ("product_images","product_specs"):
        if any(_integer_relation(item,"product_id","product_id") not in ids["products"] for item in collections[name]): raise SnapshotError("ORPHAN_RELATION",name+".product_id")
    actual=semantic_fingerprint(value)
    if value.get("semantic_fingerprint")!=actual: raise SnapshotError("SNAPSHOT_FINGERPRINT","semantic fingerprint differs")
    return value
