"""Versioned, fail-closed normalized audit document to JEM projection adapter."""
from __future__ import annotations

from hashlib import sha256
from decimal import Decimal, InvalidOperation
from copy import deepcopy
import re

from catalog_pipeline_common.serialization import canonical_bytes

ADAPTER_VERSION = "normalized-to-jem-v1"
DOCUMENT_VERSION = "1.0.0"
FIELD_MAP = {
    "WorkingHeightM": ("working_height_m", "decimal", "m"),
    "MaximumLoadCapacityKg": ("maximum_load_capacity_kg", "decimal", "kg"),
    "MachineWeightKg": ("machine_weight_kg", "decimal", "kg"),
    "PowerSource": ("power_source", "enum", None),
    "TerrainType": ("terrain_type", "enum", None),
    "Year": ("year", "integer", None),
    "HoursMeter": ("hours_meter", "decimal", "h"),
}
ENUMS={"PowerSource":{"diesel","electric_24v","electric_lithium"},
       "TerrainType":{"indoor_smooth","outdoor","outdoor_slopes_and_ramps"}}
PROJECTABLE={"exact","normalized","derived_by_approved_rule","manual_approved"}
IDENTITY=re.compile(r"^canonical-identity-v1:sha256:[0-9a-f]{64}$")

class NormalizedProjectionError(ValueError):
    pass

def _decimal(value, integer=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise NormalizedProjectionError("TYPE_INCOMPATIBLE")
    try: number=Decimal(str(value))
    except InvalidOperation as exc: raise NormalizedProjectionError("TYPE_INCOMPATIBLE") from exc
    if not number.is_finite() or (integer and number != number.to_integral_value()):
        raise NormalizedProjectionError("TYPE_INCOMPATIBLE")
    rendered=format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered

def adapt_normalized_product(document):
    """Validate and project one immutable producer document, retaining evidence."""
    source=deepcopy(document)
    if source.get("document_kind") != "normalized_for_audit_not_api_payload": raise NormalizedProjectionError("DOCUMENT_KIND_INCOMPATIBLE")
    if source.get("schema_version") != DOCUMENT_VERSION: raise NormalizedProjectionError("DOCUMENT_VERSION_INCOMPATIBLE")
    identity=source.get("canonical_identity")
    if not isinstance(identity,str) or not IDENTITY.fullmatch(identity): raise NormalizedProjectionError("IDENTITY_CONTRADICTORY")
    observations=source.get("observations")
    if not isinstance(observations,list): raise NormalizedProjectionError("OBSERVATIONS_MISSING")
    by_id={}
    for observation in observations:
        reference=observation.get("observation_id")
        if not reference or reference in by_id: raise NormalizedProjectionError("OBSERVATION_AMBIGUOUS")
        if observation.get("canonical_identity") != identity: raise NormalizedProjectionError("IDENTITY_CONTRADICTORY")
        by_id[reference]=observation
    if source.get("reviews"): raise NormalizedProjectionError("BLOCKING_REVIEW")
    structured={"name":source.get("canonical_model"),"model":source.get("canonical_model"),"slug":identity}
    evidence=[]
    for normalized_name,wrapper in sorted(source.get("structured_fields",{}).items()):
        if normalized_name not in FIELD_MAP: raise NormalizedProjectionError("UNDECLARED_FIELD_ALIAS")
        if not isinstance(wrapper,dict) or "value" not in wrapper: raise NormalizedProjectionError("VALUE_MISSING")
        if wrapper.get("status") not in PROJECTABLE: raise NormalizedProjectionError("STATUS_NOT_PROJECTABLE")
        reference=wrapper.get("observation_reference")
        observation=by_id.get(reference)
        if observation is None: raise NormalizedProjectionError("OBSERVATION_ORPHAN")
        if observation.get("conflict_group") is not None: raise NormalizedProjectionError("OPEN_CONFLICT")
        if observation.get("review_references"): raise NormalizedProjectionError("BLOCKING_REVIEW")
        target,kind,unit=FIELD_MAP[normalized_name]
        if wrapper.get("unit") != unit: raise NormalizedProjectionError("UNIT_INCOMPATIBLE")
        value=wrapper["value"]
        if value is None: structured[target]=None
        elif kind in {"decimal","integer"}: structured[target]=_decimal(value,kind=="integer")
        elif not isinstance(value,str) or value not in ENUMS[normalized_name]: raise NormalizedProjectionError("UNKNOWN_ENUM")
        else: structured[target]=value
        evidence.append({"source_field":normalized_name,"target_field":target,"value":structured[target],
                         "observation_reference":reference,"provenance":deepcopy(observation),
                         "adapter_version":ADAPTER_VERSION})
    specs=[]
    for spec in source.get("product_specs",[]):
        reference=spec.get("observation_reference")
        observation=by_id.get(reference)
        if observation is None: raise NormalizedProjectionError("OBSERVATION_ORPHAN")
        if spec.get("canonical_identity") != identity: raise NormalizedProjectionError("IDENTITY_CONTRADICTORY")
        specs.append({"key":spec["canonical_key"],"value":spec["display_value"],"unit":spec.get("display_unit") or None,"order":spec.get("order",0)})
        evidence.append({"source_field":spec["source_field_key"],"target_field":"ProductSpec.value","value":spec["display_value"],
                         "observation_reference":reference,"provenance":deepcopy(observation),"adapter_version":ADAPTER_VERSION})
    projection={"schema_version":"2.0.0","canonical_identity_value":identity,"adapter_version":ADAPTER_VERSION,
                "structured_fields":structured,"product_specs":specs,"field_evidence":evidence,"issues":[],"ready":True}
    projection["fingerprint"]=sha256(canonical_bytes(projection)).hexdigest()
    return projection
