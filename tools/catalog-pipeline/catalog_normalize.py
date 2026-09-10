#!/usr/bin/env python3
"""Offline normalization CLI: planning, immutable execution, and verification."""
import argparse
import json
from pathlib import Path

from catalog_acquisition.normalization import NormalizationError, build_plan, normalize_to, verify_output
from catalog_acquisition.serialization import canonical_bytes

EXIT_OK, EXIT_REVIEW, EXIT_INVALID = 0, 3, 4

def read(path): return json.loads(Path(path).read_text(encoding="utf-8", errors="strict"))
def parser():
    value=argparse.ArgumentParser(description="Offline normalization; never imports or publishes")
    commands=value.add_subparsers(dest="command",required=True)
    plan=commands.add_parser("plan"); plan.add_argument("--inputs",required=True)
    normalize=commands.add_parser("normalize"); normalize.add_argument("--inputs",required=True); normalize.add_argument("--output-root",required=True); normalize.add_argument("--fingerprint",required=True)
    verify=commands.add_parser("verify"); verify.add_argument("--output-root",required=True)
    return value
def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=="verify": result=verify_output(args.output_root)
        else:
            result=build_plan(read(args.inputs))
            if args.command=="normalize": result=normalize_to(result,args.fingerprint,args.output_root)
        print(canonical_bytes(result).decode("utf-8"),end="")
        if isinstance(result,dict) and (result.get("valid") is False or result.get("reviews")): return EXIT_REVIEW
        return EXIT_OK
    except (NormalizationError, OSError, ValueError, json.JSONDecodeError) as error:
        print(canonical_bytes({"error":getattr(error,"code","INVALID_INPUT"),"message":str(error)}).decode("utf-8"),end="")
        return EXIT_INVALID
if __name__=="__main__": raise SystemExit(main())
