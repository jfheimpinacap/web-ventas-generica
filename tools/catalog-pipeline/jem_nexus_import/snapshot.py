"""Closed, order-independent representation of an observed local JEM API."""
from __future__ import annotations
from catalog_pipeline_common.serialization import content_fingerprint

SCHEMA_VERSION="1.0.0"; RULES_VERSION="jem-snapshot-v1"
COLLECTIONS=("categories","brands","suppliers","products","product_images","product_specs","technical_sheets")

class SnapshotError(ValueError):
    def __init__(self,code,detail): self.code=code; super().__init__(detail)

def semantic_fingerprint(snapshot):
    semantic={"schema_version":SCHEMA_VERSION,"rules_version":RULES_VERSION,"contract_fingerprint":snapshot.get("contract_fingerprint"),
              "classification":snapshot.get("classification"),"collections":{k:sorted(snapshot.get("collections",{}).get(k,[]),key=lambda x:(x.get("id",-1),str(x))) for k in COLLECTIONS},
              "endpoints":sorted(({k:v for k,v in e.items() if k!="captured_at"} for e in snapshot.get("endpoints",[])),key=lambda x:x.get("path",""))}
    return content_fingerprint(semantic)

def validate_snapshot(value,contract_fingerprint=None):
    if value.get("schema_version")!=SCHEMA_VERSION or value.get("complete") is not True: raise SnapshotError("SNAPSHOT_INCOMPLETE","snapshot must be complete v1")
    if value.get("classification") not in ("fixture_only","local_development"): raise SnapshotError("SNAPSHOT_CLASSIFICATION","unsafe classification")
    if contract_fingerprint and value.get("contract_fingerprint")!=contract_fingerprint: raise SnapshotError("CONTRACT_FINGERPRINT","snapshot contract differs")
    collections=value.get("collections",{})
    if set(collections)!=set(COLLECTIONS): raise SnapshotError("ENDPOINT_REQUIRED","all collections are required")
    endpoints=value.get("endpoints",[])
    if {e.get("collection") for e in endpoints}!=set(COLLECTIONS) or any(not e.get("complete") or e.get("status")!=200 or "json" not in e.get("mime","").lower() or e.get("pages_received")!=e.get("pages_expected") for e in endpoints):
        raise SnapshotError("PAGINATION_INCOMPLETE","endpoint evidence is incomplete")
    ids={}
    for name,items in collections.items():
        values=[x.get("id") for x in items]
        if None in values or len(values)!=len(set(values)): raise SnapshotError("DUPLICATE_ID",name)
        if name in ("categories","brands","suppliers","products"):
            folded=[str(x.get("slug",x.get("name",""))).casefold() for x in items]
            if "" in folded or len(folded)!=len(set(folded)): raise SnapshotError("IDENTITY_COLLISION",name)
        ids[name]=set(values)
    for category in collections["categories"]:
        if category.get("parent_id") is not None and category["parent_id"] not in ids["categories"]: raise SnapshotError("ORPHAN_RELATION","category.parent_id")
    for product in collections["products"]:
        if product.get("category_id") not in ids["categories"]: raise SnapshotError("ORPHAN_RELATION","product.category_id")
    for name in ("product_images","product_specs"):
        if any(item.get("product_id") not in ids["products"] for item in collections[name]): raise SnapshotError("ORPHAN_RELATION",name+".product_id")
    actual=semantic_fingerprint(value)
    if value.get("semantic_fingerprint")!=actual: raise SnapshotError("SNAPSHOT_FINGERPRINT","semantic fingerprint differs")
    return value
