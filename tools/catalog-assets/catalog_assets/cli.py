from __future__ import annotations

import argparse
import csv
import json
import socket
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from . import __version__
from .discovery import discover
from .downloader import download_one
from .inventory import scan
from .paths import initialize, safe_path
from .reports import INVENTORY_FIELDS, PENDING_FIELDS, csv_bytes, write_csv, write_json
from .sources import COLUMNS, read_sources, serializable
from .models import MODEL_COLUMNS
from .validation import validate_public_url
from .ep_harvest import harvest_ep

def initial_files():
    header=(",".join(COLUMNS)+"\n").encode("utf-8-sig")
    return {"_control/fuentes.csv":header,"_control/candidatos.json":b"[]\n",
            "_control/modelos.csv": (",".join(MODEL_COLUMNS)+"\n").encode("utf-8-sig"),
            "_control/manifest.json":json.dumps({"format_version":1,"tool_version":__version__,"configuration":{},"accepted_files":[],"sources":[],"associations":[],"pending":[],"errors":[]},indent=2).encode()+b"\n",
            "_control/checksums.csv":b"\xef\xbb\xbfruta_relativa,sha256,bytes\n",
            "inventario.csv":csv_bytes(INVENTORY_FIELDS,[]),"pendientes-revision.csv":csv_bytes(PENDING_FIELDS,[])}

@dataclass
class Response:
    status:int; body:bytes; headers:dict; final_url:str

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class UrlTransport:
    resolve=staticmethod(socket.getaddrinfo)
    def __init__(self): self.opener=urllib.request.build_opener(SafeRedirect)
    def get(self,url,headers,timeout,max_bytes):
        validate_public_url(url)
        request=urllib.request.Request(url,headers={**headers,"User-Agent":"catalog-assets/1.0","Accept":"text/html,application/pdf,image/*"})
        with self.opener.open(request,timeout=timeout) as response:
            body=response.read(max_bytes+1)
            return Response(response.status,body,dict(response.headers),response.url)

def parser():
    result=argparse.ArgumentParser(description="Inventario y descarga independiente de activos")
    result.add_argument("--root",required=True,type=Path,help="raíz Maquinas")
    sub=result.add_subparsers(dest="command",required=True)
    for name in ("init","inventory","plan","status"): sub.add_parser(name)
    verify=sub.add_parser("verify"); verify.add_argument("--strict",action="store_true")
    for name in ("discover","download"):
        command=sub.add_parser(name); command.add_argument("--allow-public-network",action="store_true")
        command.add_argument("--max-bytes",type=int,default=50_000_000)
        if name=="download":
            command.add_argument("--dry-run",action="store_true"); command.add_argument("--download-pending",action="store_true")
            command.add_argument("--timeout",type=float,default=30); command.add_argument("--retries",type=int,default=2); command.add_argument("--pause",type=float,default=.25)
    harvest=sub.add_parser("harvest-ep")
    harvest.add_argument("--allow-public-network",action="store_true")
    harvest.add_argument("--request-delay",type=float,default=1.0)
    harvest.add_argument("--max-pages",type=int,default=100)
    harvest.add_argument("--max-models",type=int,default=39)
    harvest.add_argument("--max-bytes",type=int,default=5_000_000)
    harvest.add_argument("--timeout",type=float,default=20.0)
    return result

def require_initialized(root):
    if not safe_path(root,"_control/fuentes.csv").is_file(): raise ValueError("ejecute init primero")

def main(argv=None, transport=None):
    args=parser().parse_args(argv); root=args.root.expanduser().resolve()
    if args.command=="init": initialize(root,initial_files()); return 0
    require_initialized(root)
    if args.command=="inventory": rows,pending=scan(root); print(f"archivos={len(rows)} pendientes={len(pending)}"); return 0
    if args.command=="verify":
        with safe_path(root,"inventario.csv").open(encoding="utf-8-sig",newline="") as handle:
            expected={r["ruta_relativa"]:r for r in csv.DictReader(handle)}
        current,pending=scan(root,write=False)
        current_paths={r["ruta_relativa"] for r in current}
        failures=[r["ruta_relativa"] for r in current if r["estado_integridad"]!="VALID" or expected.get(r["ruta_relativa"],{}).get("sha256")!=r["sha256"]]
        failures.extend(sorted(set(expected)-current_paths))
        manifest=json.loads(safe_path(root,"_control/manifest.json").read_text(encoding="utf-8"))
        hashes=manifest.get("hashes",{})
        current_hashes={r["ruta_relativa"]:r["sha256"] for r in current}
        failures.extend(path for path,digest in hashes.items() if current_hashes.get(path)!=digest)
        classification=sorted({p["ruta_relativa"] for p in pending if p["motivo"] in {"MODEL_UNKNOWN","MODEL_AMBIGUOUS","DUPLICATE"}})
        if args.strict: failures.extend(x for x in classification if x not in failures)
        print(json.dumps({"verified":len(current)-len(set(failures)),"failures":sorted(set(failures)),"classification_pending":classification},ensure_ascii=False)); return 1 if failures else 0
    if args.command=="status":
        with safe_path(root,"inventario.csv").open(encoding="utf-8-sig",newline="") as handle: rows=list(csv.DictReader(handle))
        with safe_path(root,"pendientes-revision.csv").open(encoding="utf-8-sig",newline="") as handle: pending=list(csv.DictReader(handle))
        models={(r["marca"],r["modelo"]) for r in rows if r["modelo"]}; images={x for x in models if any((r["marca"],r["modelo"])==x and r["tipo"]=="image" for r in rows)}; pdfs={x for x in models if any((r["marca"],r["modelo"])==x and r["tipo"]=="technical_sheet" for r in rows)}
        listing=lambda values:[{"marca":b,"modelo":m} for b,m in sorted(values)]
        by_hash={}
        for row in rows: by_hash.setdefault(row["sha256"],[]).append(row)
        duplicates=[]
        for digest, group in sorted(by_hash.items()):
            for duplicate in group[1:]:
                primary=group[0]; duplicates.append({"sha256":digest,"ruta_principal":primary["ruta_relativa"],"ruta_duplicada":duplicate["ruta_relativa"],"marca":duplicate["marca"] or primary["marca"],"modelo":duplicate["modelo"] or primary["modelo"],"bytes":int(duplicate["bytes"]),"accion_sugerida":"revisar ambas rutas; no eliminar automáticamente"})
        reasons={}
        for item in pending: reasons[item["motivo"]]=reasons.get(item["motivo"],0)+1
        result={"modelos_encontrados":len(models),"modelos_con_imagenes":len(images),"modelos_con_pdf":len(pdfs),"modelos_incompletos":len(models-(images&pdfs)),"modelos_sin_imagen":listing(models-images),"modelos_sin_pdf":listing(models-pdfs),"archivos_duplicados":len(duplicates),"duplicados":duplicates,"pendientes_revision":len(pending),"pendientes_por_motivo":dict(sorted(reasons.items())),"descargas_fallidas":reasons.get("DOWNLOAD_FAILED",0)}
        print(json.dumps(result,ensure_ascii=False)); return 0
    if args.command=="harvest-ep":
        if not args.allow_public_network: raise ValueError("la red requiere --allow-public-network")
        result=harvest_ep(root,transport or UrlTransport(),args.request_delay,args.max_pages,args.max_models,args.max_bytes,args.timeout)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True)); return 0
    sources=read_sources(safe_path(root,"_control/fuentes.csv"))
    if args.command=="plan":
        plan={"format_version":1,"sources":[serializable(s) for s in sources]}; write_json(safe_path(root,"_control/candidatos.json"),plan,root); print(f"filas={len(sources)}"); return 0
    if not args.allow_public_network: raise ValueError("la red requiere --allow-public-network")
    transport=transport or UrlTransport()
    if args.command=="discover":
        candidates=discover(sources,transport,args.max_bytes); write_json(safe_path(root,"_control/candidatos.json"),{"format_version":1,"candidates":candidates},root); print(f"candidatos={len(candidates)}"); return 0
    document=json.loads(safe_path(root,"_control/candidatos.json").read_text(encoding="utf-8")); candidates=document.get("candidates",[]); results=[]
    primary_available={(c.get("target_brand"),c.get("model"),c.get("asset_type")) for c in candidates if c.get("approved") and c.get("source_role")=="primary"}
    for candidate in candidates:
        if not candidate.get("approved") and not args.download_pending: continue
        if args.dry_run: results.append({"state":"DRY_RUN","url":candidate["url"]}); continue
        if candidate.get("source_name","").upper()=="GAM" and (candidate.get("target_brand")!="EP" or candidate.get("source_role")!="fallback"): continue
        if candidate.get("source_name","").upper()=="GAM" and (candidate.get("target_brand"),candidate.get("model"),candidate.get("asset_type")) in primary_available: continue
        try:
            result=download_one(root,candidate,transport,args.max_bytes,args.timeout,args.retries,args.pause,pending=not candidate.get("approved"))
        except ValueError as error:
            reason="MIME_CONFLICT" if "MIME_CONFLICT" in str(error) else "INVALID_BINARY"
            result={"state":reason,"error":str(error)}
        results.append({**result,"source":candidate.get("source_name"),"url":candidate["url"],"model":candidate.get("model")})
        time.sleep(args.pause)
    manifest_path=safe_path(root,"_control/manifest.json")
    previous=json.loads(manifest_path.read_text(encoding="utf-8")); accepted={r.get("path"):r for r in previous.get("accepted_files",[]) if r.get("path")}
    accepted.update({r["path"]:r for r in results if r["state"]=="VALID"})
    manifest={"format_version":1,"tool_version":__version__,"configuration":{"max_bytes":args.max_bytes},"accepted_files":[accepted[key] for key in sorted(accepted)],"hashes":{r["path"]:r["sha256"] for r in accepted.values()},"sources":[serializable(s) for s in sources],"associations":[{"brand":next((c.get("target_brand") for c in candidates if c.get("model")==r.get("model")),""),"model":r.get("model"),"path":r.get("path"),"method":"canonical_filename"} for r in accepted.values()],"pending":[r for r in results if r["state"]!="VALID"],"errors":[]}
    write_json(manifest_path,manifest,root)
    pending=[]
    for index,result in enumerate((r for r in results if r["state"]!="VALID"),1):
        row={field:"" for field in PENDING_FIELDS}; row.update(id=f"download-{index:04d}",marca_sugerida="EP" if result.get("source")=="GAM" else "",modelo_sugerido=result.get("model", ""),motivo=result["state"],fuente=result.get("source", ""),url_original=result.get("url", ""),ruta_relativa=result.get("path", ""),accion_sugerida="revisar candidato o reintentar")
        pending.append(row)
    if pending: write_csv(safe_path(root,"pendientes-revision.csv"),PENDING_FIELDS,pending,root)
    print(json.dumps(results,ensure_ascii=False)); return 0

def entrypoint():
    try: raise SystemExit(main())
    except ValueError as error: print(f"error: {error}",file=sys.stderr); raise SystemExit(2)
