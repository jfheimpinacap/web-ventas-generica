from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
PREPARE = (ROOT / "Prepare-JemNexusDisposableRehearsal.ps1").read_text(encoding="utf-8")
CAPTURE = (ROOT / "Capture-JemNexusProductionSchemaBaseline.sql").read_text(encoding="utf-8")


class PreparationContractTests(unittest.TestCase):
    def test_fixed_destination_and_explicit_forbidden_names(self):
        self.assertIn("$Instance='(localdb)\\MSSQLLocalDB'", PREPARE)
        self.assertIn("$Database='JemNexus_DisposableRehearsal_364'", PREPARE)
        self.assertIn("@('JemNexus_Local','jemnexusb_prod')", PREPARE)
        parameters = PREPARE[PREPARE.index("param("):PREPARE.index("Set-StrictMode")]
        for forbidden in ("Server", "Database", "ConnectionString"):
            self.assertNotIn(forbidden, parameters)

    def test_plan_only_precedes_files_connections_and_dotnet(self):
        plan = PREPARE.index("if($Mode -eq 'PlanOnly')")
        end = PREPARE.index("if($Database -cin", plan)
        block = PREPARE[plan:end]
        for forbidden in ("Get-Item", "Get-Content", "SqlConnection", "dotnet", "Remove-Item"):
            self.assertNotIn(forbidden, block)
        self.assertLess(plan, PREPARE.index("Get-Item -LiteralPath"))

    def test_create_is_guarded_and_existing_database_is_never_changed(self):
        create = PREPARE.index("CREATE DATABASE")
        for required in ("Get-Item -LiteralPath $ProductionBaselinePath", "PRODUCTION_BASELINE_INVALID",
                         "LOCAL_MIGRATION_INPUTS_INVALID", "Get-Command dotnet",
                         "dotnet ef migrations script", "CANONICAL_MIGRATION_SCRIPT_INCOMPLETE"):
            self.assertLess(PREPARE.index(required), create)
        self.assertLess(PREPARE.index("SERVERPROPERTY('IsLocalDB')"), PREPARE.index("CREATE DATABASE"))
        self.assertLess(PREPARE.index("DB_ID(N'$Database') IS NOT NULL"), PREPARE.index("CREATE DATABASE"))
        self.assertIn("DATABASE_ALREADY_EXISTS", PREPARE)
        self.assertNotIn("DROP DATABASE", PREPARE.upper())
        self.assertNotIn("RESTORE DATABASE", PREPARE.upper())

    def test_canonical_migrations_marker_and_post_inspection(self):
        self.assertEqual(22, PREPARE.count("'2026"))
        self.assertIn("dotnet ef migrations script", PREPARE)
        self.assertNotIn("--no-build", PREPARE)
        self.assertIn("EXECUTE AS USER=N'JemNexusTask364MigrationUser'", PREPARE)
        marker = PREPARE.index("sp_addextendedproperty")
        self.assertLess(PREPARE.index("MIGRATIONS_MISMATCH"), marker)
        self.assertLess(marker, PREPARE.index("-File $InspectorPath"))
        self.assertIn("PARTIAL_PREPARATION_REQUIRES_MANUAL_DIAGNOSIS", PREPARE)

    def test_production_sql_is_read_only_and_identity_guarded(self):
        self.assertIn("DB_NAME() <> N'jemnexusb_prod'", CAPTURE)
        snapshot_guard = CAPTURE.index("snapshot_isolation_state_desc=N'ON'")
        snapshot_transaction = CAPTURE.index("SET TRANSACTION ISOLATION LEVEL SNAPSHOT")
        self.assertLess(CAPTURE.index("DB_NAME() <> N'jemnexusb_prod'"), snapshot_guard)
        self.assertLess(snapshot_guard, snapshot_transaction)
        self.assertIn("SNAPSHOT_ISOLATION_NOT_ENABLED_ENABLE_ALLOW_SNAPSHOT_ISOLATION_BEFORE_CAPTURE", CAPTURE)
        self.assertNotIn("is_read_committed_snapshot_on", CAPTURE.lower())
        for verb in ("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "CREATE ", "ALTER ", "DROP ", "TRUNCATE "):
            self.assertNotIn(verb, CAPTURE.upper())
        self.assertIn("ROLLBACK TRANSACTION", CAPTURE)


if __name__ == "__main__":
    unittest.main()
