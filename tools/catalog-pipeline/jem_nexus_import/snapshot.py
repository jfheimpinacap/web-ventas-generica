"""Closed, order-independent representation of an observed local JEM API."""
from __future__ import annotations
from catalog_pipeline_common.serialization import content_fingerprint

SCHEMA_VERSION="1.0.0"; RULES_VERSION="jem-snapshot-v1"
COLLECTIONS=("categories","brands","suppliers","products","product_images","product_specs","technical_sheets")

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
        parent_id=_nullable_integer_relation(category,"parent_id","parent")
        if parent_id is not None and parent_id not in ids["categories"]: raise SnapshotError("ORPHAN_RELATION","category.parent_id")
    for product in collections["products"]:
        # The captured GET exposes an integer ``category``; the inspected
        # ProductListReadDto also contracts a CategoryReadDto object. Historical
        # structured snapshots use the write-side ``category_id``.
        if _integer_relation(product,"category_id","category",read_object=True) not in ids["categories"]: raise SnapshotError("ORPHAN_RELATION","product.category_id")
    for name in ("product_images","product_specs"):
        # Inspected read DTOs expose ``Product`` while write DTOs also accept
        # ``product_id``.  Snapshot validation accepts either real read shape.
        if any(_integer_relation(item,"product_id","product") not in ids["products"] for item in collections[name]): raise SnapshotError("ORPHAN_RELATION",name+".product_id")
    actual=semantic_fingerprint(value)
    if value.get("semantic_fingerprint")!=actual: raise SnapshotError("SNAPSHOT_FINGERPRINT","semantic fingerprint differs")
    return value
