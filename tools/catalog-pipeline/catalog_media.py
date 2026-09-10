#!/usr/bin/env python3
"""Explicitly offline asset plan, validation and verification CLI."""
import argparse
from pathlib import Path
from catalog_acquisition.media import AssetBlockedError, AssetIncompatibleError, AssetInputError, plan, validate, verify
from catalog_acquisition.serialization import canonical_bytes

def _path(value):
    path=Path(value)
    if not value.strip() or ".." in path.parts or path.resolve()==Path(path.anchor): raise argparse.ArgumentTypeError("unsafe path")
    return path

def main(argv=None):
    parser=argparse.ArgumentParser(description="Offline local asset validation; no transport or downloads")
    commands=parser.add_subparsers(dest="command",required=True)
    planning=commands.add_parser("plan"); planning.add_argument("--extraction-dir",type=_path,required=True); planning.add_argument("--payload-manifest",type=_path,required=True)
    validation=commands.add_parser("validate"); validation.add_argument("--extraction-dir",type=_path,required=True); validation.add_argument("--payload-manifest",type=_path,required=True); validation.add_argument("--payload-root",type=_path,required=True); validation.add_argument("--output-root",type=_path,required=True)
    checking=commands.add_parser("verify"); checking.add_argument("--output-root",type=_path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=="plan": result=plan(args.extraction_dir,args.payload_manifest)
        elif args.command=="validate": result=validate(args.extraction_dir,args.payload_manifest,args.payload_root,args.output_root)
        else: result=verify(args.output_root)
        print(canonical_bytes(result).decode("utf-8"),end="")
        return 0 if result.get("status") not in {"blocked"} else 2
    except AssetIncompatibleError as exc: parser.exit(3,f"incompatible: {exc}\n")
    except (AssetBlockedError,AssetInputError,OSError,ValueError) as exc: parser.exit(1,f"error: {exc}\n")
if __name__=="__main__": raise SystemExit(main())
