#!/usr/bin/env python3
"""Offline-only CLI: plan, extract and compare immutable local evidence."""
import argparse
from pathlib import Path

from catalog_acquisition.extraction import (ExtractionBlockedError, ExtractionIncompatibleError,
 ExtractionInputError, _read_json, compare_manifests, extract, plan)
from catalog_acquisition.serialization import canonical_bytes
from catalog_acquisition.storage import atomic_write

EXIT_COMPLETE=0; EXIT_ERROR=1; EXIT_BLOCKED=2; EXIT_INCOMPATIBLE=3

def _path(value):
    path=Path(value)
    if not value.strip() or ".." in path.parts or path.resolve()==Path(path.anchor):
        raise argparse.ArgumentTypeError("empty, filesystem-root and traversal paths are forbidden")
    return path

def main(argv=None):
    parser=argparse.ArgumentParser(description="Deterministic catalog extraction (offline; no transport)")
    commands=parser.add_subparsers(dest="command",required=True)
    planning=commands.add_parser("plan"); planning.add_argument("--snapshot-manifest",required=True,type=_path); planning.add_argument("--matching-manifest",required=True,type=_path)
    run=commands.add_parser("extract"); run.add_argument("--snapshot-manifest",required=True,type=_path); run.add_argument("--snapshot-root",required=True,type=_path)
    run.add_argument("--matching-manifest",required=True,type=_path); run.add_argument("--output-dir",required=True,type=_path)
    comparison=commands.add_parser("compare"); comparison.add_argument("--old-manifest",required=True,type=_path); comparison.add_argument("--new-manifest",required=True,type=_path); comparison.add_argument("--output",required=True,type=_path)
    args=parser.parse_args(argv)
    try:
        if args.command=="plan": print(canonical_bytes(plan(args.snapshot_manifest,args.matching_manifest)).decode("utf-8"),end=""); return EXIT_COMPLETE
        if args.command=="extract":
            checkout=Path(__file__).resolve().parent
            if args.output_dir.resolve()==checkout or checkout in args.output_dir.resolve().parents: raise ExtractionInputError("output must not be the pipeline checkout")
            if args.output_dir.resolve() in {args.snapshot_root.resolve(),args.snapshot_manifest.resolve(),args.matching_manifest.resolve()}:
                raise ExtractionInputError("output collides with an input")
            result=extract(args.snapshot_manifest,args.snapshot_root,args.matching_manifest,args.output_dir)
            return EXIT_BLOCKED if result["status"]=="blocked" else EXIT_COMPLETE
        if args.output.resolve() in {args.old_manifest.resolve(),args.new_manifest.resolve()}:
            raise ExtractionInputError("comparison output collides with an input")
        result=compare_manifests(_read_json(args.old_manifest),_read_json(args.new_manifest)); atomic_write(args.output,canonical_bytes(result))
        return EXIT_INCOMPATIBLE if result["status"]=="comparison_blocked" else EXIT_COMPLETE
    except ExtractionIncompatibleError as exc: parser.exit(EXIT_INCOMPATIBLE,f"incompatible: {exc}\n")
    except ExtractionBlockedError as exc: parser.exit(EXIT_BLOCKED,f"blocked: {exc}\n")
    except (ExtractionInputError,OSError,ValueError) as exc: parser.exit(EXIT_ERROR,f"error: {exc}\n")

if __name__=="__main__": raise SystemExit(main())
