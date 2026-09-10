#!/usr/bin/env python3
"""Offline audit/plan/build/verify CLI; never imports, publishes or contacts a service."""
import argparse
import json
from pathlib import Path

from catalog_acquisition.packaging import (PackageError, audit, build_package,
    package_plan, read_json, validate_references, verify_package, write_audit)
from catalog_acquisition.serialization import canonical_bytes

EXIT_OK = 0
EXIT_INPUT_INVALID = 2
EXIT_AUDIT_BLOCKED = 3
EXIT_FINGERPRINT_MISMATCH = 4
EXIT_PACKAGE_UNSAFE = 5


def parser():
    root=argparse.ArgumentParser(description="Closed local catalog audit and canonical package")
    commands=root.add_subparsers(dest="command",required=True)
    command=commands.add_parser("audit"); command.add_argument("--input-manifest",required=True); command.add_argument("--input-root",required=True); command.add_argument("--output",required=True)
    command=commands.add_parser("plan"); command.add_argument("--audit-result",required=True); command.add_argument("--source-root",required=True); command.add_argument("--output",required=True); command.add_argument("--schema",action="append",default=[])
    command=commands.add_parser("build"); command.add_argument("--plan",required=True); command.add_argument("--plan-fingerprint",required=True); command.add_argument("--source-root",required=True); command.add_argument("--output",required=True); command.add_argument("--receipt",required=True)
    command=commands.add_parser("verify"); command.add_argument("--package",required=True); command.add_argument("--receipt"); command.add_argument("--policy")
    return root


def _emit(value):
    print(canonical_bytes(value).decode("utf-8"),end="")


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=="audit":
            manifest=read_json(args.input_manifest); artifacts=validate_references(manifest,args.input_root)
            normalized=artifacts["normalization_manifest"]["document"]
            bundle=dict(manifest["audit_bundle"]); bundle["upstream_fingerprints"]=normalized.get("input_fingerprints",{})
            result=audit(bundle); write_audit(result,args.output); _emit(result)
            return EXIT_AUDIT_BLOCKED if result["catalog_readiness"]=="audit_complete_with_blockers" else EXIT_OK
        if args.command=="plan":
            result=package_plan(read_json(args.audit_result),args.source_root,args.schema)
            Path(args.output).write_bytes(canonical_bytes(result)); _emit(result); return EXIT_AUDIT_BLOCKED if result["blocking"] else EXIT_OK
        if args.command=="build": result=build_package(read_json(args.plan),args.plan_fingerprint,args.output,args.source_root,args.receipt)
        else:
            policy=read_json(args.policy) if args.policy else None; result=verify_package(args.package,args.receipt,policy)
            if not result["valid"]: _emit(result); return EXIT_PACKAGE_UNSAFE
        _emit(result); return EXIT_OK
    except PackageError as error:
        _emit({"error":error.code,"message":str(error)})
        return EXIT_FINGERPRINT_MISMATCH if "FINGERPRINT" in error.code else EXIT_INPUT_INVALID
    except (OSError,UnicodeDecodeError,json.JSONDecodeError,KeyError,ValueError) as error:
        _emit({"error":"INPUT_INVALID","message":str(error)}); return EXIT_INPUT_INVALID


if __name__=="__main__": raise SystemExit(main())
