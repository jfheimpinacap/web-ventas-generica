#!/usr/bin/env python3
"""File-only CLI for read-only JEM Nexus snapshot certification."""
import argparse
import json
from pathlib import Path

from catalog_pipeline_common.serialization import canonical_bytes
from jem_nexus_import.output import write_output_set
from jem_nexus_import.readiness import RESULTS, assess


def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("assess")
    command.add_argument("--snapshot", required=True)
    command.add_argument("--contract", required=True)
    command.add_argument("--output-dir", required=True)
    return root


def _read(path):
    value = json.loads(Path(path).read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict): raise ValueError("INPUT_OBJECT_REQUIRED")
    return value


def text_projection(report):
    lines = ["JEM Nexus local snapshot readiness", "", "Result: " + report["result"],
             "Assessment: offline", "Snapshot capture: local GET read-only",
             "Mutation authorized: no", "", "Collections:"]
    lines.extend("- {collection}: present={present}, valid_type={valid_type}, count={count}".format(**item) for item in report["checks"])
    lines.extend(("", "Binary observability:"))
    lines.extend("- {class}: count={count}, exact={exact_verification_capable}".format(**item) for item in report["binary_observability"])
    lines.extend(("", "Blockers:"))
    lines.extend("- " + item["code"] for item in report["blockers"])
    lines.extend(("", "Warnings:"))
    lines.extend("- " + item["code"] for item in report["warnings"])
    lines.extend(("", "Next permitted step: " + report["next_permitted_step"], ""))
    return "\n".join(lines).encode("utf-8")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        snapshot, contract = _read(args.snapshot), _read(args.contract)
    except (FileNotFoundError, IsADirectoryError, UnicodeError, json.JSONDecodeError, ValueError):
        return 2
    try:
        report = assess(snapshot, contract)
        if report["result"] not in RESULTS: raise ValueError("RESULT_INVALID")
    except (ValueError, TypeError, KeyError):
        return 2
    try:
        write_output_set(args.output_dir, {"local-readiness-report.json": canonical_bytes(report),
                                           "local-readiness-report.txt": text_projection(report)})
    except FileExistsError:
        return 4
    return 3 if report["result"] == "read_incompatible" else 0


if __name__ == "__main__": raise SystemExit(main())
