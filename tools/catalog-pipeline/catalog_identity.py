#!/usr/bin/env python3
"""Offline-only CLI for catalog identity planning, resolution and comparison."""
import argparse
import json
from pathlib import Path

from catalog_acquisition.matching import (_read_json, _validate_discovery, compare_manifests,
 MatchingBlockedError, MatchingIncompatibleError, MatchingInputError, resolve)
from catalog_acquisition.serialization import canonical_bytes
from catalog_acquisition.storage import atomic_write

EXIT_COMPLETE=0
EXIT_ERROR=1
EXIT_BLOCKED=2
EXIT_INCOMPATIBLE=3

def _path(value):
    path=Path(value)
    if not value.strip() or path.resolve()==Path(path.anchor) or ".." in path.parts:
        raise argparse.ArgumentTypeError("empty, filesystem-root and traversal paths are forbidden")
    return path

def main(argv=None):
    parser=argparse.ArgumentParser(description="Deterministic catalog identity matching (offline)")
    commands=parser.add_subparsers(dest="command",required=True)
    plan=commands.add_parser("plan"); plan.add_argument("--discovery-manifest",required=True,type=_path)
    run=commands.add_parser("resolve"); run.add_argument("--discovery-manifest",required=True,type=_path)
    run.add_argument("--output-dir",required=True,type=_path); run.add_argument("--rules",type=_path); run.add_argument("--decisions",type=_path)
    compare=commands.add_parser("compare"); compare.add_argument("--old-manifest",required=True,type=_path)
    compare.add_argument("--new-manifest",required=True,type=_path); compare.add_argument("--output",required=True,type=_path)
    args=parser.parse_args(argv)
    try:
        if args.command=="plan":
            manifest,candidates,hashes=_validate_discovery(args.discovery_manifest)
            print(json.dumps({"status":"ready","sources":manifest["sources"],"candidates":len(candidates),"input_hashes":hashes},sort_keys=True))
            return EXIT_COMPLETE
        if args.command=="resolve":
            result=resolve(args.discovery_manifest,args.output_dir,rules_path=args.rules,decisions_path=args.decisions)
            return EXIT_BLOCKED if result["status"]=="blocked" else EXIT_COMPLETE
        result=compare_manifests(_read_json(args.old_manifest),_read_json(args.new_manifest))
        atomic_write(args.output,canonical_bytes(result))
        return EXIT_INCOMPATIBLE if result["status"]=="comparison_blocked" else EXIT_BLOCKED if result["status"]=="blocked" else EXIT_COMPLETE
    except MatchingIncompatibleError as exc:
        parser.exit(EXIT_INCOMPATIBLE,f"incompatible: {exc}\n")
    except MatchingBlockedError as exc:
        parser.exit(EXIT_BLOCKED,f"blocked: {exc}\n")
    except (MatchingInputError,OSError,ValueError) as exc:
        parser.exit(EXIT_ERROR,f"error: {exc}\n")

if __name__=="__main__": raise SystemExit(main())
