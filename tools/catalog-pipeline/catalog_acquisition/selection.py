"""Deterministic, offline asset selection and immutable local materialization."""
from __future__ import annotations
import hashlib, json, os, shutil, tempfile
from pathlib import Path, PurePosixPath
from .paths import (category_slug, document_filename, image_filename, model_key,
                    safe_join, technical_sheet_filename, windows_collision_key)
from .serialization import canonical_bytes

SELECTION_POLICY_VERSION = "selection-v1"
NAMING_POLICY_VERSION = "catalog-layout-v1"
EXCLUDED_KINDS = {"logo", "banner", "icon", "placeholder", "editorial"}

def semantic_fingerprint(value):
    return hashlib.sha256(canonical_bytes({k:v for k,v in value.items() if k not in {"created_at","operated_at","updated_at"}})).hexdigest()

def _objects(candidates):
    grouped={}
    for item in candidates: grouped.setdefault(item["sha256"],[]).append(item)
    return [(sha, sorted(items,key=lambda x:x["relation_id"])) for sha,items in sorted(grouped.items())]

def eligible(item, approvals=()):
    reasons=[]
    if item.get("validation_status")!="valid_container": reasons.append("binary_validation")
    if item.get("encrypted") or item.get("risk_signals"): reasons.append("unsafe_bytes")
    if not item.get("canonical_identity") or not item.get("exact_variant"): reasons.append("unresolved_association")
    if item.get("association_status")!="unambiguous": reasons.append("ambiguous_relation")
    if not item.get("authorized") or not item.get("receipt_valid"): reasons.append("authorization")
    if item.get("fixture_only") or "synthetic_fixture" in item.get("provenance_types",[]): reasons.append("synthetic")
    if item.get("blocking_review"): reasons.append("blocking_review")
    if item.get("content_kind") in EXCLUDED_KINDS: reasons.append("excluded_kind")
    if item.get("association_evidence")=="filename": reasons.append("filename_inference")
    return not reasons,reasons

def _decision(identity, role, status, rule, objects, reasons=()):
    relations=sorted({r["relation_id"] for _,rs in objects for r in rs})
    hashes=[sha for sha,_ in objects]
    seed={"identity":identity,"role":role,"status":status,"rule":rule,"objects":hashes,"relations":relations}
    return {"schema_version":"1.0.0","decision_id":"sel-"+semantic_fingerprint(seed)[:24],"policy_version":SELECTION_POLICY_VERSION,
      "rule_id":rule,"canonical_identity":identity,"role":role,"status":status,"object_sha256":hashes[0] if len(hashes)==1 else None,
      "relation_ids":relations,"alternatives":hashes,"exclusion_reasons":sorted(reasons),"evidence_refs":sorted({r.get("evidence_ref","") for _,rs in objects for r in rs if r.get("evidence_ref")}),"human_approval_id":None}

def select_assets(candidates, approvals=()):
    """Select by categorical evidence; input order and locator names have no effect."""
    decisions=[]; reviews=[]
    identities=sorted({x.get("canonical_identity") for x in candidates if x.get("canonical_identity")})
    for identity in identities:
        raw=[x for x in candidates if x.get("canonical_identity")==identity]
        good=[x for x in raw if eligible(x,approvals)[0]]
        images=[x for x in good if x.get("asset_class")=="image" and x.get("source_role")=="official_primary"]
        grouped=_objects(images); primary=None
        levels=[("primary_explicit",lambda x:x.get("image_signal") in {"primary","hero"} and x.get("product_specific_locator")),("gallery_ordinal_one",lambda x:x.get("gallery_ordinal")==1),("sole_ep_image",lambda x:True)]
        for rule,predicate in levels:
            level=[g for g in grouped if any(predicate(x) for x in g[1])]
            if not level: continue
            if len(level)>1:
                decisions.append(_decision(identity,"primary","manual_review_required",rule,level,["semantic_tie"]))
                reviews.append({"schema_version":"1.0.0","review_id":"review-"+semantic_fingerprint({"i":identity,"r":rule})[:24],"policy_version":SELECTION_POLICY_VERSION,"canonical_identity":identity,"review_type":"selection_tie","status":"manual_review_required","candidate_sha256":[x[0] for x in level],"reason":"distinct objects occupy the same semantic level","fixture_only":False})
            else: primary=level[0]; decisions.append(_decision(identity,"primary","selected",rule,[primary]))
            break
        if primary is None and not any(d["canonical_identity"]==identity and d["role"]=="primary" for d in decisions): decisions.append(_decision(identity,"primary","primary_missing","no_eligible_ep_image",[]))
        remaining=[g for g in grouped if not primary or g[0]!=primary[0]]
        complete=all(any(x.get("gallery_ordinal") is not None for x in rs) for _,rs in remaining)
        ordinals=[min(x["gallery_ordinal"] for x in rs if x.get("gallery_ordinal") is not None) for _,rs in remaining] if complete else []
        if len(remaining)>4 and (not complete or len(set(ordinals))!=len(ordinals)):
            decisions.append(_decision(identity,"secondary","manual_review_required","secondary_order_incomplete",remaining,["capacity_ambiguous"]))
        else:
            ordered=sorted(remaining,key=lambda g:min(x.get("gallery_ordinal",10**9) for x in g[1]))
            for g in ordered[:4]: decisions.append(_decision(identity,"secondary","selected","explicit_gallery_order" if complete else "within_capacity",[g]))
            for g in ordered[4:]: decisions.append(_decision(identity,"secondary","unselected_capacity_limit","secondary_capacity",[g]))
        sheets=_objects([x for x in good if x.get("asset_class")=="document" and x.get("document_type")=="technical_sheet" and x.get("source_role")=="official_primary" and x.get("detected_format")=="pdf"])
        chosen=False
        for language in ("es-419","es","en-001","en"):
            level=[g for g in sheets if any(x.get("language")==language for x in g[1])]
            if not level: continue
            status="selected" if len(level)==1 else "manual_review_required"
            decisions.append(_decision(identity,"technical_sheet",status,"language_"+language,level,[] if len(level)==1 else ["incomparable_revision"])); chosen=True; break
        if chosen and decisions[-1]["status"]=="manual_review_required":
            reviews.append({"schema_version":"1.0.0","review_id":"review-"+semantic_fingerprint({"i":identity,"r":"technical_sheet"})[:24],"policy_version":SELECTION_POLICY_VERSION,"canonical_identity":identity,"review_type":"selection_tie","status":"manual_review_required","candidate_sha256":decisions[-1]["alternatives"],"reason":"distinct technical sheets have incomparable revisions in the preferred language","fixture_only":False})
        if not chosen: decisions.append(_decision(identity,"technical_sheet","technical_sheet_missing","no_eligible_ep_sheet",[]))
        selected_sheet={d["object_sha256"] for d in decisions if d["canonical_identity"]==identity and d["role"]=="technical_sheet" and d["status"]=="selected"}
        for group in _objects([x for x in good if x.get("asset_class")=="document"]):
            if group[0] not in selected_sheet: decisions.append(_decision(identity,"document","selected","preserve_additional_document",[group]))
    return sorted(decisions,key=lambda x:x["decision_id"]),sorted(reviews,key=lambda x:x["review_id"])

def build_materialization_plan(decisions, candidates, products, object_root, destination_root):
    by_hash={x["sha256"]:x for x in candidates}; operations=[]; collisions={}
    for d in decisions:
        if d["status"]!="selected" or not d["object_sha256"]: continue
        item=by_hash[d["object_sha256"]]; product=products[d["canonical_identity"]]
        if not product.get("primary_physical_category") or product.get("category_status")!="resolved": continue
        brand=model_key(product["brand_code"]); model=model_key(product["filesystem_model_key"]); base=f"{brand}/catalogo/{category_slug(product['primary_physical_category'])}/{model}"
        if d["role"]=="primary": name=image_filename(brand,model,1,item["canonical_extension"],True); rel=f"{base}/imagenes/{name}"
        elif d["role"]=="secondary":
            peers=[x for x in decisions if x["canonical_identity"]==d["canonical_identity"] and x["role"]=="secondary" and x["status"]=="selected"]
            order=2+sorted(x["object_sha256"] for x in peers).index(d["object_sha256"]); rel=f"{base}/imagenes/{image_filename(brand,model,order,item['canonical_extension'])}"
        elif d["role"]=="technical_sheet": rel=f"{base}/fichas-tecnicas/{technical_sheet_filename(brand,model,item['language'],item.get('revision'))}"
        else: rel=f"{base}/documentos/{document_filename(brand,model,item.get('document_type','additional_document'),item.get('language'),item.get('revision'),item.get('document_ordinal'))}"
        key="/".join(windows_collision_key(x) for x in PurePosixPath(rel).parts); action="create"
        if key in collisions and collisions[key]!=item["sha256"]: action="blocked_collision"
        collisions[key]=item["sha256"]
        seed={"identity":d["canonical_identity"],"sha256":item["sha256"],"path":rel,"role":d["role"]}
        operations.append({"schema_version":"1.0.0","operation_id":"op-"+semantic_fingerprint(seed)[:24],"canonical_identity":d["canonical_identity"],"object_id":item["object_id"],"source_path":item["object_path"],"destination_path":rel,"role":d["role"],"sha256":item["sha256"],"size":item["size"],"action":action,"dependencies":[d["decision_id"]],"policy_version":SELECTION_POLICY_VERSION,"rule_id":d["rule_id"],"evidence_refs":d["evidence_refs"]})
    return sorted(operations,key=lambda x:x["operation_id"])

def verify_tree(root, manifest):
    expected={x["destination_path"]:(x["sha256"],x["size"]) for x in manifest["operations"]}
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name!="selection-manifest.json"}
    errors=[]
    for rel,(digest,size) in expected.items():
        path=safe_join(root,rel)
        if not path.is_file() or path.is_symlink(): errors.append("missing_or_unsafe:"+rel); continue
        data=path.read_bytes()
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest: errors.append("modified:"+rel)
    errors += ["extra:"+x for x in sorted(actual-set(expected))]
    return {"valid":not errors,"errors":errors}

def materialize(manifest, object_root, destination, fingerprint):
    if fingerprint!=manifest.get("fingerprint"): raise ValueError("fingerprint confirmation mismatch")
    plan=manifest["operations"]
    if any(x["action"].startswith("blocked") for x in plan): return {"state":"blocked"}
    destination=Path(destination)
    if destination.exists():
        old=json.loads((destination/"selection-manifest.json").read_text(encoding="utf-8",errors="strict"))
        return {"state":"already_complete"} if old.get("fingerprint")==fingerprint and verify_tree(destination,old)["valid"] else {"state":"blocked"}
    staging=Path(tempfile.mkdtemp(prefix=".catalog-selection-",dir=destination.parent))
    try:
        for op in plan:
            source=safe_join(Path(object_root),op["source_path"]); target=safe_join(staging,op["destination_path"]); target.parent.mkdir(parents=True,exist_ok=True)
            if source.is_symlink(): raise ValueError("symlink object forbidden")
            shutil.copyfile(source,target); os.chmod(target,0o644)
            if hashlib.sha256(target.read_bytes()).hexdigest()!=op["sha256"] or target.stat().st_size!=op["size"]: raise ValueError("staged verification failed")
        (staging/"selection-manifest.json").write_bytes(canonical_bytes(manifest)); os.replace(staging,destination)
        return {"state":"completed"}
    finally:
        if staging.exists(): shutil.rmtree(staging)
