"""Pure adapter from commercial read DTO JSON to the canonical snapshot view."""
from __future__ import annotations

PRODUCT_FIELDS=("id","name","slug","category_id","brand_id","supplier_id","technical_sheet_id",
 "product_type","condition","short_description","description","model","sku","working_height_m",
 "terrain_type","year","hours_meter","maximum_load_capacity_kg","machine_weight_kg","power_source",
 "includes_technical_review","includes_commercial_technical_advice","includes_coordinated_delivery",
 "price","price_currency","price_tax_mode","price_visible","stock_status","is_featured","is_published",
 "created_at","updated_at")

class NormalizationError(ValueError):
    def __init__(self,code,detail): self.code=code; super().__init__(detail)

def _id(value, field, nullable=False):
    if value is None and nullable: return None
    if type(value) is not int or value <= 0: raise NormalizationError("RELATION_ID_INVALID",field)
    return value

def _relation(row,direct,nested,nullable):
    if direct not in row: raise NormalizationError("RELATION_NOT_OBSERVABLE",direct)
    value=_id(row[direct],direct,nullable)
    if nested in row:
        obj=row[nested]
        nested_id=None if obj is None else (_id(obj["id"],nested,False) if isinstance(obj,dict) and "id" in obj else (_raise("RELATION_OBJECT_INVALID",nested)))
        if nested_id != value: raise NormalizationError("RELATION_CONTRADICTORY",direct)
    return value

def _raise(code,detail): raise NormalizationError(code,detail)

def _copy_required(row,fields,collection):
    if not isinstance(row,dict): raise NormalizationError("DTO_OBJECT_REQUIRED",collection)
    missing=[field for field in fields if field not in row]
    if missing: raise NormalizationError("DTO_FIELD_MISSING",collection+"."+missing[0])
    return {field:row[field] for field in fields}

def normalize_collections(source):
    result={}
    for name,items in source.items():
        if not isinstance(items,list): raise NormalizationError("COLLECTION_SHAPE",name)
        normalized=[]
        for row in items:
            if name=="categories":
                if "parent_id" not in row and "parent" not in row: _raise("RELATION_NOT_OBSERVABLE","parent_id")
                observed=[_id(row[key],key,True) for key in ("parent_id","parent") if key in row]
                if any(value != observed[0] for value in observed): _raise("RELATION_CONTRADICTORY","parent_id")
                item=dict(row); item["parent_id"]=observed[0]
                item.pop("parent",None)
            elif name=="products":
                item=_copy_required(row,PRODUCT_FIELDS,name)
                item["category_id"]=_relation(row,"category_id","category",False)
                item["brand_id"]=_relation(row,"brand_id","brand",True)
                item["supplier_id"]=_relation(row,"supplier_id","supplier",True)
                item["technical_sheet_id"]=_relation(row,"technical_sheet_id","technical_sheet",True)
                item["relations_complete"]=True
            elif name in ("product_images","product_specs"):
                if "product" not in row: raise NormalizationError("RELATION_NOT_OBSERVABLE",name+".product_id")
                item=dict(row); item["product_id"]=_id(row["product"],name+".product_id"); item.pop("product",None)
                if name=="product_specs":
                    if "name" not in item: raise NormalizationError("DTO_FIELD_MISSING","product_specs.key")
                    item["key"]=item.pop("name")
            else: item=dict(row) if isinstance(row,dict) else _raise("DTO_OBJECT_REQUIRED",name)
            normalized.append(item)
        result[name]=normalized
    return result
