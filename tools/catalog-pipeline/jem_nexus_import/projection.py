"""Conservative candidate projection against the inspected JEM contract."""
from __future__ import annotations

STRUCTURED_FIELDS = {"name","slug","category_id","brand_id","supplier_id","technical_sheet","product_type","condition","short_description","description","model","sku","working_height_m","terrain_type","year","hours_meter","maximum_load_capacity_kg","machine_weight_kg","power_source","includes_technical_review","includes_commercial_technical_advice","includes_coordinated_delivery","price","price_currency","price_tax_mode","price_visible","stock_status","is_featured","is_published"}
FUTURE_SPEC_ONLY = {"maximum_lift_height_mm", "battery_voltage_v", "battery_capacity_ah", "battery_chemistry"}
ENUMS = {"product_type":{"machinery","spare_part","service"},"condition":{"new","used","refurbished","not_applicable"},"stock_status":{"available","on_request","sold","reserved"},"power_source":{"diesel","electric_24v","electric_lithium"},"terrain_type":{"indoor_smooth","outdoor","outdoor_slopes_and_ramps"}}

def project_candidate(values: dict[str, object]) -> dict[str, object]:
    structured={}; specs=[]; issues=[]; evidence=[]
    safe={"price":None,"price_visible":False,"is_featured":False,"is_published":False}
    for key, value in values.items():
        if key in ENUMS and value not in ENUMS[key]: issues.append({"code":"UNKNOWN_ENUM","field":key,"blocking":True})
        elif key in FUTURE_SPEC_ONLY: specs.append({"key":key,"value":value}); evidence.append({"source_pointer":"/"+key,"target_field":"ProductSpec.value","transformation":"preserve","rule_version":"jem-projection-v1","provenance":"audited_package","result":"projected"})
        elif key in STRUCTURED_FIELDS:
            if key in safe and value!=safe[key]: issues.append({"code":"UNSAFE_COMMERCIAL_OVERRIDE","field":key,"blocking":True})
            structured[key]=value
            evidence.append({"source_pointer":"/"+key,"target_field":key,"transformation":"identity","rule_version":"jem-projection-v1","provenance":"audited_package","result":"projected"})
        else: specs.append({"key":key,"value":value}); evidence.append({"source_pointer":"/"+key,"target_field":"ProductSpec.value","transformation":"preserve_unknown","rule_version":"jem-projection-v1","provenance":"audited_package","result":"review_required"})
    # Lift/mast height is deliberately never inferred as working_height_m.
    return {"structured_fields":structured,"product_specs":specs,"field_evidence":evidence,"issues":issues,"ready":not issues}

def build_safe_product_payload(projection: dict[str, object]) -> dict[str, object]:
    """Copy a validated projection and apply explicit future-import safety policy."""
    if projection.get("issues") or not projection.get("ready",False): raise ValueError("UNSAFE_PRODUCT_PROJECTION")
    payload=dict(projection.get("structured_fields",{}))
    defaults={"price":None,"price_visible":False,"is_featured":False,"is_published":False}
    for field,safe_value in defaults.items():
        if field in payload and payload[field]!=safe_value: raise ValueError("UNSAFE_COMMERCIAL_OVERRIDE:"+field)
        payload[field]=safe_value
    evidence=[{"target_field":field,"value":value,"transformation":"import_safety_default","rule_version":"jem-import-safety-v1","provenance":"import_policy"} for field,value in defaults.items()]
    return {"payload":payload,"safety_evidence":evidence,"rule_version":"jem-import-safety-v1"}
