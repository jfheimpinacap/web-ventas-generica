#!/usr/bin/env python3
"""Composition root for offline planning and explicitly authorized local capture."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from catalog_pipeline_common.serialization import canonical_bytes
from jem_nexus_import.binary_observation import BinaryObservationError, build_plan, capture_plan, validate_plan
from jem_nexus_local_binary_transport import BinaryTransportError, LocalBinaryTransport

OUTPUTS = ("binary-observation-plan.json", "binary-observation-plan.txt")
REPORT_OUTPUTS = ("binary-observation-report.json", "binary-observation-report.txt")


def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("plan")
    command.add_argument("--snapshot", required=True)
    command.add_argument("--readiness", required=True)
    command.add_argument("--contract", required=True)
    command.add_argument("--base-url", required=True)
    command.add_argument("--output-dir", required=True)
    capture = commands.add_parser("capture-local")
    capture.add_argument("--plan", required=True)
    capture.add_argument("--plan-fingerprint", required=True)
    capture.add_argument("--output-dir", required=True)
    return root


def _read(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw.decode("utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ValueError("INPUT_OBJECT_REQUIRED")
    return value, hashlib.sha256(raw).hexdigest()


def text_projection(plan):
    counts = plan["counts"]
    lines = ["JEM Nexus local binary observation plan", "", "State: " + plan["state"],
             "Plan fingerprint: " + plan["plan_fingerprint"],
             "Contract fingerprint: " + plan["contract_fingerprint"],
             "Snapshot semantic fingerprint: " + plan["snapshot_semantic_fingerprint"],
             "Snapshot file SHA-256: " + plan["snapshot_file_sha256"],
             "Readiness file SHA-256: " + plan["readiness_file_sha256"], "",
             f"Targets total: {counts['targets_total']}", f"Image targets: {counts['image_targets']}",
             f"Technical-sheet targets: {counts['technical_sheet_targets']}",
             f"Bindings total: {counts['bindings_total']}",
             f"Observable relations: {counts['relations_observable']}",
             f"Manual relations: {counts['manual_relations']}", "", "Blockers:"]
    lines.extend("- " + item for item in plan["blockers"])
    if not plan["blockers"]: lines.append("- none")
    lines.append("Warnings:")
    lines.extend("- " + item for item in plan["warnings"])
    lines.extend(("", "Network executed: no", "Bytes observed: no", "Capture supported: yes",
                  "Mutation authorized: no", "Content published: no",
                  "Next permitted step: " + plan["next_permitted_step"], ""))
    return "\n".join(lines).encode("utf-8")


def _sync_directory(directory):
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        try: os.fsync(descriptor)
        except OSError: pass
    finally:
        os.close(descriptor)


def preflight_new_output(directory):
    target = Path(directory)
    parent = target.parent.resolve(strict=True)
    if target.exists() or target.is_symlink():
        raise FileExistsError("OUTPUT_DIRECTORY_MUST_BE_NEW")
    if target.parent.resolve(strict=True) != parent:
        raise FileExistsError("OUTPUT_PARENT_INVALID")
    return target,parent

def write_new_output(directory, documents):
    target,parent=preflight_new_output(directory)
    staging = Path(tempfile.mkdtemp(prefix="." + target.name + ".writing-", dir=parent))
    try:
        for name in sorted(documents):
            data = documents[name]
            path = staging / name
            with path.open("xb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        _sync_directory(staging)
        os.replace(staging, target)
        _sync_directory(parent)
    except Exception:
        for name in documents:
            (staging / name).unlink(missing_ok=True)
        try: staging.rmdir()
        except FileNotFoundError: pass
        raise


def report_text_projection(report):
    counts=report["counts"]
    return ("JEM Nexus local binary observation report\n\nResult: "+report["state"]+"\nPlan: "+report["plan_fingerprint"]+"\n"+"\n".join(f"{key}: {value}" for key,value in counts.items())+"\nValidations: bounded binary structure and SHA-256\nBlockers: "+str(len(report["blockers"]))+"\nWarnings: "+str(len(report["warnings"]))+"\nMutating methods: 0\nNext permitted step: "+report["next_permitted_step"]+"\n").encode("utf-8")

def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command=="plan":
            snapshot, snapshot_hash = _read(args.snapshot); readiness, readiness_hash = _read(args.readiness); contract, _ = _read(args.contract)
            plan = build_plan(snapshot, readiness, contract, args.base_url, snapshot_hash, readiness_hash)
            write_new_output(args.output_dir, {OUTPUTS[0]: canonical_bytes(plan),OUTPUTS[1]: text_projection(plan)})
        else:
            plan,plan_hash=_read(args.plan); validate_plan(plan,capture=True)
            if plan.get("plan_fingerprint")!=args.plan_fingerprint: raise BinaryObservationError("CAPTURE_PLAN_FINGERPRINT_MISMATCH")
            preflight_new_output(args.output_dir)
            token=os.environ.get("JEM_NEXUS_LOCAL_READ_TOKEN")
            if not token: raise BinaryObservationError("CAPTURE_TOKEN_MISSING")
            if os.environ.get("JEM_NEXUS_LOCAL_MUTATION_TOKEN") is not None: raise BinaryObservationError("MUTATION_TOKEN_PRESENT")
            report=capture_plan(plan,args.plan_fingerprint,plan_hash,LocalBinaryTransport(token))
            write_new_output(args.output_dir,{REPORT_OUTPUTS[0]:canonical_bytes(report),REPORT_OUTPUTS[1]:report_text_projection(report)})
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, BinaryObservationError, BinaryTransportError):
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
