"""Offline oracle for the fail-closed production-baseline capture contract."""
from __future__ import annotations

import hashlib
import json

KINDS = ("columns", "primaryKeys", "foreignKeys", "indexes", "checks", "identities", "sequence")


def canonical_hash(rows: list[dict], columns: tuple[str, ...]) -> str:
    def value(item: object) -> str:
        return "<NULL>" if item is None else str(item).replace("\r", "").replace("\n", " ")
    lines = sorted("|".join(value(row[column]) for column in columns) for row in rows)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def compare_observations(first: dict, second: dict, known_migrations: list[str]) -> dict:
    """Return sanitized semantic evidence or raise; timestamps never participate."""
    for observation in (first, second):
        if observation.get("complete") is not True:
            raise ValueError("INCOMPLETE_OBSERVATION")
        if observation.get("database") != "jemnexusb_prod" or not observation.get("serverIdentityOk"):
            raise ValueError("PRODUCTION_IDENTITY_MISMATCH")
        if observation.get("transactionCount") != 0:
            raise ValueError("TRANSACTION_NOT_CLOSED")
        if observation.get("migrationIds") != known_migrations:
            raise ValueError("MIGRATIONS_MISMATCH")
        if set(observation.get("schemaFingerprints", {})) != set(KINDS):
            raise ValueError("FINGERPRINT_SET_INVALID")
    semantic = ("migrationIds", "schemaFingerprints")
    if any(first[key] != second[key] for key in semantic):
        raise ValueError("OBSERVATIONS_DIFFER_NO_GO")
    return {"migrationIds": first["migrationIds"], "schemaFingerprints": first["schemaFingerprints"]}


def canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
