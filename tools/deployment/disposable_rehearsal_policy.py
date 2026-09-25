"""Pure, offline policy oracle for synthetic task-364 preflight tests.

It deliberately contains no SQL or filesystem access.  The PowerShell inspector
enforces the same constants against live, read-only catalog observations.
"""

EXPECTED_DATABASE = "JemNexus_DisposableRehearsal_364"
EXPECTED_MARKER = "TASK-364|READONLY-PREFLIGHT|DISPOSABLE"
FINGERPRINT_KINDS = (
    "columns", "primaryKeys", "foreignKeys", "indexes", "checks",
    "identities", "sequence",
)


def evaluate(observation, production_baseline):
    blockers = []
    if observation.get("isLocalDb") != 1:
        blockers.append("SERVER_NOT_LOCALDB")
    if observation.get("database") != EXPECTED_DATABASE:
        blockers.append("DATABASE_IDENTITY_MISMATCH")
    if (observation.get("markerCount") != 1 or
            observation.get("markerValue") != EXPECTED_MARKER):
        blockers.append("DISPOSABLE_MARKER_MISSING_OR_AMBIGUOUS")
    if observation.get("migrations") != 22:
        blockers.append("MIGRATIONS_MISMATCH")
    if observation.get("importTables") != 17:
        blockers.append("IMPORT_TABLE_SET_MISMATCH")
    for kind in FINGERPRINT_KINDS:
        if observation.get("schemaFingerprints", {}).get(kind) != production_baseline.get(kind):
            blockers.append("SCHEMA_%s_MISMATCH" % kind.upper())
    if not observation.get("permissionsOk"):
        blockers.append("IMPORT_PERMISSIONS_INSUFFICIENT")
    if not observation.get("foliosOk"):
        blockers.append("FOLIO_STATE_INVALID")
    return "READY_FOR_DISPOSABLE_REHEARSAL" if not blockers else "NO-GO", blockers
