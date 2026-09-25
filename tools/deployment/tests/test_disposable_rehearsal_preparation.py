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

    def test_impersonated_user_gets_and_proves_only_migration_permissions(self):
        impersonate = PREPARE.index("EXECUTE AS USER=N'JemNexusTask364MigrationUser'")
        first_batch = PREPARE.index("foreach($batch in [regex]::Split")
        for grant in (
            "GRANT CREATE TABLE, CREATE SEQUENCE TO [JemNexusTask364MigrationUser]",
            "GRANT ALTER, REFERENCES, SELECT, INSERT, UPDATE ON SCHEMA::[$Schema]",
        ):
            self.assertLess(PREPARE.index(grant), impersonate)
        for permission in ("CREATE TABLE", "CREATE SEQUENCE", "ALTER", "REFERENCES",
                           "SELECT", "INSERT", "UPDATE"):
            check = f"HAS_PERMS_BY_NAME"
            self.assertIn(permission, PREPARE[impersonate:first_batch])
            self.assertIn(check, PREPARE[impersonate:first_batch])
        self.assertLess(PREPARE.index("IMPERSONATED_MIGRATION_PERMISSIONS_INSUFFICIENT"), first_batch)
        self.assertNotIn("SERVER ROLE", PREPARE.upper())
        self.assertNotIn("GRANT CONTROL", PREPARE.upper())

    def test_all_localdb_guards_reject_null_and_non_integer_values(self):
        guards = [line for line in PREPARE.splitlines() if "SERVERPROPERTY('IsLocalDB')" in line]
        self.assertGreaterEqual(len(guards), 3)
        for guard in guards:
            self.assertIn("COALESCE(TRY_CONVERT(int,SERVERPROPERTY('IsLocalDB')),0)<>1", guard)
            self.assertNotIn("CONVERT(int,SERVERPROPERTY('IsLocalDB'))", guard.replace("TRY_CONVERT", ""))

    def test_production_sql_is_read_only_and_identity_guarded(self):
        self.assertIn("DB_NAME() <> N'jemnexusb_prod'", CAPTURE)
        snapshot_guard = CAPTURE.index("snapshot_isolation_state_desc=N'ON'")
        snapshot_transaction = CAPTURE.index("SET TRANSACTION ISOLATION LEVEL SNAPSHOT")
        self.assertLess(CAPTURE.index("DB_NAME() <> N'jemnexusb_prod'"), snapshot_guard)
        self.assertLess(snapshot_guard, snapshot_transaction)
        self.assertIn("NO_GO_SNAPSHOT_ISOLATION_NOT_ENABLED", CAPTURE)
        self.assertNotIn("ENABLE_ALLOW_SNAPSHOT", CAPTURE)
        self.assertNotIn("is_read_committed_snapshot_on", CAPTURE.lower())
        for verb in ("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "CREATE ", "ALTER ", "DROP ", "TRUNCATE "):
            self.assertNotIn(verb, CAPTURE.upper())
        self.assertIn("ROLLBACK TRANSACTION", CAPTURE)

    def test_capture_rolls_back_intermediate_execution_or_compilation_failure(self):
        begin_try = CAPTURE.index("BEGIN TRY")
        dynamic = CAPTURE.index("EXEC sys.sp_executesql", begin_try)
        catch = CAPTURE.index("BEGIN CATCH", dynamic)
        catch_body = CAPTURE[catch:]
        self.assertIn("IF XACT_STATE() <> 0 OR @@TRANCOUNT > 0 ROLLBACK TRANSACTION", catch_body)
        self.assertIn("THROW;", catch_body)
        self.assertNotIn("\nGO\n", CAPTURE.upper())

    def test_capture_success_signal_requires_closed_transaction(self):
        rollback = CAPTURE.index("ROLLBACK TRANSACTION;", CAPTURE.index("EXEC sys.sp_executesql"))
        closed = CAPTURE.index("IF @@TRANCOUNT <> 0 THROW", rollback)
        success = CAPTURE.index("BASELINE_CAPTURE_COMPLETE", closed)
        catch = CAPTURE.index("BEGIN CATCH", success)
        self.assertLess(rollback, closed)
        self.assertLess(closed, success)
        self.assertLess(success, catch)
        self.assertEqual(1, CAPTURE.count("BASELINE_CAPTURE_COMPLETE"))


if __name__ == "__main__":
    unittest.main()
