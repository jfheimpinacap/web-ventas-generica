"""Bounded, offline binary asset validation and content-addressed publication."""
from __future__ import annotations

import binascii
from hashlib import sha256
import json
from pathlib import Path
import re
import struct

from .errors import HashMismatchError
from .paths import safe_join
from .schema_validation import validate as validate_schema
from .serialization import canonical_bytes
from .storage import atomic_write, verify_hash, write_once

SCHEMA_VERSION = "1.0.0"
RULES_VERSION = "asset-validation-v1"
VALIDATOR_VERSION = "bounded-container-1.0.0"
OUTPUTS = ("asset-records.jsonl", "asset-relations.jsonl", "asset-reviews.jsonl")
MIMES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf"}
EXTENSIONS = {"jpeg": "jpg", "png": "png", "webp": "webp", "pdf": "pdf"}
ACTIVE_PDF = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/OpenAction", b"/AA")

class AssetInputError(ValueError): pass
class AssetIncompatibleError(AssetInputError): pass
class AssetBlockedError(AssetInputError): pass

def _id(kind: str, *parts: object) -> str:
    return f"{kind}:sha256:{sha256(chr(0).join(map(str, parts)).encode('utf-8')).hexdigest()}"

def _read_json(path: Path) -> dict[str, object]:
    try: value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc: raise AssetInputError(f"invalid local JSON: {path.name}") from exc
    if not isinstance(value, dict): raise AssetInputError("manifest must be an object")
    return value

def _jsonl(path: Path) -> list[dict[str, object]]:
    try: lines = path.read_bytes().splitlines()
    except OSError as exc: raise AssetInputError(f"missing local input: {path.name}") from exc
    rows = []
    for number, line in enumerate(lines, 1):
        try: row = json.loads(line.decode("utf-8", errors="strict"))
        except (UnicodeError, json.JSONDecodeError) as exc: raise AssetInputError(f"invalid JSONL line {number}: {path.name}") from exc
        if not isinstance(row, dict): raise AssetInputError("JSONL rows must be objects")
        rows.append(row)
    return rows

def _dimensions(width: int, height: int, limits: dict[str, int]) -> list[str]:
    risks = []
    if width <= 0 or height <= 0: risks.append("invalid_dimensions")
    if width > limits["max_width"] or height > limits["max_height"] or width * height > limits["max_pixels"]: risks.append("dimension_limit_exceeded")
    return risks

def _jpeg(data: bytes, limits: dict[str, int]) -> tuple[str, dict[str, int] | None, list[str]]:
    if not data.startswith(b"\xff\xd8"): return "invalid", None, ["signature_mismatch"]
    position, dims, risks, saw_eoi = 2, None, [], False
    while position < len(data):
        if data[position] != 0xff: position += 1; continue
        while position < len(data) and data[position] == 0xff: position += 1
        if position >= len(data): break
        marker = data[position]; position += 1
        if marker == 0xd9: saw_eoi = True; break
        if marker in {0x01, *range(0xd0, 0xd8)}: continue
        if position + 2 > len(data): risks.append("truncated_container"); break
        length = int.from_bytes(data[position:position+2], "big")
        if length < 2 or position + length > len(data): risks.append("truncated_container"); break
        if marker in {0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf}:
            if length < 7: risks.append("invalid_sof")
            else:
                height = int.from_bytes(data[position+3:position+5], "big"); width = int.from_bytes(data[position+5:position+7], "big")
                dims = {"width": width, "height": height}; risks.extend(_dimensions(width, height, limits))
        position += length
    if not saw_eoi: risks.append("missing_eoi")
    if dims is None: risks.append("missing_dimensions")
    return ("invalid" if risks else "valid_container"), dims, sorted(set(risks))

def _png(data: bytes, limits: dict[str, int]) -> tuple[str, dict[str, int] | None, list[str]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"): return "invalid", None, ["signature_mismatch"]
    position, dims, risks, first, ended = 8, None, [], True, False
    while position < len(data):
        if position + 12 > len(data): risks.append("truncated_container"); break
        length = int.from_bytes(data[position:position+4], "big"); kind=data[position+4:position+8]; end=position+12+length
        if end > len(data): risks.append("truncated_container"); break
        payload=data[position+8:position+8+length]; expected=int.from_bytes(data[position+8+length:end],"big")
        if binascii.crc32(kind+payload) & 0xffffffff != expected: risks.append("crc_mismatch")
        if first:
            if kind != b"IHDR" or length != 13: risks.append("invalid_ihdr")
            else:
                width,height=struct.unpack(">II",payload[:8]); dims={"width":width,"height":height}; risks.extend(_dimensions(width,height,limits))
            first=False
        if kind == b"IEND":
            if length: risks.append("invalid_iend")
            ended=True
            if end != len(data): risks.append("trailing_data")
            break
        position=end
    if not ended: risks.append("missing_iend")
    return ("invalid" if risks else "valid_container"), dims, sorted(set(risks))

def _webp(data: bytes, limits: dict[str, int]) -> tuple[str, dict[str, int] | None, list[str]]:
    if len(data)<12 or data[:4]!=b"RIFF" or data[8:12]!=b"WEBP": return "invalid",None,["signature_mismatch"]
    risks=[]; declared=int.from_bytes(data[4:8],"little")+8
    if declared != len(data): risks.append("truncated_container" if declared>len(data) else "trailing_data")
    position,dims,variant=12,None,None
    while position+8<=len(data):
        kind=data[position:position+4]; length=int.from_bytes(data[position+4:position+8],"little"); end=position+8+length
        if end>len(data): risks.append("truncated_container"); break
        payload=data[position+8:end]
        if variant is None and kind in {b"VP8 ",b"VP8L",b"VP8X"}:
            variant=kind
            if kind==b"VP8X" and length>=10: width=1+int.from_bytes(payload[4:7],"little"); height=1+int.from_bytes(payload[7:10],"little")
            elif kind==b"VP8L" and length>=5 and payload[0]==0x2f:
                bits=int.from_bytes(payload[1:5],"little"); width=(bits&0x3fff)+1; height=((bits>>14)&0x3fff)+1
            elif kind==b"VP8 " and length>=10 and payload[3:6]==b"\x9d\x01\x2a": width=int.from_bytes(payload[6:8],"little")&0x3fff; height=int.from_bytes(payload[8:10],"little")&0x3fff
            else: risks.append("missing_dimensions"); width=height=0
            if width and height: dims={"width":width,"height":height}; risks.extend(_dimensions(width,height,limits))
        position=end+(length&1)
    if variant is None: risks.append("unsupported_webp_variant")
    return ("invalid" if risks else "valid_container"),dims,sorted(set(risks))

def _pdf(data: bytes) -> tuple[str, None, list[str]]:
    if not data.startswith(b"%PDF-"): return "invalid",None,["signature_mismatch"]
    risks=[]
    if not re.match(br"%PDF-[12]\.[0-9]",data[:12]): risks.append("unsupported_pdf_version")
    tail=data[-2048:]
    if b"%%EOF" not in tail: risks.append("missing_eof")
    matches=list(re.finditer(br"startxref\s+(\d+)",tail))
    if not matches: risks.append("missing_startxref")
    elif int(matches[-1].group(1)) >= len(data): risks.append("invalid_startxref")
    encrypted=b"/Encrypt" in data
    active=[token[1:].decode("ascii") for token in ACTIVE_PDF if token in data]
    if encrypted: risks.append("encrypted")
    risks.extend("active_"+x for x in active)
    if any(x in risks for x in ("missing_eof","missing_startxref","invalid_startxref","unsupported_pdf_version")): status="invalid"
    elif encrypted: status="encrypted_review_required"
    elif active: status="active_content_review_required"
    else: status="valid_container"
    return status,None,sorted(set(risks))

def validate_binary(data: bytes, asset_class: str, declared_mime: str | None, filename: str, limits: dict[str,int]) -> dict[str, object]:
    risks=[]
    if not data: return {"format":"unknown","mime_detected":"application/octet-stream","canonical_extension":None,"status":"invalid","level":"signature_only","dimensions":None,"encrypted":None,"risks":["empty_file"]}
    if len(data)>limits["max_bytes"]: risks.append("size_limit_exceeded")
    if data.startswith(b"\xff\xd8"): fmt="jpeg"; status,dims,found=_jpeg(data,limits)
    elif data.startswith(b"\x89PNG\r\n\x1a\n"): fmt="png"; status,dims,found=_png(data,limits)
    elif data.startswith(b"RIFF") and data[8:12]==b"WEBP": fmt="webp"; status,dims,found=_webp(data,limits)
    elif data.startswith(b"%PDF-"): fmt="pdf"; status,dims,found=_pdf(data)
    elif data.lstrip().startswith(b"<svg"): fmt="svg"; status,dims,found="unsupported",None,["active_vector_unsupported"]
    else: fmt="unknown"; status,dims,found="unsupported",None,["unknown_signature"]
    risks.extend(found); mime=MIMES.get(fmt,"application/octet-stream")
    if (asset_class=="image" and fmt not in {"jpeg","png","webp","svg"}) or (asset_class=="document" and fmt!="pdf"): risks.append("class_signature_mismatch"); status="invalid"
    if declared_mime and declared_mime.split(";",1)[0].strip().lower()!=mime: risks.append("mime_signature_mismatch")
    apparent=Path(filename).suffix.lower().lstrip(".")
    if apparent and apparent not in ({"jpg","jpeg"} if fmt=="jpeg" else {EXTENSIONS.get(fmt,"-")}): risks.append("extension_signature_mismatch")
    if risks and status=="valid_container": status="manual_review_required"
    if "size_limit_exceeded" in risks: status="invalid"
    return {"format":fmt,"mime_detected":mime,"canonical_extension":EXTENSIONS.get(fmt),"status":status,"level":"bounded_container_structure","dimensions":dims,"encrypted":(b"/Encrypt" in data) if fmt=="pdf" else None,"risks":sorted(set(risks))}

def _load_inputs(extraction_dir:Path,payload_manifest_path:Path):
    extraction=_read_json(extraction_dir/"extraction-manifest.json"); payloads=_read_json(payload_manifest_path)
    schema_root=Path(__file__).parents[1]/"schemas"/"v1"
    validate_schema(payloads,schema_root/"payload-manifest.schema.json")
    if extraction.get("schema_version")!=SCHEMA_VERSION or payloads.get("schema_version")!=SCHEMA_VERSION: raise AssetIncompatibleError("unsupported input version")
    fingerprint=extraction.get("semantic_fingerprint"); semantic=dict(extraction); semantic.pop("semantic_fingerprint",None); semantic.pop("generated_at",None)
    if not isinstance(fingerprint,str) or sha256(canonical_bytes(semantic)).hexdigest()!=fingerprint: raise AssetBlockedError("invalid extraction semantic fingerprint")
    candidates={}
    for asset_class,name,key in (("image","media-candidates.jsonl","media_candidate_id"),("document","document-candidates.jsonl","document_candidate_id")):
        raw=(extraction_dir/name).read_bytes(); claimed=extraction.get("output_hashes",{}).get(name)
        if claimed: verify_hash(raw,claimed)
        for row in _jsonl(extraction_dir/name):
            cid=row.get(key)
            if not isinstance(cid,str) or cid in candidates: raise AssetBlockedError("invalid or duplicate candidate ID")
            candidates[cid]=(asset_class,row)
    bindings=payloads.get("bindings")
    if not isinstance(bindings,list): raise AssetBlockedError("payload bindings must be an array")
    candidate_ids=[binding.get("candidate_id") for binding in bindings]
    if len(candidate_ids)!=len(set(candidate_ids)): raise AssetBlockedError("candidate has multiple payload bindings")
    return extraction,payloads,candidates,sorted(bindings,key=canonical_bytes)

def plan(extraction_dir:Path,payload_manifest_path:Path) -> dict[str,object]:
    _,_,candidates,bindings=_load_inputs(extraction_dir,payload_manifest_path); ids=[x.get("candidate_id") for x in bindings]
    return {"schema_version":SCHEMA_VERSION,"status":"offline_plan","candidates":len(candidates),"payloads":len(bindings),"missing_payloads":len(set(candidates)-set(ids)),"orphan_payloads":len(set(ids)-set(candidates)),"network_requests":0,"downloads":0,"writes":0}

def validate(extraction_dir:Path,payload_manifest_path:Path,payload_root:Path,output_root:Path,*,operated_at=None,limits=None):
    limits=limits or {"max_bytes":25_000_000,"max_width":20000,"max_height":20000,"max_pixels":100_000_000}
    extraction,payload_manifest,candidates,bindings=_load_inputs(extraction_dir,payload_manifest_path)
    records_by_hash={}; object_bytes={}; relations=[]; reviews=[]; bound=set(); duplicates=0
    for binding in bindings:
        cid=binding.get("candidate_id")
        if cid not in candidates:
            reviews.append(_review("orphan_payload","error",cid,None,None,"payload has no candidate",binding.get("relative_path"))); continue
        asset_class,candidate=candidates[cid]; bound.add(cid); relative=binding.get("relative_path")
        if not isinstance(relative,str): raise AssetBlockedError("payload path must be relative text")
        source=safe_join(payload_root,relative)
        try: data=source.read_bytes()
        except OSError as exc: raise AssetBlockedError("payload missing") from exc
        if len(data)!=binding.get("expected_size"): raise AssetBlockedError("payload size mismatch")
        expected=binding.get("expected_sha256")
        if not isinstance(expected,str) or not re.fullmatch(r"[0-9a-f]{64}",expected): raise AssetBlockedError("invalid expected SHA-256")
        verify_hash(data,expected); assessment=validate_binary(data,asset_class,binding.get("declared_mime"),source.name,limits)
        object_id="asset:sha256:"+expected; object_path=f"_pipeline/cache/sha256/{expected[:2]}/{expected[2:4]}/{expected}"
        relation_id=_id("asset-relation",cid,object_id,candidate.get("locator"),candidate.get("source_namespace"))
        authorization=binding.get("authorization_status","unknown")
        provenance=binding.get("provenance_type")
        if authorization=="authorized_with_evidence" and (provenance!="authorized_capture_receipt" or not binding.get("audit_reference")):
            raise AssetBlockedError("authorization requires an auditable capture receipt")
        identity=candidate.get("canonical_identity_value")
        association="ambiguous" if isinstance(identity,list) else "unambiguous" if isinstance(identity,str) and identity else "pending_identity"
        eligibility=_eligibility(assessment,candidate,provenance,authorization,association)
        relation={"schema_version":SCHEMA_VERSION,"relation_id":relation_id,"candidate_id":cid,"object_id":object_id,"source_namespace":candidate.get("source_namespace","unknown"),"source_role":candidate.get("source_role","unknown"),"source_entry_id":candidate.get("discovered_entry_id"),"association_id":candidate.get("supplemental_association_id"),"canonical_identity":identity if isinstance(identity,str) else None,"source_url":candidate.get("original_url"),"resolved_candidate_url":candidate.get("resolved_url",candidate.get("candidate_url")),"referrer":candidate.get("canonical_url"),"locator":candidate.get("locator"),"source_attribute":candidate.get("source_attribute",candidate.get("relationship")),"scope_status":candidate.get("scope_status","candidate"),"authorization_status":authorization,"provisional_classification":candidate.get("relationship"),"language_hint":candidate.get("language"),"revision_hint":candidate.get("revision"),"association_status":association,"eligibility_status":eligibility,"blocking_reasons":sorted(set(assessment["risks"]+_relation_blocks(candidate,provenance,authorization,association)))}
        relations.append(relation)
        if expected in records_by_hash: duplicates+=1
        else:
            records_by_hash[expected]={"schema_version":SCHEMA_VERSION,"object_id":object_id,"sha256":expected,"size":len(data),"asset_class":asset_class,"detected_format":assessment["format"],"declared_mime":binding.get("declared_mime"),"detected_mime":assessment["mime_detected"],"source_filename":source.name,"apparent_extension":source.suffix.lower(),"canonical_extension":assessment["canonical_extension"],"validation_status":assessment["status"],"validation_level":assessment["level"],"dimensions":assessment["dimensions"],"encrypted":assessment["encrypted"],"risk_signals":assessment["risks"],"object_path":object_path,"relation_ids":[],"provenance_types":[],"operated_at":operated_at}
            object_bytes[expected]=data
        records_by_hash[expected]["relation_ids"].append(relation_id); records_by_hash[expected]["provenance_types"].append(provenance)
        for risk in relation["blocking_reasons"]: reviews.append(_review(risk,"error" if assessment["status"]=="invalid" else "warning",cid,object_id,relation_id,risk,relative))
    for cid in sorted(set(candidates)-bound): reviews.append(_review("pending_payload","info",cid,None,None,"candidate has no local payload",None))
    records=[]
    for record in records_by_hash.values(): record["relation_ids"]=sorted(set(record["relation_ids"])); record["provenance_types"]=sorted(set(record["provenance_types"])); records.append(record)
    records.sort(key=canonical_bytes); relations.sort(key=canonical_bytes); reviews.sort(key=canonical_bytes)
    blobs={OUTPUTS[0]:b"".join(canonical_bytes(x) for x in records),OUTPUTS[1]:b"".join(canonical_bytes(x) for x in relations),OUTPUTS[2]:b"".join(canonical_bytes(x) for x in reviews)}
    counts={"unique_objects":len(records),"relations":len(relations),"exact_duplicates":duplicates,"candidates_without_payload":len(set(candidates)-bound),"orphan_payloads":sum(x["code"]=="orphan_payload" for x in reviews),"invalid":sum(x["validation_status"]=="invalid" for x in records),"pending_review":sum(x["severity"] in {"warning","error"} for x in reviews),"eligible":sum(x["eligibility_status"]=="eligible_for_future_selection" for x in relations),"blocked":sum(x["eligibility_status"]!="eligible_for_future_selection" for x in relations)}
    report=("Offline asset validation\n"+"\n".join(f"{k}: {v}" for k,v in sorted(counts.items()))+"\noffline: true\ndownloads: 0\nselection_performed: false\nmaterialization_performed: false\n").encode("utf-8")
    semantic={"schema_version":SCHEMA_VERSION,"rules_version":RULES_VERSION,"validator_version":VALIDATOR_VERSION,"input_versions":{"extraction":extraction["schema_version"],"payloads":payload_manifest["schema_version"]},"input_hashes":{"extraction_manifest":sha256((extraction_dir/"extraction-manifest.json").read_bytes()).hexdigest(),"media_candidates":sha256((extraction_dir/"media-candidates.jsonl").read_bytes()).hexdigest(),"document_candidates":sha256((extraction_dir/"document-candidates.jsonl").read_bytes()).hexdigest(),"payload_manifest":sha256(payload_manifest_path.read_bytes()).hexdigest()},"configuration_fingerprint":sha256(canonical_bytes({"schema_version":SCHEMA_VERSION,"rules_version":RULES_VERSION,"limits":limits})).hexdigest(),"output_hashes":{**{k:sha256(v).hexdigest() for k,v in sorted(blobs.items())},"asset-report.txt":sha256(report).hexdigest()},"counts":counts,"offline":True,"downloads":0}
    semantic["semantic_fingerprint"]=sha256(canonical_bytes(semantic)).hexdigest(); manifest=semantic|{"operated_at":operated_at}
    for expected,data in sorted(object_bytes.items()): write_once(safe_join(output_root,records_by_hash[expected]["object_path"]),data,expected)
    for name,data in blobs.items(): atomic_write(output_root/name,data)
    atomic_write(output_root/"asset-manifest.json",canonical_bytes(manifest)); atomic_write(output_root/"asset-report.txt",report)
    return manifest

def _relation_blocks(candidate,provenance,authorization,association):
    blocks=[]
    if candidate.get("scope_status")!="candidate": blocks.append("scope_not_approved")
    if provenance=="synthetic_fixture": blocks.append("synthetic_not_live_evidence")
    if provenance=="unverified_local_payload": blocks.append("payload_unverified")
    if authorization!="authorized_with_evidence": blocks.append("authorization_pending")
    if association!="unambiguous": blocks.append("identity_pending")
    return blocks

def _eligibility(assessment,candidate,provenance,authorization,association):
    if assessment["status"] in {"invalid","unsupported"}: return "ineligible"
    if provenance=="synthetic_fixture": return "synthetic_only"
    if candidate.get("scope_status")!="candidate" or assessment["status"]!="valid_container": return "manual_review_required"
    if association!="unambiguous": return "pending_identity"
    if authorization!="authorized_with_evidence" or provenance=="unverified_local_payload": return "pending_authorization"
    return "eligible_for_future_selection"

def _review(code,severity,candidate_id,object_id,relation_id,reason,locator):
    return {"schema_version":SCHEMA_VERSION,"review_id":_id("asset-review",code,candidate_id,object_id,relation_id,locator),"code":code,"severity":severity,"object_id":object_id,"candidate_id":candidate_id,"relation_id":relation_id,"reason":reason,"evidence":{"offline":True},"locator":locator,"status":"pending","rule_id":code,"rule_version":RULES_VERSION}

def verify(output_root:Path) -> dict[str,object]:
    manifest=_read_json(output_root/"asset-manifest.json"); problems=[]
    if manifest.get("schema_version")!=SCHEMA_VERSION: raise AssetIncompatibleError("unsupported asset manifest")
    for name,expected in manifest.get("output_hashes",{}).items():
        target=safe_join(output_root,name)
        try: verify_hash(target.read_bytes(),expected)
        except (OSError,HashMismatchError): problems.append("altered_output:"+name)
    records=_jsonl(output_root/"asset-records.jsonl"); relations=_jsonl(output_root/"asset-relations.jsonl"); relation_ids={x.get("relation_id") for x in relations}
    for record in records:
        try:
            data=safe_join(output_root,record["object_path"]).read_bytes(); verify_hash(data,record["sha256"])
            if len(data)!=record["size"]: problems.append("object_size:"+record["object_id"])
        except (OSError,HashMismatchError,KeyError): problems.append("object_missing_or_altered:"+str(record.get("object_id")))
        if not set(record.get("relation_ids",[]))<=relation_ids: problems.append("invalid_relation_reference:"+str(record.get("object_id")))
    object_ids={x.get("object_id") for x in records}
    for relation in relations:
        if relation.get("object_id") not in object_ids: problems.append("orphan_relation:"+str(relation.get("relation_id")))
    return {"schema_version":SCHEMA_VERSION,"status":"verified" if not problems else "blocked","problems":sorted(problems),"offline":True,"downloads":0,"writes":0}
