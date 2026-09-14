#!/usr/bin/env python3
"""Offline-only CLI that writes a future binary-observation plan."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from catalog_pipeline_common.serialization import canonical_bytes
from jem_nexus_import.binary_observation import BinaryObservationError, build_plan

OUTPUTS = ("binary-observation-plan.json", "binary-observation-plan.txt")


def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("plan")
    command.add_argument("--snapshot", required=True)
    command.add_argument("--readiness", required=True)
    command.add_argument("--contract", required=True)
    command.add_argument("--base-url", required=True)
    command.add_argument("--output-dir", required=True)
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
    lines.extend(("", "Network executed: no", "Bytes observed: no", "Capture supported: no",
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


def write_new_output(directory, documents):
    target = Path(directory)
    parent = target.parent.resolve(strict=True)
    if target.exists() or target.is_symlink():
        raise FileExistsError("OUTPUT_DIRECTORY_MUST_BE_NEW")
    if target.parent.resolve(strict=True) != parent:
        raise FileExistsError("OUTPUT_PARENT_INVALID")
    staging = Path(tempfile.mkdtemp(prefix="." + target.name + ".writing-", dir=parent))
    try:
        for name in OUTPUTS:
            data = documents[name]
            path = staging / name
            with path.open("xb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        _sync_directory(staging)
        os.replace(staging, target)
        _sync_directory(parent)
    except Exception:
        for name in OUTPUTS:
            (staging / name).unlink(missing_ok=True)
        try: staging.rmdir()
        except FileNotFoundError: pass
        raise


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        snapshot, snapshot_hash = _read(args.snapshot)
        readiness, readiness_hash = _read(args.readiness)
        contract, _ = _read(args.contract)
        plan = build_plan(snapshot, readiness, contract, args.base_url, snapshot_hash, readiness_hash)
        write_new_output(args.output_dir, {"binary-observation-plan.json": canonical_bytes(plan),
                                           "binary-observation-plan.txt": text_projection(plan)})
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, BinaryObservationError):
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
