"""Deterministic orchestration for extraction from immutable local snapshots."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit

from .extraction_adapters import FixtureHtmlExtractionAdapter
from .paths import safe_join
from .serialization import canonical_bytes
from .storage import atomic_write, verify_hash

ENGINE_VERSION="catalog-extraction-v1"; SCHEMA_VERSION="1.0.0"; IDENTITY_STRATEGY="source-identity-v1"
OUTPUTS=("raw-products.jsonl","raw-field-observations.jsonl","raw-tables.jsonl",
         "media-candidates.jsonl","document-candidates.jsonl","extraction-review.jsonl")

class ExtractionInputError(ValueError): pass
class ExtractionBlockedError(ExtractionInputError): pass
class ExtractionIncompatibleError(ExtractionInputError): pass

def _read_json(path):
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise ExtractionInputError(f"invalid local JSON: {path.name}") from exc
    if not isinstance(value,dict): raise ExtractionInputError("manifest must be an object")
    return value
def _jsonl(path):
    try: lines=path.read_bytes().splitlines()
    except OSError as exc: raise ExtractionInputError(f"missing artifact: {path.name}") from exc
    result=[]
    for number,line in enumerate(lines,1):
        try: item=json.loads(line.decode("utf-8",errors="strict"))
        except (UnicodeError,json.JSONDecodeError) as exc: raise ExtractionInputError(f"invalid JSONL line {number}") from exc
        if not isinstance(item,dict): raise ExtractionInputError("JSONL rows must be objects")
        result.append(item)
    return result
def _digest(value): return sha256(canonical_bytes(value)).hexdigest()
def _stable_id(kind,*parts): return f"{kind}:sha256:"+sha256("\0".join(str(x) for x in parts).encode("utf-8")).hexdigest()

def _validate_fingerprint(manifest):
    field="content_fingerprint" if "content_fingerprint" in manifest else "semantic_fingerprint"
    claimed=manifest.get(field); semantic=dict(manifest); semantic.pop(field,None); semantic.pop("generated_at",None)
    if not isinstance(claimed,str) or len(claimed)!=64 or _digest(semantic)!=claimed:
        raise ExtractionBlockedError(f"invalid {field}")

def validate_inputs(snapshot_manifest_path:Path,snapshot_root:Path,matching_manifest_path:Path):
    snapshots=_read_json(snapshot_manifest_path); matching=_read_json(matching_manifest_path)
    if snapshots.get("schema_version")!="snapshot-manifest-v1": raise ExtractionIncompatibleError("unsupported snapshot manifest")
    if matching.get("schema_version")!="1.0.0": raise ExtractionIncompatibleError("unsupported matching manifest")
    _validate_fingerprint(snapshots); _validate_fingerprint(matching)
    rows=snapshots.get("snapshots")
    if not isinstance(rows,list) or not rows: raise ExtractionBlockedError("snapshot manifest is empty")
    required={"source","source_role","source_identity_value","requested_url","canonical_url","relative_path","sha256","size","content_type","encoding","adapter_version"}
    seen_ids=set(); seen_refs=set(); validated=[]
    allowed_sources={(x.get("source"),x.get("role"),x.get("adapter_version")) for x in matching.get("sources",[])}
    known_sources=set(matching.get("source_mappings",{}))|set(matching.get("supplemental_entry_mappings",{}))
    for row in sorted(rows,key=lambda x:(x.get("source_identity_value",""),x.get("relative_path",""))):
        if not required<=row.keys(): raise ExtractionBlockedError("incomplete snapshot metadata")
        identity=row["source_identity_value"]; reference=row["relative_path"]
        if identity in seen_ids or reference in seen_refs: raise ExtractionBlockedError("duplicate snapshot identity or reference")
        seen_ids.add(identity); seen_refs.add(reference)
        if not identity.startswith(row["source"]+":"): raise ExtractionBlockedError("source identity namespace mismatch")
        parsed_url=urlsplit(row["canonical_url"])
        if parsed_url.scheme not in {"http","https"} or not parsed_url.hostname or parsed_url.fragment:
            raise ExtractionBlockedError("invalid canonical URL metadata")
        if identity not in known_sources: raise ExtractionBlockedError("snapshot references unknown source identity")
        if (row["source"],row["source_role"],row["adapter_version"]) not in allowed_sources: raise ExtractionIncompatibleError("source role or adapter mismatch")
        if row["content_type"].split(";",1)[0].lower() not in {"text/html","application/xhtml+xml"}: raise ExtractionIncompatibleError("snapshot MIME is not passive HTML")
        if not row["encoding"]: raise ExtractionBlockedError("snapshot encoding is required")
        target=safe_join(snapshot_root,reference)
        try: body=target.read_bytes()
        except OSError as exc: raise ExtractionBlockedError("missing snapshot") from exc
        if len(body)!=row["size"]: raise ExtractionBlockedError("snapshot size mismatch")
        verify_hash(body,row["sha256"]); validated.append((row,body))
    return snapshots,matching,validated

def _provenance(row,matching):
    sid=row["source_identity_value"]; entry=matching.get("supplemental_entry_mappings",{}).get(sid)
    if row["source_role"]=="authoritative_existence": entry="discovered:"+sid
    association=_stable_id("supplemental-association",sid) if row["source_role"]=="supplemental" else None
    return {"source_namespace":row["source"],"source_role":row["source_role"],"source_identity_value":sid,
      "discovered_entry_id":entry,"supplemental_association_id":association,"canonical_identity_value":matching.get("source_mappings",{}).get(sid),
      "original_url":row["requested_url"],"canonical_url":row["canonical_url"],"snapshot_reference":row["relative_path"],
      "snapshot_sha256":row["sha256"],"content_type":row["content_type"],"encoding":row["encoding"],"adapter_id":"generic-passive-html","adapter_version":"1.0.0"}

def plan(snapshot_manifest_path,matching_manifest_path):
    snapshots=_read_json(snapshot_manifest_path); matching=_read_json(matching_manifest_path)
    return {"status":"blocked_live" if not snapshots.get("synthetic",False) else "ready_synthetic","snapshots":len(snapshots.get("snapshots",[])),
            "snapshot_manifest_sha256":sha256(snapshot_manifest_path.read_bytes()).hexdigest(),"matching_fingerprint":matching.get("semantic_fingerprint"),
            "network_requests":0,"writes":0}

def extract(snapshot_manifest_path:Path,snapshot_root:Path,matching_manifest_path:Path,output_dir:Path,*,generated_at=None):
    snapshots,matching,validated=validate_inputs(snapshot_manifest_path,snapshot_root,matching_manifest_path)
    if not snapshots.get("synthetic",False): raise ExtractionBlockedError("live extraction blocked: no approved structural evidence")
    adapter=FixtureHtmlExtractionAdapter(); collections={name:[] for name in OUTPUTS}; snapshot_hashes=[]
    for row,body in validated:
        provenance=_provenance(row,matching); parsed=adapter.parse(body,row|{"approved_hosts":snapshots.get("approved_hosts",[])})
        product_id=_stable_id("raw-page",provenance["source_identity_value"],row["sha256"],parsed["page_type"])
        collections[OUTPUTS[0]].append({"schema_version":SCHEMA_VERSION,"raw_product_id":product_id,"evidence_kind":"synthetic",
          **provenance,"page_type":parsed["page_type"],"classification_rule_id":parsed["classification_rule_id"],"classification_rule_version":parsed["classification_rule_version"],
          "model_scopes":sorted({f["scope"]["value"] for f in parsed["fields"] if f["scope"]["value"]}),"json_ld":parsed["json_ld"],"resolution_status":"unresolved"})
        for index,field in enumerate(parsed["fields"]):
            oid=_stable_id("observation",provenance["source_identity_value"],row["sha256"],field["locator"],field["source_field_raw"],field["raw_value"],index)
            excluded=field["source_field_raw"].casefold() in {"precio","price","stock","availability","disponibilidad"}
            hint="ProductSpec" if "altura" in field["source_field_raw"].casefold() else field["semantic_hint"]
            collections[OUTPUTS[1]].append({"schema_version":SCHEMA_VERSION,"observation_id":oid,"raw_product_id":product_id,**provenance,
              "source_field_raw":field["source_field_raw"],"raw_value":field["raw_value"],"raw_unit":field["raw_unit"],"visible_value":None,"transformations":[],
              "locator":field["locator"],"page_type":parsed["page_type"],"scope":field["scope"],"semantic_hint":hint,"extraction_rule_id":"fixture-raw-fields",
              "extraction_rule_version":"1.0.0","resolution_status":"excluded_commercial" if excluded else "unresolved","blocking_reasons":["commercial_field_not_importable"] if excluded else [],"observed_at":generated_at})
        for index,table in enumerate(parsed["tables"]):
            tid=_stable_id("raw-table",provenance["source_identity_value"],row["sha256"],table["locator"],index)
            collections[OUTPUTS[2]].append({"schema_version":SCHEMA_VERSION,"raw_table_id":tid,"raw_product_id":product_id,**provenance,
              "page_type":parsed["page_type"],"caption_raw":table["caption"],"locator":table["locator"],"rows":table["rows"],"irregular":table["irregular"],
              "scope_status":"ambiguous" if table["irregular"] else "preserved","extraction_rule_id":"fixture-raw-tables","extraction_rule_version":"1.0.0"})
            for table_row in table["rows"]:
                cells=table_row["cells"]
                label=cells[0]["raw_value"] if cells else ""
                for cell_index,cell in enumerate(cells[1:],1):
                    if cell["kind"]!="value": continue
                    oid=_stable_id("observation",provenance["source_identity_value"],row["sha256"],cell["locator"],label,cell["raw_value"],cell_index)
                    scope={"kind":"model" if cell["model_scope"] else "unscoped","value":cell["model_scope"]}
                    collections[OUTPUTS[1]].append({"schema_version":SCHEMA_VERSION,"observation_id":oid,"raw_product_id":product_id,**provenance,
                      "source_field_raw":label,"raw_value":cell["raw_value"],"raw_unit":cell["raw_unit"],"visible_value":None,"transformations":[],
                      "locator":cell["locator"],"page_type":parsed["page_type"],"scope":scope,"semantic_hint":None,"extraction_rule_id":"fixture-raw-tables",
                      "extraction_rule_version":"1.0.0","resolution_status":"unresolved","blocking_reasons":["ambiguous_table_scope"] if table["irregular"] else [],"observed_at":generated_at})
        for index,item in enumerate(parsed["media"]):
            collections[OUTPUTS[3]].append({"schema_version":SCHEMA_VERSION,"media_candidate_id":_stable_id("media",provenance["source_identity_value"],row["sha256"],item["locator"],item["candidate_url"],index),**provenance,**item,"extraction_rule_id":"fixture-linked-assets","extraction_rule_version":"1.0.0"})
        for index,item in enumerate(parsed["documents"]):
            collections[OUTPUTS[4]].append({"schema_version":SCHEMA_VERSION,"document_candidate_id":_stable_id("document",provenance["source_identity_value"],row["sha256"],item["locator"],item["candidate_url"],index),**provenance,**item,"extraction_rule_id":"fixture-linked-assets","extraction_rule_version":"1.0.0"})
        for index,item in enumerate(parsed["issues"]):
            collections[OUTPUTS[5]].append({"schema_version":SCHEMA_VERSION,"review_id":_stable_id("extraction-review",provenance["source_identity_value"],row["sha256"],item["code"],item["locator"],index),**provenance,**item})
        snapshot_hashes.append(row["sha256"])
    for name in collections: collections[name].sort(key=canonical_bytes)
    output_bytes={name:b"".join(canonical_bytes(x) for x in rows) for name,rows in collections.items()}
    semantic={"schema_version":SCHEMA_VERSION,"rules_version":adapter.rules_version,"engine_version":ENGINE_VERSION,"evidence_kind":"synthetic",
      "identity_strategy":IDENTITY_STRATEGY,"matching_fingerprint":matching["semantic_fingerprint"],"adapters":[{"id":adapter.adapter_id,"version":adapter.adapter_version,"structure_verified":False}],
      "rules":list(adapter.rules),"input_hashes":{"snapshot_manifest":sha256(snapshot_manifest_path.read_bytes()).hexdigest(),"matching_manifest":sha256(matching_manifest_path.read_bytes()).hexdigest()},
      "snapshot_hashes":sorted(snapshot_hashes),"output_hashes":{k:sha256(v).hexdigest() for k,v in sorted(output_bytes.items())},
      "sources":matching["sources"],"counts":{k.removesuffix(".jsonl"):len(v) for k,v in sorted(collections.items())},
      "structure_hash":sha256(output_bytes["raw-tables.jsonl"]).hexdigest(),"status":"synthetic",
      "blocking_reasons":["fixture_evidence_not_live","live_structure_unverified"],"artifacts":list(OUTPUTS)+["extraction-report.txt"]}
    semantic["semantic_fingerprint"]=_digest(semantic); manifest=semantic|{"generated_at":generated_at}
    report=("Offline catalog extraction\nstatus: synthetic\nnetwork_requests: 0\nstructure_verified: false\n"+
            "live_sources: blocked\nunits_normalized: 0\njem_fields_mapped: 0\nproducts_created: 0\n")
    parent=output_dir.parent.resolve(); parent.mkdir(parents=True,exist_ok=True); staging=Path(tempfile.mkdtemp(prefix=".catalog-extract-",dir=parent))
    try:
        for name,data in output_bytes.items(): atomic_write(staging/name,data)
        atomic_write(staging/"extraction-manifest.json",canonical_bytes(manifest)); atomic_write(staging/"extraction-report.txt",report.encode("utf-8"))
        if output_dir.exists(): raise ExtractionInputError("output directory already exists")
        staging.replace(output_dir)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return manifest

def compare_manifests(old,new):
    compatibility=("schema_version","rules_version","identity_strategy","matching_fingerprint")
    if any(old.get(k)!=new.get(k) for k in compatibility) or old.get("adapters")!=new.get("adapters"):
        return {"schema_version":SCHEMA_VERSION,"status":"comparison_blocked","classifications":["comparison_blocked","source_structure_changed"],"differences":[]}
    differences=[]; old_counts=old.get("counts",{}); new_counts=new.get("counts",{})
    observation="raw-field-observations.jsonl"; old_n=old_counts.get("raw-field-observations",0); new_n=new_counts.get("raw-field-observations",0)
    if old.get("output_hashes",{}).get(observation)==new.get("output_hashes",{}).get(observation):
        differences.append({"artifact":observation,"classification":"unchanged"})
    else:
        differences.append({"artifact":observation,"classification":"new_observation"})
        differences.append({"artifact":observation,"classification":"field_added" if new_n>old_n else "field_not_observed" if new_n<old_n else "value_changed"})
    for artifact,added in (("media-candidates.jsonl","media_candidate_added"),("document-candidates.jsonl","document_candidate_added")):
        classification="unchanged" if old.get("output_hashes",{}).get(artifact)==new.get("output_hashes",{}).get(artifact) else added
        differences.append({"artifact":artifact,"classification":classification})
    if old.get("structure_hash")!=new.get("structure_hash"):
        differences.append({"artifact":"raw-tables.jsonl","classification":"source_structure_changed"})
    return {"schema_version":SCHEMA_VERSION,"status":"complete","classifications":sorted({x["classification"] for x in differences}),"differences":differences,
      "absence_semantics":"field_not_observed; never confirmed deletion"}
