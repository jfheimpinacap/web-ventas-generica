"""Deterministic, offline source-to-canonical identity matching.

This module deliberately imports no discovery adapter or transport.  It consumes the
bytes emitted by discovery and keeps proposed identities separate from approval.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from .identity import canonical_identity, source_identity
from .paths import safe_join
from .serialization import canonical_bytes
from .storage import atomic_write, write_once

ENGINE_VERSION = "catalog-identity-v1"
SCHEMA_VERSION = "1.0.0"
RESULTS = frozenset({"exact", "normalized_candidate", "derived_by_approved_rule",
 "manual_approval_required", "manual_approved", "ambiguous", "conflict", "missing",
 "no_match", "supplemental_orphan"})
COMPARISON_RULE = {"id": "conservative-comparison", "version": "1.0.0"}
BRAND_BINDINGS = {
 "ep": {"brand": "EP Equipment", "rule_id": "ep-brand-binding", "version": "1.0.0"},
 "gam": {"brand": "EP Equipment", "rule_id": "gam-ep-scope-brand-binding", "version": "1.0.0"},
}
OUTPUTS = ("source-identities.jsonl", "discovered-product-entries.jsonl",
 "canonical-candidates.jsonl", "identity-links.jsonl", "supplemental-associations.jsonl",
 "matching-review.jsonl")

class MatchingInputError(ValueError): pass
class MatchingBlockedError(MatchingInputError): pass
class MatchingIncompatibleError(MatchingInputError): pass

def canonical_component(raw: str | None) -> str | None:
    """NFC + exterior trim only; reject controls and empty values."""
    if raw is None: return None
    if not isinstance(raw, str): raise MatchingInputError("identity component must be text")
    value = unicodedata.normalize("NFC", raw).strip()
    if not value or any(unicodedata.category(c) == "Cc" for c in value):
        raise MatchingInputError("identity component is empty or unsafe")
    return value

def comparison_key(value: str) -> dict:
    canonical = canonical_component(value)
    normalized = re.sub(r"\s+", " ", canonical).casefold()
    normalized = "-".join(re.split("[‐‑‒–—―]", normalized))
    tokens = tuple(re.findall(r"[^\W_]+|[^\w\s]", normalized, re.UNICODE))
    return {"value": "\x1f".join(tokens), "rule_id": COMPARISON_RULE["id"],
            "rule_version": COMPARISON_RULE["version"], "changed": normalized != canonical}

def _association_component(raw: dict) -> str | None:
    """Return explicit matching evidence without turning a label into a model."""
    for field in ("model_hint", "label_hint", "label_raw"):
        try:
            value=canonical_component(raw.get(field))
        except MatchingInputError:
            value=None
        if value: return value
    return None

def _read_json(path: Path) -> dict:
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc: raise MatchingInputError(f"invalid local JSON: {path.name}") from exc
    if not isinstance(value, dict): raise MatchingInputError("manifest must be an object")
    return value

def _read_jsonl(path: Path) -> list[dict]:
    try: lines=path.read_bytes().splitlines()
    except OSError as exc: raise MatchingInputError(f"missing referenced artifact: {path.name}") from exc
    rows=[]
    for number,line in enumerate(lines,1):
        try: row=json.loads(line)
        except json.JSONDecodeError as exc: raise MatchingInputError(f"invalid JSONL line {number}") from exc
        if not isinstance(row,dict): raise MatchingInputError("candidate must be an object")
        rows.append(row)
    return rows

def _validate_discovery(path: Path) -> tuple[dict,list[dict],dict[str,str]]:
    manifest=_read_json(path)
    if manifest.get("schema_version") != "discovery-manifest-v1": raise MatchingIncompatibleError("unsupported discovery schema")
    semantic=dict(manifest); claimed=semantic.pop("content_fingerprint",None)
    if not claimed or sha256(canonical_bytes(semantic)).hexdigest()!=claimed: raise MatchingBlockedError("invalid discovery fingerprint")
    sources=manifest.get("sources"); adapters=manifest.get("adapters"); states=manifest.get("states")
    if not isinstance(sources,list) or not isinstance(adapters,dict) or not isinstance(states,dict): raise MatchingBlockedError("incomplete discovery manifest")
    if any(s not in BRAND_BINDINGS or not adapters.get(s) for s in sources): raise MatchingIncompatibleError("unsupported source or adapter")
    if any(states.get(s)!="complete" for s in sources): raise MatchingBlockedError("discovery is not complete")
    candidates_path=safe_join(path.parent,"product-candidates.jsonl")
    candidates=_read_jsonl(candidates_path)
    if manifest.get("counts",{}).get("candidates") != len(candidates): raise MatchingBlockedError("candidate count mismatch")
    required={"source","source_role","source_identity","source_key","source_url","canonical_url",
              "label_raw","model_hint","source_categories","discovery_page","evidence_reference","locator","rule_version"}
    seen=set(); source_roles={}
    for row in candidates:
        if not required <= row.keys() or row["source"] not in sources: raise MatchingBlockedError("invalid discovery candidate")
        if row["source_role"] not in {"authoritative_existence","supplemental"}: raise MatchingBlockedError("invalid source role")
        previous_role=source_roles.setdefault(row["source"],row["source_role"])
        if previous_role != row["source_role"]: raise MatchingBlockedError("inconsistent source role")
        key=(row["source"],row["source_key"])
        if key in seen: raise MatchingBlockedError("duplicate stable source key")
        seen.add(key)
        if row["source_identity"] != f"{row['source']}:{row['source_key']}" or not row["source_key"].startswith("url-v1:sha256:"):
            raise MatchingIncompatibleError("source key strategy is not the adapter-declared url-v1 strategy")
        if not row["evidence_reference"] or not row["locator"] or not row["rule_version"]: raise MatchingBlockedError("missing evidence")
    return manifest,candidates,{"discovery-manifest":sha256(path.read_bytes()).hexdigest(),
                                "product-candidates":sha256(candidates_path.read_bytes()).hexdigest()}

def _load_rules(path: Path | None) -> dict:
    rules={"schema_version":SCHEMA_VERSION,"rules_version":"builtin-1.0.0",
           "rules":[{"rule_id":"exact-components","version":"1.0.0","approved":True},
                    {"rule_id":"exact-entry-association","version":"1.0.0","approved":True},
                    {"rule_id":COMPARISON_RULE["id"],"version":COMPARISON_RULE["version"],"approved":False}],"aliases":[]}
    if path is not None: rules=_read_json(path)
    if rules.get("schema_version")!=SCHEMA_VERSION or not rules.get("rules_version"): raise MatchingIncompatibleError("unsupported rules")
    ids=set()
    for rule in rules.get("rules",[]):
        key=(rule.get("rule_id"),rule.get("version"))
        if not all(key) or key in ids: raise MatchingInputError("invalid or duplicate matching rule")
        ids.add(key)
    required={('exact-components','1.0.0'),('exact-entry-association','1.0.0'),
              (COMPARISON_RULE['id'],COMPARISON_RULE['version'])}
    if not required <= ids: raise MatchingIncompatibleError("required matching rules are missing")
    aliases=rules.get("aliases",[]); graph=defaultdict(set); folded={}
    for alias in aliases:
        key=(alias.get("source_namespace"),str(alias.get("alias","")).casefold())
        target=alias.get("canonical_identity_value")
        if not key[0] or not key[1] or not target: raise MatchingInputError("invalid alias")
        if key in folded and folded[key]!=target: raise MatchingBlockedError("case-insensitive alias collision")
        folded[key]=target; graph[alias["alias"]].add(target)
    if any(len(v)>1 for v in graph.values()): raise MatchingBlockedError("one-to-many alias")
    def visit(node,trail):
        if node in trail: raise MatchingBlockedError("alias cycle")
        for child in graph.get(node,()): visit(child,trail|{node})
    for node in graph: visit(node,set())
    return rules

def _load_decisions(path: Path | None) -> dict[str,dict]:
    if path is None:return {}
    data=_read_json(path)
    if data.get("schema_version")!=SCHEMA_VERSION: raise MatchingIncompatibleError("unsupported decisions")
    result={}
    for item in data.get("decisions",[]):
        did=item.get("human_decision_id"); source=item.get("source_identity_value")
        if not did or not source or not item.get("candidate_canonical_identity_values") or not item.get("canonical_identity_value"): raise MatchingInputError("manual decision requires ID, reviewed candidates and explicit decision")
        if source in result and result[source]!=item: raise MatchingBlockedError("incompatible decisions; use supersedes")
        result[source]=item
    return result

def resolve(discovery_manifest: Path, output_dir: Path, *, rules_path: Path|None=None,
            decisions_path: Path|None=None, generated_at: str|None=None) -> dict:
    manifest,observations,input_hashes=_validate_discovery(discovery_manifest)
    rules=_load_rules(rules_path); decisions=_load_decisions(decisions_path)
    source_rows=[]; entries=[]; canonical_rows={}; links=[]; associations=[]; review=[]
    prepared=[]
    for raw in sorted(observations,key=lambda x:(x["source_role"]!="authoritative_existence",x["source"],x["source_key"])):
        sid=source_identity(raw["source"],raw["source_key"],key_strategy="url-v1")
        source_rows.append(asdict(sid)|{"raw_observation":raw})
        model=None
        try: model=canonical_component(raw.get("model_hint"))
        except MatchingInputError: pass
        binding=BRAND_BINDINGS[raw["source"]]; candidate=None
        if model and raw["source_role"]=="authoritative_existence":
            candidate=canonical_identity(binding["brand"],model,canonical_component(raw.get("variant_hint")))
            canonical_rows[candidate.value]=asdict(candidate)|{"brand_binding_rule_id":binding["rule_id"],"brand_binding_rule_version":binding["version"],"adopted":False,"comparison_key":comparison_key(model)}
        prepared.append((raw,sid,candidate,_association_component(raw)))
    official=defaultdict(list)
    authoritative=[]
    for raw,sid,candidate,association_component in prepared:
        if raw["source_role"]=="authoritative_existence":
            authoritative.append((raw,sid,candidate,association_component))
        if raw["source_role"]=="authoritative_existence" and candidate: official[(candidate.brand,candidate.model,candidate.variant)].append((raw,sid,candidate))
    for raw,sid,candidate,association_component in prepared:
        candidates=[]; status="missing"; adopted=None; blocking=True
        association=None
        if raw["source_role"]=="authoritative_existence" and candidate:
            candidates=[candidate.value]
            matches=official.get((candidate.brand,candidate.model,candidate.variant),[])
            requires_review=bool(raw.get("warnings")) or raw.get("review_status")=="blocked"
            if len(matches)==1 and not requires_review: status="derived_by_approved_rule"; adopted=candidate.value; blocking=False
            elif len(matches)==1: status="manual_approval_required"
            else: status="ambiguous"
        elif raw["source_role"]=="supplemental":
            exact=[x for x in authoritative if association_component and x[3]==association_component]
            normalized=[x for x in authoritative if association_component and x[3] and comparison_key(x[3])["value"]==comparison_key(association_component)["value"]]
            plausible=exact or normalized
            candidate_entry_ids=sorted("discovered:"+x[1].value for x in plausible)
            chosen=candidate_entry_ids[0] if len(exact)==1 else None
            association_status="confirmed" if len(exact)==1 else "ambiguous" if len(plausible)>1 else "proposed_for_review" if plausible else "no_authoritative_candidate"
            association={"schema_version":SCHEMA_VERSION,"source_identity_value":sid.value,
              "source_namespace":raw["source"],"source_role":raw["source_role"],
              "discovered_entry_id":chosen,"candidate_discovered_entry_ids":candidate_entry_ids,
              "association_status":association_status,"canonical_resolution_status":"unresolved",
              "matching_basis":"exact_preserved_component" if exact else "normalized_comparison_key" if normalized else "none",
              "matching_rule_id":"exact-entry-association" if exact else COMPARISON_RULE["id"],
              "matching_rule_version":"1.0.0" if exact else COMPARISON_RULE["version"],
              "human_decision_id":None,"source_url":raw["canonical_url"],"locator":raw["locator"],
              "evidence_ids":[raw["evidence_reference"]],"blocking_reasons":[] if len(exact)==1 else [association_status]}
            if len(exact)==1:
                authoritative_raw,authoritative_sid,authoritative_candidate,_=exact[0]
                # Entries are assembled later; canonical state is derived from the authoritative link.
                authoritative_link=next((x for x in links if x["source_identity"]==authoritative_sid.value),None)
                candidates=list(authoritative_link["candidate_canonical_identity_values"]) if authoritative_link else ([authoritative_candidate.value] if authoritative_candidate else [])
                if authoritative_link and not authoritative_link["blocking"]:
                    adopted=authoritative_link["canonical_identity_value"]; status="derived_by_approved_rule"; blocking=False
                    association["canonical_resolution_status"]="resolved_by_authoritative_entry"
                else:
                    status="manual_approval_required"
                    association["blocking_reasons"]=["authoritative_identity_unresolved"]
                association["evidence_ids"]=sorted({raw["evidence_reference"],authoritative_raw["evidence_reference"]})
            elif plausible:
                candidates=sorted({value for x in plausible for value in ([x[2].value] if x[2] else [])})
                status="ambiguous" if len(plausible)>1 else "normalized_candidate"
            else:
                status="supplemental_orphan"
        decision=decisions.get(sid.value)
        if decision:
            if set(decision["candidate_canonical_identity_values"])!=set(candidates): status="conflict"
            else:
                status="manual_approved"; adopted=decision["canonical_identity_value"]; blocking=False
                if association: association["canonical_resolution_status"]="manual_approved"
        evidence=[raw["evidence_reference"]]
        if association: evidence.extend(association["evidence_ids"])
        link={"schema_version":SCHEMA_VERSION,"source_identity":sid.value,"canonical_identity_value":adopted,
              "candidate_canonical_identity_values":sorted(set(candidates)),"source_namespace":raw["source"],
              "matching_rule_id":"manual-review" if decision else "exact-components",
              "matching_rule_version":"1.0.0","evidence_ids":sorted(set(evidence)),
              "resolution_status":status,"human_decision_id":decision.get("human_decision_id") if decision else None,
              "blocking":blocking,"observed_at":None}
        links.append(link)
        if association: associations.append(association)
        if blocking: review.append({"schema_version":SCHEMA_VERSION,"review_id":sid.value,"source_identity_value":sid.value,"status":status,"candidate_canonical_identity_values":link["candidate_canonical_identity_values"],"candidate_discovered_entry_ids":association["candidate_discovered_entry_ids"] if association else [],"discovered_entry_id":association["discovered_entry_id"] if association else None,"association_status":association["association_status"] if association else None,"canonical_resolution_status":association["canonical_resolution_status"] if association else "unresolved","blocking_reasons":association["blocking_reasons"] if association and association["blocking_reasons"] else [status],"evidence_ids":link["evidence_ids"]})
        if raw["source_role"]=="authoritative_existence":
            entries.append({"schema_version":SCHEMA_VERSION,"discovered_entry_id":"discovered:"+sid.value,
             "authoritative_source_identity":sid.value,"source_role":"authoritative_existence",
             "raw_observation_ids":[sid.value],"canonical_identity_value":adopted,
             "canonical_candidate_identity_values":link["candidate_canonical_identity_values"],
             "resolution_status":status,"blocking_issue_codes":[] if not blocking else [status],
             "original_categories":raw["source_categories"],"evidence_ids":link["evidence_ids"],
             "supplemental_source_identity_values":[],"review_status":"resolved" if not blocking else "blocked"})
    # Supplemental evidence attaches by entry association, independently of canonical identity.
    by_id={x["discovered_entry_id"]:x for x in entries}
    for association in associations:
        if association["discovered_entry_id"] in by_id:
            by_id[association["discovered_entry_id"]]["supplemental_source_identity_values"].append(association["source_identity_value"])
    collections={OUTPUTS[0]:source_rows,OUTPUTS[1]:entries,OUTPUTS[2]:list(canonical_rows.values()),OUTPUTS[3]:links,OUTPUTS[4]:associations,OUTPUTS[5]:review}
    for name in collections: collections[name]=sorted(collections[name],key=lambda x:canonical_bytes(x))
    output_hashes={name:sha256(b"".join(canonical_bytes(x) for x in rows)).hexdigest() for name,rows in collections.items()}
    resolved={x["canonical_identity_value"] for x in links if not x["blocking"] and x["canonical_identity_value"]}
    semantic={"schema_version":SCHEMA_VERSION,"rules_version":rules["rules_version"],"engine_version":ENGINE_VERSION,
      "input_hashes":input_hashes,"output_hashes":output_hashes,"rules":[{"rule_id":x["rule_id"],"version":x["version"]} for x in rules.get("rules",[])],
      "sources":[{"source":s,"role":next((x["source_role"] for x in observations if x["source"]==s),"supplemental"),"adapter_version":manifest["adapters"][s]} for s in sorted(manifest["sources"])],
      "universes":{"source_identity_universe":len(source_rows),"supplemental_association_universe":len(associations),"discovered_universe":len(entries),"canonical_candidate_universe":len(canonical_rows),"resolved_canonical_universe":len(resolved),"importable_universe":0,"blocked":len(review)},
      "source_mappings":{x["source_identity"]:x["canonical_identity_value"] for x in links},
      "supplemental_entry_mappings":{x["source_identity_value"]:x["discovered_entry_id"] for x in associations},
      "status":"blocked" if review else "complete","blocking_reasons":sorted({r for x in review for r in x["blocking_reasons"]}),"artifacts":list(OUTPUTS)+["matching-report.txt"]}
    semantic["semantic_fingerprint"]=sha256(canonical_bytes(semantic)).hexdigest()
    result=semantic|{"generated_at":generated_at}
    validate_domain(result,collections)
    output_dir.mkdir(parents=True,exist_ok=True)
    for name,rows in collections.items(): write_once(safe_join(output_dir,name),b"".join(canonical_bytes(x) for x in rows),output_hashes[name])
    atomic_write(safe_join(output_dir,"matching-manifest.json"),canonical_bytes(result))
    report="Catalog identity matching (offline)\n"+"\n".join(f"{k}: {v}" for k,v in sorted(semantic["universes"].items()))+f"\nstatus: {semantic['status']}\nfingerprint: {semantic['semantic_fingerprint']}\n"
    write_once(safe_join(output_dir,"matching-report.txt"),report.encode("utf-8"))
    return result

def validate_domain(manifest:dict, collections:dict[str,list[dict]]) -> None:
    source={x["value"] for x in collections[OUTPUTS[0]]}; canonical={x["value"] for x in collections[OUTPUTS[2]]}
    entry_ids={x["discovered_entry_id"] for x in collections[OUTPUTS[1]]}
    resolved={x["canonical_identity_value"] for x in collections[OUTPUTS[3]] if not x["blocking"] and x["canonical_identity_value"]}
    review_sources={x["source_identity_value"] for x in collections[OUTPUTS[5]]}
    for link in collections[OUTPUTS[3]]:
        if link["source_identity"] not in source or any(x not in canonical for x in link["candidate_canonical_identity_values"]): raise MatchingInputError("dangling identity link")
        if link["canonical_identity_value"] and link["canonical_identity_value"] not in canonical: raise MatchingInputError("dangling resolution")
        if link["resolution_status"] not in RESULTS: raise MatchingInputError("unknown result")
    universes=manifest["universes"]
    if (universes["source_identity_universe"]!=len(source) or universes["supplemental_association_universe"]!=len(collections[OUTPUTS[4]]) or
        universes["discovered_universe"]!=len(entry_ids) or universes["canonical_candidate_universe"]!=len(canonical) or universes["resolved_canonical_universe"]!=len(resolved) or universes["importable_universe"]!=0): raise MatchingInputError("universe count invariant failed")
    if any(x["source_role"]!="authoritative_existence" for x in collections[OUTPUTS[1]]): raise MatchingInputError("supplemental source expanded discovered universe")
    for association in collections[OUTPUTS[4]]:
        candidates=set(association["candidate_discovered_entry_ids"])
        if association["source_identity_value"] not in source or not candidates <= entry_ids: raise MatchingInputError("dangling supplemental association")
        if association["discovered_entry_id"] is not None and association["discovered_entry_id"] not in candidates: raise MatchingInputError("selected entry is not an association candidate")
        if association["source_role"]!="supplemental": raise MatchingInputError("authoritative source in supplemental associations")
        if association["canonical_resolution_status"]=="unresolved" and association["source_identity_value"] not in review_sources: raise MatchingInputError("unresolved supplemental evidence missing from review")

def compare_manifests(old:dict,new:dict) -> dict:
    if old.get("schema_version")!=new.get("schema_version") or old.get("engine_version")!=new.get("engine_version") or old.get("rules_version")!=new.get("rules_version"):
        return {"schema_version":SCHEMA_VERSION,"status":"comparison_blocked","reason":"incompatible versions","changes":[]}
    if not old.get("semantic_fingerprint") or not new.get("semantic_fingerprint"):
        return {"schema_version":SCHEMA_VERSION,"status":"comparison_blocked","reason":"missing fingerprint","changes":[]}
    changes=[]
    old_associations=old.get("supplemental_entry_mappings",{}); new_associations=new.get("supplemental_entry_mappings",{})
    for key in sorted(set(old_associations)|set(new_associations)):
        before=old_associations.get(key); after=new_associations.get(key)
        if before and before!=after:
            changes.append({"source_identity_value":key,"classification":"remapping_conflict","old_canonical_identity_value":before,"new_canonical_identity_value":after})
    for key in sorted(set(old.get("source_mappings",{}))|set(new.get("source_mappings",{}))):
        before_present=key in old.get("source_mappings",{}); after_present=key in new.get("source_mappings",{})
        before=old.get("source_mappings",{}).get(key); after=new.get("source_mappings",{}).get(key)
        kind="new_source_identity" if not before_present else "not_observed_in_latest" if not after_present else "preserved_resolution" if before==after and before is not None else "unchanged" if before==after else "new_resolution" if before is None else "remapping_conflict"
        changes.append({"source_identity_value":key,"classification":kind,
                        "old_canonical_identity_value":before,"new_canonical_identity_value":after})
    return {"schema_version":SCHEMA_VERSION,"status":"blocked" if any(x["classification"]=="remapping_conflict" for x in changes) else "complete","reason":None,"changes":changes}
