import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "Inspect-JemNexusDisposableRehearsal.ps1"
POLICY = ROOT / "disposable_rehearsal_policy.py"
SPEC = importlib.util.spec_from_file_location("policy", POLICY)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


def valid_observation():
    fingerprints = {kind: kind + "-synthetic" for kind in policy.FINGERPRINT_KINDS}
    return {
        "isLocalDb": 1, "database": policy.EXPECTED_DATABASE,
        "markerCount": 1, "markerValue": policy.EXPECTED_MARKER,
        "applicationSchema": policy.APPLICATION_SCHEMA,
        "historySchema": policy.HISTORY_SCHEMA,
        "sequenceSchema": policy.SEQUENCE_SCHEMA,
        "markerScope": policy.MARKER_SCOPE,
        "migrations": 22, "importTables": 17,
        "schemaFingerprints": fingerprints.copy(), "permissionsOk": True,
        "foliosOk": True,
    }, {"schema": policy.APPLICATION_SCHEMA,
        "historySchema": policy.HISTORY_SCHEMA,
        "sequenceSchema": policy.SEQUENCE_SCHEMA,
        "markerScope": policy.MARKER_SCOPE, **fingerprints}


class DisposableRehearsalPolicyTests(unittest.TestCase):
    def test_valid_identity_and_contract_is_ready(self):
        observed, baseline = valid_observation()
        self.assertEqual(("READY_FOR_DISPOSABLE_REHEARSAL", []),
                         policy.evaluate(observed, baseline))

    def test_rejects_non_localdb_wrong_database_and_missing_marker(self):
        mutations = (
            ("isLocalDb", 0, "SERVER_NOT_LOCALDB"),
            ("database", "JemNexus_Local", "DATABASE_IDENTITY_MISMATCH"),
            ("markerCount", 0, "DISPOSABLE_MARKER_MISSING_OR_AMBIGUOUS"),
        )
        for key, value, expected in mutations:
            with self.subTest(key=key):
                observed, baseline = valid_observation()
                observed[key] = value
                status, blockers = policy.evaluate(observed, baseline)
                self.assertEqual("NO-GO", status)
                self.assertIn(expected, blockers)

    def test_rejects_migration_or_every_schema_component_drift(self):
        observed, baseline = valid_observation()
        observed["migrations"] = 21
        self.assertIn("MIGRATIONS_MISMATCH", policy.evaluate(observed, baseline)[1])
        for kind in policy.FINGERPRINT_KINDS:
            with self.subTest(kind=kind):
                observed, baseline = valid_observation()
                observed["schemaFingerprints"][kind] = "different"
                self.assertEqual("NO-GO", policy.evaluate(observed, baseline)[0])

    def test_rejects_dbo_only_application_tables(self):
        observed, baseline = valid_observation()
        observed["applicationSchema"] = "dbo"
        observed["importTables"] = 17
        self.assertIn("APPLICATION_SCHEMA_MISMATCH", policy.evaluate(observed, baseline)[1])

    def test_rejects_wrong_baseline_application_schema(self):
        observed, baseline = valid_observation()
        baseline["schema"] = "dbo"
        self.assertIn("PRODUCTION_BASELINE_INVALID", policy.evaluate(observed, baseline)[1])

    def test_rejects_wrong_sequence_or_history_location(self):
        for key, blocker in (("sequenceSchema", "SELLER_SEQUENCE_SCHEMA_MISMATCH"),
                             ("historySchema", "MIGRATION_HISTORY_SCHEMA_MISMATCH")):
            with self.subTest(key=key):
                observed, baseline = valid_observation()
                observed[key] = "dbo"
                self.assertIn(blocker, policy.evaluate(observed, baseline)[1])

    def test_schema_queries_and_output_use_fixed_effective_locations(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("$ApplicationSchema = 'jemnexusb_api'", source)
        self.assertIn("[$HistorySchema].[__EFMigrationsHistory]", source)
        self.assertIn("s.name='$SequenceSchema'", source)
        self.assertIn("applicationSchema=$ApplicationSchema", source)
        self.assertNotIn("s.name='dbo'", source)
        self.assertNotIn("FROM dbo.", source)

    def test_plan_only_contract_precedes_every_connection_or_file_read(self):
        source = SCRIPT.read_text(encoding="utf-8")
        plan = source.index("if($Mode -eq 'PlanOnly')")
        connection = source.index("$connection=New-Object Data.SqlClient.SqlConnection")
        file_read = source.index("Get-Content -LiteralPath")
        self.assertLess(plan, connection)
        self.assertLess(plan, file_read)
        plan_block = source[plan:source.index("if([string]::IsNullOrWhiteSpace", plan)]
        for forbidden in ("Get-Content", "Get-Item", "CreateDirectory", "SqlConnection"):
            self.assertNotIn(forbidden, plan_block)
        self.assertIn("PLAN_ONLY_REJECTS_INPUT_PATHS", plan_block)

    def test_tool_has_no_apply_mode_or_arbitrary_connection_parameters(self):
        source = SCRIPT.read_text(encoding="utf-8")
        parameter_block = source[source.index("param("):source.index("Set-StrictMode")]
        self.assertNotIn("Apply", parameter_block)
        self.assertNotIn("ConnectionString", parameter_block)
        self.assertNotIn("Server", parameter_block)
        self.assertNotIn("Database", parameter_block)
        self.assertIn("IntegratedSecurity=$true", source)
        self.assertIn("ApplicationIntent=[Data.SqlClient.ApplicationIntent]::ReadOnly", source)


if __name__ == "__main__":
    unittest.main()
