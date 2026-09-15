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
from .validation import validate_public_url

def initial_files():
    header=(",".join(COLUMNS)+"\n").encode("utf-8-sig")
    return {"_control/fuentes.csv":header,"_control/candidatos.json":b"[]\n",
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
    for name in ("init","inventory","plan","verify","status"): sub.add_parser(name)
    for name in ("discover","download"):
        command=sub.add_parser(name); command.add_argument("--allow-public-network",action="store_true")
        command.add_argument("--max-bytes",type=int,default=50_000_000)
        if name=="download":
            command.add_argument("--dry-run",action="store_true"); command.add_argument("--download-pending",action="store_true")
            command.add_argument("--timeout",type=float,default=30); command.add_argument("--retries",type=int,default=2); command.add_argument("--pause",type=float,default=.25)
    return result

def require_initialized(root):
    if not safe_path(root,"_control/fuentes.csv").is_file(): raise ValueError("ejecute init primero")

def main(argv=None, transport=None):
    args=parser().parse_args(argv); root=args.root.expanduser().resolve()
    if args.command=="init": initialize(root,initial_files()); return 0
    require_initialized(root)
    if args.command=="inventory": rows,pending=scan(root); print(f"archivos={len(rows)} pendientes={len(pending)}"); return 0
    if args.command=="verify":
        expected={r["ruta_relativa"]:r for r in csv.DictReader(safe_path(root,"inventario.csv").open(encoding="utf-8-sig",newline=""))}
        current,_=scan(root,write=False); failures=[r["ruta_relativa"] for r in current if r["estado"] not in {"VALID","DUPLICATE"} or expected.get(r["ruta_relativa"],{}).get("sha256")!=r["sha256"]]
        print(json.dumps({"verified":len(current)-len(failures),"failures":failures},ensure_ascii=False)); return 1 if failures else 0
    if args.command=="status":
        rows=list(csv.DictReader(safe_path(root,"inventario.csv").open(encoding="utf-8-sig",newline=""))); pending=list(csv.DictReader(safe_path(root,"pendientes-revision.csv").open(encoding="utf-8-sig",newline="")))
        models={(r["marca"],r["modelo"]) for r in rows if r["modelo"]}; images={x for x in models if any((r["marca"],r["modelo"])==x and r["tipo"]=="image" for r in rows)}; pdfs={x for x in models if any((r["marca"],r["modelo"])==x and r["tipo"]=="technical_sheet" for r in rows)}
        print(json.dumps({"modelos_encontrados":len(models),"modelos_con_imagenes":len(images),"modelos_con_pdf":len(pdfs),"modelos_incompletos":len(models-(images&pdfs)),"descargas_fallidas":sum(p["motivo"]=="DOWNLOAD_FAILED" for p in pending),"pendientes_revision":len(pending),"archivos_duplicados":sum(r["estado"]=="DUPLICATE" for r in rows)},ensure_ascii=False,sort_keys=True)); return 0
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
    manifest={"format_version":1,"tool_version":__version__,"configuration":{"max_bytes":args.max_bytes},"accepted_files":[accepted[key] for key in sorted(accepted)],"hashes":{r["path"]:r["sha256"] for r in accepted.values()},"sources":[serializable(s) for s in sources],"associations":[{"model":r.get("model"),"path":r.get("path")} for r in accepted.values()],"pending":[r for r in results if r["state"]!="VALID"],"errors":[]}
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
