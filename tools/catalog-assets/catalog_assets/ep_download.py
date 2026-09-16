from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

from . import __version__
from .downloader import download_one
from .ep_harvest import CANDIDATE_FIELDS, CHECKPOINT_VERSION, FAMILIES, MODEL_FIELDS, _allowed_asset
from .paths import safe_path
from .reports import INVENTORY_FIELDS, PENDING_FIELDS, write_csv, write_json
from .sources import read_sources

RESULT_FIELDS = ("source", "target_brand", "model", "asset_type", "asset_url", "page_url",
                 "path", "bytes", "sha256", "state", "detail")


class EpDownloadError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(json.dumps({"error": code, "detail": detail}, ensure_ascii=False, sort_keys=True))


def _read_csv(path: Path, fields: tuple[str, ...], code: str) -> list[dict]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != fields:
                raise EpDownloadError(code, f"columnas incompatibles: {path.name}")
            return list(reader)
    except (OSError, csv.Error, UnicodeError) as error:
        raise EpDownloadError(code, f"no se pudo leer {path.name}: {error}") from None


def load_ep_plan(root: Path) -> dict:
    checkpoint_path = safe_path(root, "_control/research/ep-harvest-checkpoint.json")
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EpDownloadError("CHECKPOINT_MISSING", "falta el checkpoint final de harvest-ep") from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise EpDownloadError("CHECKPOINT_CORRUPT", "el checkpoint de harvest-ep no es JSON válido") from None
    if not isinstance(checkpoint, dict) or any(checkpoint.get(k) != v for k, v in CHECKPOINT_VERSION.items()):
        raise EpDownloadError("CHECKPOINT_INCOMPATIBLE", "se requiere format=2, parser=4 y matcher=2")

    research = safe_path(root, "_control/research")
    inventory = _read_csv(research / "ep-model-inventory.csv", MODEL_FIELDS, "HARVEST_INVENTORY_INVALID")
    raw_candidates = _read_csv(research / "ep-asset-candidates.csv", CANDIDATE_FIELDS, "HARVEST_CANDIDATES_INVALID")
    try:
        sources = read_sources(safe_path(root, "_control/fuentes.csv"))
    except (OSError, ValueError) as error:
        raise EpDownloadError("HARVEST_SOURCES_INVALID", str(error)) from None
    source_keys = {(s.target_brand, s.model, s.source_name, s.source_role, s.page_url,
                    s.asset_type, s.asset_url, s.enabled, s.notes) for s in sources}

    concrete = sorted({r["model"] for r in inventory if r["target_brand"] == "EP" and r["status"] != "FAMILY_REVIEW"})
    excluded = sorted({r["model"] for r in inventory if r["status"] == "FAMILY_REVIEW"})
    if set(excluded) != FAMILIES:
        raise EpDownloadError("FAMILY_SET_INVALID", "las familias en revisión no coinciden con el harvest")
    accepted = []
    seen = set()
    for row in raw_candidates:
        key = (row["target_brand"], row["model"], row["source_name"], row["source_role"],
               row["page_url"], row["asset_type"], row["asset_url"], False,
               "VALIDATION_DEFERRED; exact model page; direct asset discovered")
        if (row["target_brand"] != "EP" or row["model"] not in concrete or row["model"] in FAMILIES
                or row["asset_type"] not in {"image", "technical_sheet"}
                or row["source_name"] not in {"EP", "GAM"}
                or row["source_role"] not in ({"primary"} if row["source_name"] == "EP" else {"fallback"})
                or row["validation_status"] != "VALIDATION_DEFERRED" or not row["model_evidence"].strip()
                or not row["page_url"].strip() or not row["asset_url"].strip()
                or not _allowed_asset(row["asset_url"], row["source_name"], row["asset_type"])
                or key not in source_keys):
            raise EpDownloadError("CANDIDATE_NOT_APPROVED", f"candidato no autorizado: {row.get('model', '')}")
        logical = (row["model"], row["asset_type"], row["asset_url"])
        if logical in seen:
            continue
        seen.add(logical)
        accepted.append(row)
    accepted.sort(key=lambda r: (r["model"].casefold(), r["asset_type"], int(r["priority"]), r["asset_url"]))
    present = {(r["model"], r["asset_type"]) for r in accepted}
    return {"checkpoint": checkpoint, "models": concrete, "excluded": excluded,
            "candidates": accepted,
            "missing_image": sorted(m for m in concrete if (m, "image") not in present),
            "missing_sheet": sorted(m for m in concrete if (m, "technical_sheet") not in present)}


def _base_summary(plan: dict, dry_run: bool) -> dict:
    candidates = plan["candidates"]
    return {"format_version": 1, "checkpoint_version": dict(CHECKPOINT_VERSION),
            "models_total": len(plan["models"]), "concrete_models": len(plan["models"]),
            "families_excluded": plan["excluded"], "candidates_total": len(candidates),
            "image_candidates": sum(r["asset_type"] == "image" for r in candidates),
            "technical_sheet_candidates": sum(r["asset_type"] == "technical_sheet" for r in candidates),
            "attempted": 0, "downloaded": 0, "already_present": 0, "duplicates": 0,
            "failed": 0, "missing_source": len(plan["missing_image"]) + len(plan["missing_sheet"]),
            "models_complete": len(plan["models"]) - len(set(plan["missing_image"] + plan["missing_sheet"])),
            "models_incomplete": len(set(plan["missing_image"] + plan["missing_sheet"])),
            "models_missing_image": plan["missing_image"],
            "models_missing_technical_sheet": plan["missing_sheet"],
            "requests_this_run": 0, "bytes_downloaded": 0, "dry_run": dry_run}


def download_ep_harvest(root: Path, transport, *, dry_run=False, only="all", request_delay=0.0,
                        max_files=None, max_bytes=50_000_000, timeout=30.0) -> tuple[dict, bool]:
    plan = load_ep_plan(root)
    summary = _base_summary(plan, dry_run)
    if dry_run:
        return summary, False

    report_path = safe_path(root, "_control/ep-download-results.csv")
    previous = _read_csv(report_path, RESULT_FIELDS, "DOWNLOAD_REPORT_INVALID") if report_path.exists() else []
    completed = {(r["model"], r["asset_type"], r["asset_url"]): r for r in previous}
    results = []
    for model in plan["missing_image"]:
        results.append({"source": "", "target_brand": "EP", "model": model, "asset_type": "image",
                        "asset_url": "", "page_url": "", "path": "", "bytes": "", "sha256": "",
                        "state": "MISSING_SOURCE", "detail": "harvest sin fuente"})
    for model in plan["missing_sheet"]:
        results.append({"source": "", "target_brand": "EP", "model": model, "asset_type": "technical_sheet",
                        "asset_url": "", "page_url": "", "path": "", "bytes": "", "sha256": "",
                        "state": "MISSING_SOURCE", "detail": "harvest sin fuente"})

    selected = [r for r in plan["candidates"] if only == "all" or r["asset_type"] == only]
    for index, row in enumerate(selected):
        old = completed.get((row["model"], row["asset_type"], row["asset_url"]))
        if old and old["state"] in {"DOWNLOADED", "ALREADY_PRESENT", "DUPLICATE"} and old["path"]:
            path = safe_path(root, old["path"])
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == old["sha256"]:
                results.append({**old, "state": "ALREADY_PRESENT", "detail": "hash confirmado; sin solicitud"})
                summary["already_present"] += 1
                continue
        if max_files is not None and summary["attempted"] >= max_files:
            results.append({"source": row["source_name"], "target_brand": "EP", "model": row["model"],
                            "asset_type": row["asset_type"], "asset_url": row["asset_url"], "page_url": row["page_url"],
                            "path": "", "bytes": "", "sha256": "", "state": "SKIPPED_LIMIT", "detail": "max-files"})
            continue
        summary["attempted"] += 1
        summary["requests_this_run"] += 1
        try:
            outcome = download_one(root, {"url": row["asset_url"], "target_brand": "EP", "model": row["model"],
                                          "expected_kind": row["asset_type"], "allowed_source": row["source_name"]}, transport, max_bytes, timeout, 0, 0)
            state = {"VALID": "DOWNLOADED", "DUPLICATE": "DUPLICATE", "DOWNLOAD_FAILED": "FAILED_NETWORK"}[outcome["state"]]
            detail = outcome.get("error", "")
        except ValueError as error:
            outcome = {}
            text = str(error)
            safe_path(root, "_control/parciales/" + hashlib.sha256(row["asset_url"].encode()).hexdigest() + ".part").unlink(missing_ok=True)
            state = "TYPE_MISMATCH" if "TYPE_MISMATCH" in text or "MIME_CONFLICT" in text else "INVALID_BINARY"
            detail = text
        result = {"source": row["source_name"], "target_brand": "EP", "model": row["model"],
                  "asset_type": row["asset_type"], "asset_url": row["asset_url"], "page_url": row["page_url"],
                  "path": outcome.get("path", ""), "bytes": outcome.get("bytes", ""),
                  "sha256": outcome.get("sha256", ""), "state": state, "detail": detail}
        results.append(result)
        if state == "DOWNLOADED":
            summary["downloaded"] += 1
            summary["bytes_downloaded"] += int(outcome["bytes"])
        elif state == "DUPLICATE": summary["duplicates"] += 1
        elif state in {"FAILED_NETWORK", "INVALID_BINARY", "TYPE_MISMATCH"}: summary["failed"] += 1
        if request_delay and index + 1 < len(selected): time.sleep(request_delay)

    write_csv(report_path, RESULT_FIELDS, results, root)
    accepted = [r for r in results if r["state"] in {"DOWNLOADED", "ALREADY_PRESENT", "DUPLICATE"} and r["path"]]
    manifest_path = safe_path(root, "_control/manifest.json")
    try: old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError): old_manifest = {}
    accepted_by_path = {r.get("path"): r for r in old_manifest.get("accepted_files", []) if r.get("path")}
    accepted_by_path.update({r["path"]: r for r in accepted})
    all_accepted = [accepted_by_path[path] for path in sorted(accepted_by_path)]
    write_json(manifest_path, {"format_version": 1, "tool_version": __version__,
               "configuration": {"command": "download-ep-harvest", "max_bytes": max_bytes},
               "accepted_files": all_accepted, "hashes": {r["path"]: r["sha256"] for r in all_accepted},
               "sources": old_manifest.get("sources", []), "associations": old_manifest.get("associations", []),
               "pending": [r for r in results if r["state"] not in {"DOWNLOADED", "ALREADY_PRESENT", "DUPLICATE"}], "errors": []}, root)
    checksum_path = safe_path(root, "_control/checksums.csv")
    old_checksums = _read_csv(checksum_path, ("ruta_relativa", "sha256", "bytes"), "CHECKSUMS_INVALID") if checksum_path.exists() else []
    checksums = {r["ruta_relativa"]: r for r in old_checksums}
    checksums.update({r["path"]: {"ruta_relativa": r["path"], "sha256": r["sha256"], "bytes": r["bytes"]} for r in accepted})
    write_csv(safe_path(root, "_control/checksums.csv"), ("ruta_relativa", "sha256", "bytes"),
              list(checksums.values()), root)
    pending_path = safe_path(root, "pendientes-revision.csv")
    old_pending = _read_csv(pending_path, PENDING_FIELDS, "PENDING_INVALID") if pending_path.exists() else []
    pending = [r for r in old_pending if r.get("marca_sugerida") != "EP"]
    for i, r in enumerate((x for x in results if x["state"] not in {"DOWNLOADED", "ALREADY_PRESENT", "DUPLICATE"}), 1):
        pending.append({"id": f"ep-download-{i:04d}", "marca_sugerida": "EP", "modelo_sugerido": r["model"],
                        "tipo": r["asset_type"], "motivo": r["state"], "fuente": r["source"],
                        "pagina_origen": r["page_url"], "url_original": r["asset_url"], "ruta_relativa": r["path"],
                        "accion_sugerida": "revisar fuente o reintentar"})
    write_csv(safe_path(root, "pendientes-revision.csv"), PENDING_FIELDS, pending, root)
    inventory_path = safe_path(root, "inventario.csv")
    old_inventory = _read_csv(inventory_path, INVENTORY_FIELDS, "INVENTORY_INVALID") if inventory_path.exists() else []
    inventory = [r for r in old_inventory if not (r.get("marca") == "EP" and r.get("ruta_relativa") in {a["path"] for a in accepted})]
    for r in accepted:
        row = {field: "" for field in INVENTORY_FIELDS}
        row.update(marca="EP", modelo=r["model"], tipo=r["asset_type"], posicion="1",
                   archivo=Path(r["path"]).name, ruta_relativa=r["path"], ubicacion="canonica",
                   metodo_asociacion="ep_harvest", estado_integridad="VALID", estado_clasificacion="MATCHED",
                   fuente=r["source"], pagina_origen=r["page_url"], url_original=r["asset_url"],
                   sha256=r["sha256"], bytes=r["bytes"], estado=r["state"])
        inventory.append(row)
    write_csv(inventory_path, INVENTORY_FIELDS, inventory, root)
    return summary, bool(summary["failed"])
